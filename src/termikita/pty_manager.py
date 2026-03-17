"""PTY (pseudo-terminal) lifecycle management for Termikita.

Handles spawning a shell process, bidirectional I/O via a background read thread,
window resize signals, and clean shutdown without zombie processes.
"""

import fcntl
import os
import pty
import select
import signal
import struct
import termios
import threading
from typing import Callable, Optional

from termikita.constants import DEFAULT_COLORTERM, DEFAULT_TERM, PTY_READ_CHUNK_SIZE

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def get_user_shell() -> str:
    """Return the user's preferred shell, falling back to /bin/zsh."""
    shell = os.environ.get("SHELL", "/bin/zsh")
    return shell if os.path.exists(shell) else "/bin/zsh"


def _build_child_env() -> dict[str, str]:
    """Build environment dict for the child shell process."""
    env = os.environ.copy()
    env["TERM"] = DEFAULT_TERM
    env["COLORTERM"] = DEFAULT_COLORTERM
    env["LANG"] = env.get("LANG", "en_US.UTF-8")
    # Suppress zsh's PROMPT_SP (%) mark on fresh start
    env["PROMPT_EOL_MARK"] = ""
    return env


# ---------------------------------------------------------------------------
# PTYManager
# ---------------------------------------------------------------------------

class PTYManager:
    """Manage one pseudo-terminal session (shell process + I/O thread).

    Lifecycle::

        mgr = PTYManager(cols=80, rows=24, on_output=my_callback)
        mgr.write(b"echo hello\\n")
        mgr.resize(cols=120, rows=30)
        mgr.shutdown()
    """

    def __init__(
        self,
        cols: int,
        rows: int,
        on_output: Callable[[bytes], None],
        on_exit: Optional[Callable[[int], None]] = None,
        working_dir: Optional[str] = None,
        shell: Optional[str] = None,
    ) -> None:
        """Spawn the user's shell and start the background read thread.

        Args:
            cols: Initial terminal width in characters.
            rows: Initial terminal height in characters.
            on_output: Callback invoked with raw bytes from the child process.
            on_exit: Optional callback invoked with the exit code when the
                     child process terminates.
            working_dir: Optional starting directory for the shell process.
            shell: Optional shell path override; empty/None = auto-detect.
        """
        self._on_output = on_output
        self._on_exit = on_exit
        self._running = False
        self._master_fd: Optional[int] = None
        self._child_pid: Optional[int] = None
        self._read_thread: Optional[threading.Thread] = None

        shell_path = shell if shell and os.path.exists(shell) else get_user_shell()
        self._spawn(shell_path, cols, rows, _build_child_env(), working_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Write raw bytes (user input) to the PTY master fd.

        Handles short writes to prevent split UTF-8 sequences (e.g. Vietnamese
        characters like "ả" = 3 UTF-8 bytes could be partially written).
        No-op if the session is no longer alive.
        """
        if not self._running or self._master_fd is None:
            return
        try:
            mv = memoryview(data)
            while mv:
                written = os.write(self._master_fd, mv)
                mv = mv[written:]
        except OSError:
            # PTY already closed; ignore silently
            pass

    def resize(self, cols: int, rows: int) -> None:
        """Update PTY window dimensions and deliver SIGWINCH to the child.

        Args:
            cols: New terminal width in characters.
            rows: New terminal height in characters.
        """
        if self._master_fd is None:
            return
        try:
            # TIOCSWINSZ struct: rows, cols, xpixel, ypixel
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def shutdown(self) -> None:
        """Kill the child process, close the master fd, and stop the read thread.

        Correct order: kill process → stop reader → close fd.
        Safe to call multiple times.
        """
        if not self._running and self._master_fd is None:
            return

        self._running = False

        # Snapshot and clear pid to prevent race with _handle_child_exit
        child_pid = self._child_pid
        self._child_pid = None
        master_fd = self._master_fd
        self._master_fd = None

        # Step 1: Kill child process — causes slave PTY to close,
        # which makes master fd return EOF so reader thread can exit.
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGHUP)
            except ProcessLookupError:
                child_pid = None

        # Step 2: Close master fd — unblocks reader thread if child
        # hasn't exited yet (reader gets OSError and breaks).
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

        # Step 3: Stop reader thread (should exit quickly now).
        if self._read_thread is not None and self._read_thread.is_alive():
            self._read_thread.join(timeout=2.0)
            self._read_thread = None

        # Step 4: Reap child process (non-blocking with SIGKILL fallback).
        if child_pid is not None:
            import time
            for _ in range(5):
                try:
                    pid, _ = os.waitpid(child_pid, os.WNOHANG)
                    if pid != 0:
                        return
                except ChildProcessError:
                    return
                time.sleep(0.05)
            try:
                os.kill(child_pid, signal.SIGKILL)
                os.waitpid(child_pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass

    @property
    def is_alive(self) -> bool:
        """True while the child process is still running."""
        return self._running

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    def _spawn(
        self, shell: str, cols: int, rows: int, env: dict[str, str],
        working_dir: Optional[str] = None,
    ) -> None:
        """Fork a child shell attached to a new PTY.

        Uses ``pty.fork()`` which calls openpty, fork, and setsid internally.
        The child exec's the shell with ``-l`` (login) so ~/.zshrc / ~/.bashrc
        are sourced correctly.
        """
        child_pid, master_fd = pty.fork()

        if child_pid == 0:
            # --- Child process ---
            # Change to requested working directory before exec
            if working_dir and os.path.isdir(working_dir):
                try:
                    os.chdir(working_dir)
                except OSError:
                    pass

            # Set initial window size before exec so the shell starts with
            # the correct dimensions.
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                # fd 1 = stdout, which is the slave PTY side in the child
                fcntl.ioctl(1, termios.TIOCSWINSZ, winsize)
            except OSError:
                pass

            # Replace process image with the user's shell (login mode).
            os.execvpe(shell, [shell, "-l"], env)
            # execvpe never returns on success; if it does, exit immediately.
            os._exit(1)

        # --- Parent process ---
        self._child_pid = child_pid
        self._master_fd = master_fd
        self._running = True

        # Set initial window size on the master side as well.
        self.resize(cols, rows)

        # Start the background read thread (daemon so it doesn't block app exit).
        self._read_thread = threading.Thread(
            target=self._read_loop,
            name=f"pty-read-{child_pid}",
            daemon=True,
        )
        self._read_thread.start()

    def _read_loop(self) -> None:
        """Background thread: read PTY output and deliver to on_output callback.

        Coalesces multiple ready chunks into a single callback invocation to
        reduce per-feed overhead (regex scans, NFC normalization, pyte parsing).
        Exits when the master fd is closed (OSError) or _running is False.
        """
        while self._running:
            fd = self._master_fd
            if fd is None:
                break
            try:
                data = os.read(fd, PTY_READ_CHUNK_SIZE)
                if not data:
                    break
                # Coalesce: drain any additional ready data without blocking
                while True:
                    r, _, _ = select.select([fd], [], [], 0)
                    if not r:
                        break
                    try:
                        more = os.read(fd, PTY_READ_CHUNK_SIZE)
                        if not more:
                            break
                        data += more
                    except (OSError, TypeError):
                        break
                self._on_output(data)
            except (OSError, TypeError):
                # fd closed (shutdown) or child exited — both are normal exits.
                break

        self._handle_child_exit()

    def _handle_child_exit(self) -> None:
        """Reap the child process and invoke the on_exit callback."""
        self._running = False
        exit_code = 0

        if self._child_pid is not None:
            try:
                _, status = os.waitpid(self._child_pid, os.WNOHANG)
                exit_code = os.waitstatus_to_exitcode(status) if status else 0
            except ChildProcessError:
                pass
            self._child_pid = None

        if self._on_exit is not None:
            try:
                self._on_exit(exit_code)
            except Exception:  # noqa: BLE001 — callbacks must not crash the thread
                pass
