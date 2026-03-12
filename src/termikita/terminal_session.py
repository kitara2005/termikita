"""Terminal session orchestrator — owns PTY + Buffer, dispatches I/O.

Ties PTYManager and BufferManager together. PTY output is fed into the
buffer on the PTY read thread; the main thread is notified via a dirty
flag polled by the view's 60 fps refresh timer (no cross-thread ObjC calls).
"""

from __future__ import annotations

from typing import Callable, Optional

from termikita.buffer_manager import BufferManager
from termikita.pty_manager import PTYManager
from termikita.constants import (
    DEFAULT_COLS,
    DEFAULT_ROWS,
    DEFAULT_SCROLLBACK,
)


class TerminalSession:
    """Owns one PTY process and its associated screen buffer.

    Thread safety note:
        PTYManager's read thread calls _handle_pty_output which feeds bytes
        into BufferManager. BufferManager.feed() is not explicitly locked,
        but pyte's Screen mutations are fast and the main thread only reads
        (get_visible_lines, dirty flag). In practice this is safe for a
        single-producer / single-consumer pattern at terminal I/O rates.
        The refresh timer on the main thread polls buffer.dirty to trigger
        redraws — no cross-thread ObjC dispatch is needed.

    Usage::

        session = TerminalSession(80, 24, on_output_callback=view.setNeedsDisplay_)
        session.write(b"ls -la\\n")
        session.resize(120, 30)
        session.shutdown()
    """

    def __init__(
        self,
        cols: int = DEFAULT_COLS,
        rows: int = DEFAULT_ROWS,
        on_output_callback: Optional[Callable[[], None]] = None,
        on_title_change: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
        working_dir: Optional[str] = None,
    ) -> None:
        """Create buffer + PTY and start the shell.

        Args:
            cols: Initial terminal width in characters.
            rows: Initial terminal height in characters.
            on_output_callback: Called on the PTY read thread when new data
                arrives. Typically a no-op flag setter; the view's timer does
                the actual redraw check. Pass None to skip.
            on_title_change: Optional callback invoked when OSC 2 changes the
                window title (called from PTY thread — keep it lightweight).
            on_exit: Optional callback invoked with the shell exit code.
            working_dir: Optional starting directory for the shell process.
        """
        self.cols = cols
        self.rows = rows
        self._on_output = on_output_callback
        self._on_title_change = on_title_change
        self._on_exit_callback = on_exit
        self._prev_title: str = ""

        self.buffer = BufferManager(cols, rows, DEFAULT_SCROLLBACK)
        self.pty = PTYManager(
            cols,
            rows,
            on_output=self._handle_pty_output,
            on_exit=self._handle_pty_exit,
            working_dir=working_dir,
        )
        self.is_alive: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, data: bytes) -> None:
        """Send raw bytes to the PTY (user keystrokes / paste)."""
        self.pty.write(data)

    def resize(self, cols: int, rows: int) -> None:
        """Resize buffer grid immediately, PTY (SIGWINCH) deferred by caller."""
        self.cols = cols
        self.rows = rows
        self.buffer.resize(cols, rows)

    def resize_pty(self, cols: int, rows: int) -> None:
        """Send SIGWINCH to the child process. Call after resize settles."""
        self.pty.resize(cols, rows)

    def shutdown(self) -> None:
        """Kill the PTY and mark session inactive. Safe to call multiple times."""
        self.is_alive = False
        self.pty.shutdown()

    @property
    def title(self) -> str:
        """Current window title from OSC 2 sequences (or "Termikita")."""
        return self.buffer.title

    # ------------------------------------------------------------------
    # Private callbacks (invoked from PTY read thread)
    # ------------------------------------------------------------------

    def _handle_pty_output(self, data: bytes) -> None:
        """Feed raw PTY bytes into the buffer.

        Called on the PTY read thread. Feeds buffer (fast), then invokes the
        output callback (if any). The view's refresh timer on the main thread
        will detect buffer.dirty and call setNeedsDisplay_ — no ObjC cross-
        thread dispatch required.
        """
        self.buffer.feed(data)

        # Notify title change if OSC 2 updated the screen title
        if self._on_title_change is not None:
            new_title = self.buffer.title
            if new_title != self._prev_title:
                self._prev_title = new_title
                try:
                    self._on_title_change(new_title)
                except Exception:
                    pass

        # Optional output callback (e.g. a lightweight flag setter)
        if self._on_output is not None:
            try:
                self._on_output()
            except Exception:
                pass

    def _handle_pty_exit(self, exit_code: int) -> None:
        """Invoked by PTYManager when the child process exits."""
        self.is_alive = False
        if self._on_exit_callback is not None:
            try:
                self._on_exit_callback(exit_code)
            except Exception:
                pass
