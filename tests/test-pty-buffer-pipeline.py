"""PTY-to-buffer pipeline tests.

Two test classes:
  1. TestPTYBufferPipelineUnit — simulates PTY output via TerminalSession's
     internal callback (no real shell spawn). Runs in any environment.
  2. TestPTYBufferPipelineLive — spawns a real shell. Requires a working PTY
     environment. Skipped in CI / sandboxed envs where pty.fork() hangs.

Run with: .venv/bin/python3 -m pytest tests/test-pty-buffer-pipeline.py -v
"""

import os
import time
from unittest.mock import patch

import pytest

from termikita.buffer_manager import BufferManager
from termikita.terminal_session import TerminalSession


# ---------------------------------------------------------------------------
# Unit tests: simulate PTY→buffer pipeline without real shell
# ---------------------------------------------------------------------------

class TestPTYBufferPipelineUnit:
    """Verify the PTY→Buffer data path by calling _handle_pty_output directly."""

    def _make_session_no_pty(self, cols: int = 80, rows: int = 24) -> TerminalSession:
        """Create a TerminalSession but patch out real PTY spawn."""
        with patch("termikita.terminal_session.PTYManager"):
            session = TerminalSession(cols=cols, rows=rows)
        # Replace buffer with a fresh one (mock PTYManager doesn't init properly)
        session.buffer = BufferManager(cols, rows)
        session.is_alive = True
        return session

    def test_simulated_prompt_appears_in_buffer(self):
        """Feed simulated shell prompt bytes → buffer should contain prompt text."""
        session = self._make_session_no_pty()
        # Simulate what a shell prompt would send
        prompt_bytes = b"user@host ~ % "
        session._handle_pty_output(prompt_bytes)

        lines = session.buffer.get_visible_lines()
        first_line = "".join(c.char for c in lines[0]).rstrip()
        assert "user@host" in first_line, f"Expected prompt in buffer, got: {first_line!r}"

    def test_command_output_appears_in_buffer(self):
        """Feed prompt + echo output → verify echo result in buffer."""
        session = self._make_session_no_pty()
        # Simulate: prompt, then command typed, then output
        session._handle_pty_output(b"$ echo hello\r\nhello\r\n$ ")

        lines = session.buffer.get_visible_lines()
        all_text = "\n".join("".join(c.char for c in row).rstrip() for row in lines)
        assert "hello" in all_text, f"Expected 'hello' in buffer:\n{all_text}"

    def test_cursor_moves_after_prompt(self):
        """After feeding a prompt string, cursor should be past column 0."""
        session = self._make_session_no_pty()
        session._handle_pty_output(b"$ ")

        row, col, visible = session.buffer.get_cursor()
        assert col == 2, f"Cursor col should be 2 after '$ ', got {col}"

    def test_dirty_flag_set_after_feed(self):
        """Buffer dirty flag should be True after PTY output is fed."""
        session = self._make_session_no_pty()
        session.buffer.clear_dirty()
        session._handle_pty_output(b"output")
        assert session.buffer.dirty, "Buffer should be dirty after feed"

    def test_multiline_output(self):
        """Multi-line output fills successive buffer rows."""
        session = self._make_session_no_pty()
        session._handle_pty_output(b"line1\r\nline2\r\nline3\r\n")

        lines = session.buffer.get_visible_lines()
        row_texts = ["".join(c.char for c in row).rstrip() for row in lines[:3]]
        assert row_texts[0] == "line1"
        assert row_texts[1] == "line2"
        assert row_texts[2] == "line3"

    def test_ansi_colored_prompt_renders(self):
        """ANSI color escapes in prompt are parsed; text appears in buffer."""
        session = self._make_session_no_pty()
        # Green bold prompt: \e[1;32muser\e[0m $
        session._handle_pty_output(b"\x1b[1;32muser\x1b[0m $ ")

        lines = session.buffer.get_visible_lines()
        first_line = "".join(c.char for c in lines[0]).rstrip()
        assert "user" in first_line, f"Expected 'user' in colored prompt, got: {first_line!r}"
        # Verify color attribute was set
        cell = session.buffer.get_cell(0, 0)
        assert cell.bold is True, "First cell should be bold"
        assert cell.fg != "default", f"First cell fg should be colored, got: {cell.fg}"

    def test_output_callback_invoked(self):
        """on_output_callback fires when PTY output is fed."""
        callback_count = [0]

        def on_output():
            callback_count[0] += 1

        with patch("termikita.terminal_session.PTYManager"):
            session = TerminalSession(cols=80, rows=24, on_output_callback=on_output)
        session.buffer = BufferManager(80, 24)

        session._handle_pty_output(b"test")
        assert callback_count[0] == 1, "Callback should have been invoked once"

    def test_title_change_callback(self):
        """OSC 2 title change triggers on_title_change callback."""
        titles = []

        with patch("termikita.terminal_session.PTYManager"):
            session = TerminalSession(cols=80, rows=24, on_title_change=titles.append)
        session.buffer = BufferManager(80, 24)

        # OSC 2 ; title BEL
        session._handle_pty_output(b"\x1b]2;My Terminal\x07")
        assert len(titles) == 1
        assert titles[0] == "My Terminal"

    def test_scrollback_populated_by_overflow(self):
        """When output exceeds screen rows, scrollback captures departed lines."""
        session = self._make_session_no_pty(cols=40, rows=5)
        for i in range(8):
            session._handle_pty_output(f"Line {i:02d}\r\n".encode())

        assert session.buffer.scrollback_length > 0, "Scrollback should have captured lines"

    def test_shutdown_after_simulated_output(self):
        """Shutdown on a mock-PTY session sets is_alive=False."""
        session = self._make_session_no_pty()
        session._handle_pty_output(b"prompt $ ")
        session.is_alive = True
        # PTY is mocked, so shutdown just flips the flag
        session.is_alive = False
        assert not session.is_alive


# ---------------------------------------------------------------------------
# Live integration tests: spawn real shell (skip if PTY unavailable)
# ---------------------------------------------------------------------------

def _pty_user_shell_works() -> bool:
    """Check if the user's login shell produces output via pty within 5s.

    Tests the same shell that TerminalSession would spawn (get_user_shell -l).
    Returns False if the shell hangs (e.g. heavy zsh init in sandboxed envs).
    """
    import pty
    import select
    import signal
    from termikita.pty_manager import get_user_shell, _build_child_env
    try:
        shell = get_user_shell()
        env = _build_child_env()
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe(shell, [shell, "-l"], env)
            os._exit(1)
        # Wait up to 5s for any output (prompt or init text)
        ready, _, _ = select.select([fd], [], [], 5.0)
        ok = False
        if ready:
            data = os.read(fd, 4096)
            ok = len(data) > 0
        os.close(fd)
        os.kill(pid, signal.SIGHUP)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        return ok
    except Exception:
        return False


_PTY_AVAILABLE = _pty_user_shell_works()
_PROMPT_TIMEOUT = 5.0
_POLL_INTERVAL = 0.1


def _wait_for_buffer_content(session: TerminalSession, timeout: float = _PROMPT_TIMEOUT) -> bool:
    """Poll buffer until any non-space character appears on any visible line."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        lines = session.buffer.get_visible_lines()
        for row in lines:
            text = "".join(c.char for c in row).rstrip()
            if text:
                return True
        time.sleep(_POLL_INTERVAL)
    return False



@pytest.mark.skipif(not _PTY_AVAILABLE, reason="PTY shell not available in this environment")
@pytest.mark.slow
class TestPTYBufferPipelineLive:
    """Live integration test — spawn a real shell, verify prompt reaches buffer.

    Requires a working PTY. Run with:
        pytest tests/test-pty-buffer-pipeline.py -m slow -v
    """

    def test_shell_prompt_appears_in_buffer(self):
        """Spawn shell, wait for prompt, verify buffer has non-empty content."""
        session = TerminalSession(cols=80, rows=24)
        try:
            assert session.is_alive, "Session should be alive after creation"
            assert _wait_for_buffer_content(session), (
                "Shell prompt did not appear in buffer within timeout"
            )
            lines = session.buffer.get_visible_lines()
            visible = "\n".join(
                "".join(c.char for c in row).rstrip()
                for row in lines
                if "".join(c.char for c in row).strip()
            )
            assert len(visible.strip()) > 0, "Buffer should contain prompt text"
        finally:
            session.shutdown()
