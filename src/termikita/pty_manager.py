"""PTY (pseudo-terminal) lifecycle management for Termikita.

Handles spawning a shell process, bidirectional I/O via a background read thread,
window resize signals, and clean shutdown without zombie processes.
"""

import fcntl
import os
import pty
import signal
import struct
import termios
import threading
from typing import Callable, Optional

from termikita.constants import DEFAULT_COLORTERM, DEFAULT_TERM

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
    ) -> None:
        """Spawn the user's shell and start the background read thread.

        Args:
            cols: Initial terminal width in characters.
            rows: Initial terminal height in characters.
            on_output: Callback invoked with raw bytes from the child process.
            on_exit: Optional callback invoked with the exit code when the
                     child process terminates.
        """
        self._on_output = on_output
        self._on_exit = on_exit
        self._running = False
        self._master_fd: Optional[int] = None
        self._child_pid: Optional[int] = None
        self._read_thread: Optional[threading.Thread] = None

        self._spawn(get_user_shell(), cols, rows, _build_child_env())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Write raw bytes (user input) to the PTY master fd.

        No-op if the session is no longer alive.
        """
        if not self._running or self._master_fd is None:
            return
        try:
            os.write(self._master_fd, data)
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

        Safe to call multiple times.
        """
        if not self._running and self._master_fd is None:
            return

        self._running = False

        # Close fd first — causes the blocking os.read() in _read_loop to raise
        # OSError, which breaks the thread out of its loop cleanly.
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

        # Send SIGHUP (terminal hang-up) to the child shell.
        if self._child_pid is not None:
            try:
                os.kill(self._child_pid, signal.SIGHUP)
            except ProcessLookupError:
                pass  # Child already exited

            # Reap the child to avoid zombies; SIGKILL if it ignores SIGHUP.
            try:
                _, _ = os.waitpid(self._child_pid, 0)
            except ChildProcessError:
                pass
            self._child_pid = None

        # Wait for the read thread to finish (it will see _running=False + OSError).
        if self._read_thread is not None and self._read_thread.is_alive():
            self._read_thread.join(timeout=2.0)
            self._read_thread = None

    @property
    def is_alive(self) -> bool:
        """True while the child process is still running."""
        return self._running

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    def _spawn(self, shell: str, cols: int, rows: int, env: dict[str, str]) -> None:
        """Fork a child shell attached to a new PTY.

        Uses ``pty.fork()`` which calls openpty, fork, and setsid internally.
        The child exec's the shell with ``-l`` (login) so ~/.zshrc / ~/.bashrc
        are sourced correctly.
        """
        child_pid, master_fd = pty.fork()

        if child_pid == 0:
            # --- Child process ---
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

        Exits when the master fd is closed (OSError) or _running is False.
        """
        while self._running:
            try:
                data = os.read(self._master_fd, 4096)
                if not data:
                    break
                self._on_output(data)
            except OSError:
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
