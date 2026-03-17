"""Terminal session orchestrator — owns PTY + Buffer, dispatches I/O.

Ties PTYManager and BufferManager together. PTY output is fed into the
buffer on the PTY read thread; the main thread is notified via a dirty
flag polled by the view's 60 fps refresh timer (no cross-thread ObjC calls).
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from termikita.buffer_manager import BufferManager
from termikita.pty_manager import PTYManager
from termikita.constants import (
    DEFAULT_COLS,
    DEFAULT_ROWS,
    DEFAULT_SCROLLBACK,
)

# Silence threshold: output arriving after this many seconds of quiet
# suggests a command just finished (shell printed its prompt).
_SILENCE_THRESHOLD: float = 1.0
# Cooldown between activity notifications to avoid rapid repeated bounces.
_ACTIVITY_COOLDOWN: float = 3.0


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
        on_activity: Optional[Callable[[], None]] = None,
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
            on_activity: Optional callback invoked when a command likely finished
                (output after prolonged silence). Used for dock bounce / notification.
            working_dir: Optional starting directory for the shell process.
        """
        self.cols = cols
        self.rows = rows
        self._on_output = on_output_callback
        self._on_title_change = on_title_change
        self._on_exit_callback = on_exit
        self._on_activity = on_activity
        self._prev_title: str = ""
        # Track output timing for "command finished" heuristic
        self._last_output_time: float = 0.0
        self._last_notify_time: float = 0.0

        self.buffer = BufferManager(cols, rows, DEFAULT_SCROLLBACK, on_bell=on_activity)
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
        # Detect "output after silence" — a command likely just finished
        now = time.monotonic()
        if self._last_output_time > 0:
            silence = now - self._last_output_time
            if (
                silence > _SILENCE_THRESHOLD
                and now - self._last_notify_time > _ACTIVITY_COOLDOWN
                and self._on_activity is not None
            ):
                self._last_notify_time = now
                try:
                    self._on_activity()
                except Exception:
                    pass
        self._last_output_time = now

        # Track alternate screen state before feed — TUI apps (Claude Code,
        # vim, etc.) exit alternate screen (DECRST 1049) when they finish.
        # This is a reliable "command finished" signal even without a silence gap.
        was_alt = self.buffer._screen.in_alternate_screen
        self.buffer.feed(data)
        is_alt = self.buffer._screen.in_alternate_screen
        if (
            was_alt and not is_alt
            and self._on_activity is not None
            and now - self._last_notify_time > _ACTIVITY_COOLDOWN
        ):
            self._last_notify_time = now
            try:
                self._on_activity()
            except Exception:
                pass

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
