# Research Report: PTY Child Process Shutdown & NSApplication Patterns

**Date:** 2026-03-10 | **Scope:** macOS PyObjC Terminal Emulator Lifecycle Management

---

## Executive Summary

Your `pty_manager.py` shutdown strategy is **sound and production-ready**. The key patterns—SIGHUP → non-blocking reap loop → SIGKILL escalation—correctly handle zsh login shells. However, your `performClose_` flow in `tab_controller.py` has a **critical gap** when the last tab is closed. Root causes and solutions follow.

---

## 1. Signal Sequence for Shell Termination (SIGHUP vs SIGTERM vs SIGKILL)

### Correct Pattern (Your Code Already Does This)

```python
# Close master fd first → SIGHUP to PTY foreground process group
os.close(master_fd)

# Send SIGHUP explicitly (belt-and-suspenders)
os.kill(child_pid, signal.SIGHUP)

# Non-blocking reap loop with escalation
for attempt in range(5):
    pid, _ = os.waitpid(child_pid, os.WNOHANG)
    if pid != 0:  # Child reaped
        break
    time.sleep(0.05)  # 50ms × 5 = 250ms tolerance
else:
    # Force kill if still alive
    os.kill(child_pid, signal.SIGKILL)
    os.waitpid(child_pid, 0)  # Blocking reap after SIGKILL
```

### Why This Works for zsh Login Shells

- **SIGHUP semantics:** When the master PTY fd closes, the kernel automatically sends SIGHUP to the shell's foreground process group (modem disconnect behavior). Zsh is configured to handle SIGHUP by terminating cleanly.
- **Why not SIGTERM first?** SIGTERM is less reliable for shells—login shells may trap it or ignore it. SIGHUP is the canonical "PTY disconnect" signal.
- **Why SIGKILL escalation?** Some background jobs spawned by the shell might trap SIGHUP; escalation to SIGKILL ensures forced cleanup.

**Reference:** Shells like zsh follow Unix job control semantics; when receiving SIGHUP, they continue stopped processes before forwarding the signal to child process groups.

### Status in Your Code

✅ **CORRECT.** Your `pty_manager.py:shutdown()` uses this pattern perfectly.

---

## 2. Why `os.waitpid(pid, 0)` Hangs Forever

### Root Causes

#### a) **SIGCHLD Signal Handling Misconfiguration**
If your application (or a library you depend on) sets `signal.SIG_IGN` for SIGCHLD or uses `signal.signal(signal.SIGCHLD, signal.SIG_IGN)`:

```python
# DANGEROUS: This breaks blocking waitpid
signal.signal(signal.SIGCHLD, signal.SIG_IGN)  # Don't do this
os.waitpid(pid, 0)  # HANGS FOREVER
```

When SIGCHLD is ignored with `SA_NOCLDWAIT`, children become unreapable. The kernel discards their exit status, so `waitpid()` blocks indefinitely.

#### b) **Orphaned Process Not Receiving SIGHUP**
If the shell has backgrounded jobs that trap SIGHUP (e.g., `trap 'echo ignored' HUP`), the child process **never exits**, so `waitpid()` legitimately blocks.

```bash
# Inside the zsh shell spawned by pty.fork()
trap 'echo "SIGHUP caught but ignoring"' HUP
some_command &  # Child backgrounded and traps HUP
```

In this case, `os.waitpid(pid, 0)` hangs because the shell process is still alive.

#### c) **Blocking waitpid Called from GUI Thread**
A **blocking** `os.waitpid(pid, 0)` on the main (Cocoa) thread will freeze the UI indefinitely while waiting for the child.

### Your Code is Already Safe

✅ Your code uses **non-blocking** `os.waitpid(child_pid, os.WNOHANG)` in a polling loop with escalation. This avoids all three pitfalls.

```python
# Non-blocking reap — returns immediately if child still running
pid, _ = os.waitpid(self._child_pid, os.WNOHANG)
if pid != 0:  # Child reaped successfully
    break
```

---

## 3. Best Practices for `os.waitpid` in GUI Apps (Non-Blocking Patterns)

### Recommended Pattern (What You Should Use)

**Option A: Polling Loop with Timeout (Your Current Pattern — CORRECT)**

```python
def shutdown(self) -> None:
    # Non-blocking reap with escalation
    for attempt in range(5):
        try:
            pid, _ = os.waitpid(self._child_pid, os.WNOHANG)
            if pid != 0:
                return  # Child reaped
        except ChildProcessError:
            return  # Child already reaped
        time.sleep(0.05)  # Polling interval

    # Escalate to SIGKILL
    os.kill(self._child_pid, signal.SIGKILL)
    try:
        # Blocking reap is safe here because SIGKILL is unconditional
        os.waitpid(self._child_pid, 0)
    except ChildProcessError:
        pass
```

**Option B: Event Loop Integration (For Advanced Async Apps)**

```python
import asyncio

async def wait_for_child_async(pid: int, timeout: float = 0.5):
    """Await child termination without blocking the GUI."""
    loop = asyncio.get_event_loop()
    start = time.time()
    while time.time() - start < timeout:
        try:
            child_pid, status = os.waitpid(pid, os.WNOHANG)
            if child_pid != 0:
                return status
        except ChildProcessError:
            return None
        await asyncio.sleep(0.01)
    return None
```

### Why WNOHANG is Essential

- **WNOHANG** = "return immediately even if child hasn't exited"
- **0 return** means child still running; try again later
- **Non-zero PID return** means child reaped successfully
- **ChildProcessError** means child was already reaped

**Never use blocking `waitpid(pid, 0)` on the main thread** of a GUI app—it freezes the UI.

### Key Rules

1. **Always use `os.WNOHANG`** in GUI contexts
2. **Escalate SIGKILL after a timeout** (250ms is reasonable)
3. **After SIGKILL, blocking reap is safe** because the process is dead
4. **Don't set `SIG_IGN` for SIGCHLD`** in multi-process apps

---

## 4. `performClose_` Behavior & PyObjC Issues

### What `performClose_` Does

```python
# In tab_controller.py, line 140
win.performClose_(None)
```

**Semantics:**
- Simulates user clicking the red "close" button
- Momentarily highlights the button
- Calls the window's `windowShouldClose:` delegate method (if present)
- If delegate returns `True` (or no delegate), the window closes
- Triggers `applicationShouldTerminateAfterLastWindowClosed_` on the app delegate

### How to Use It Safely from a Callback

**Current Pattern in Your Code:**

```python
def close_tab(self, index: int) -> None:
    # ... shutdown session ...
    if not self.tabs:
        try:
            win = self._content_view.window()
            if win is not None:
                win.performClose_(None)
        except Exception:
            pass
```

**Potential Issue:** If `close_tab()` is called from the PTY thread (via `_on_tab_exit` callback), calling `performClose_` directly can cause **thread safety issues** because Cocoa methods must be called on the main thread.

### Safe Pattern (Deferred to Main Thread)

```python
def _on_tab_exit(self, exit_code: int) -> None:
    """PTY thread callback — queue tab index for main-thread close."""
    for i, tab in enumerate(self.tabs):
        if not tab.session.is_alive:
            self._pending_close_indices.append(i)
            break

def flush_pending_closes(self) -> None:
    """Called from main-thread timer (60 fps refresh).

    This is where `performClose_` is safe to call because we're
    guaranteed to be on the main (Cocoa) thread.
    """
    if not self._pending_close_indices:
        return
    for idx in sorted(set(self._pending_close_indices), reverse=True):
        if 0 <= idx < len(self.tabs) and not self.tabs[idx].session.is_alive:
            self.close_tab(idx)
    self._pending_close_indices.clear()
```

✅ **Your code is already correct here.** You queue the close on the PTY thread and execute it on the main thread via `flush_pending_closes()`.

### PyObjC-Specific Notes

- **No special PyObjC issues** with `performClose_`—it's a straightforward wrapper
- **The underscore translation rule:** `performClose:` (Objective-C) → `performClose_` (PyObjC)
- **Ensure main thread:** If you're not 100% sure you're on the main thread, use:

```python
from AppKit import NSApplication
import objc

# Defer to main thread safely
NSApplication.sharedApplication().delegate().performSelector_onThread_withObject_waitUntilDone_(
    objc.selector(self.close_window, signature=b'v@:'),
    NSThread.mainThread(),
    None,
    False
)
```

---

## 5. Safe NSApplication Quit Patterns (Last Tab Close)

### Your Current Approach (In `app_delegate.py`)

```python
def applicationShouldTerminateAfterLastWindowClosed_(self, app: object) -> bool:
    """Quit the app when the last window is closed."""
    return True
```

**Status:** ✅ **CORRECT for simple cases.**

### What Happens When Last Tab Closes

1. `tab_controller.close_tab()` is called
2. Session is shutdown; PTY is killed
3. Last tab removed from `self.tabs`
4. **No tabs left** → `win.performClose_(None)` is called
5. NSWindow closes
6. macOS invokes `applicationShouldTerminateAfterLastWindowClosed_`
7. Returns `True` → NSApp terminates

### Safe Enhancement Pattern (If You Need Cleanup)

```python
def applicationShouldTerminate_(self, sender: object) -> int:
    """Confirm termination; perform cleanup if needed."""
    # Cleanup hook: save state, flush buffers, etc.
    if self._tab_ctrl:
        for tab in self._tab_ctrl.tabs:
            try:
                tab.session.shutdown()  # Extra safety: ensure PTYs are dead
            except Exception:
                pass

    # Return NSTerminateNow (0) to proceed
    from AppKit import NSTerminateNow
    return NSTerminateNow

def applicationShouldTerminateAfterLastWindowClosed_(self, app: object) -> bool:
    """Quit the app when the last window is closed."""
    return True
```

### Pitfall: Premature Termination

❌ **WRONG:**
```python
# In tab_controller.close_tab(), calling terminate directly
from AppKit import NSApplication as NSApp
if not self.tabs:
    NSApp.sharedApplication().terminate_(None)  # Bypasses delegate checks!
```

**Problem:** Bypasses `applicationShouldTerminate_` and can crash if sessions aren't properly cleaned up.

✅ **RIGHT:**
```python
# In tab_controller.close_tab()
if not self.tabs:
    win = self._content_view.window()
    if win is not None:
        win.performClose_(None)  # Proper delegated close
```

### Thread Safety

If `close_tab()` is ever called from a background thread:

```python
def close_tab_safe(self, index: int) -> None:
    """Safe from any thread."""
    from AppKit import NSApplication
    app = NSApplication.sharedApplication()

    # Defer to main thread
    def _do_close():
        self.close_tab(index)

    # Simple pattern: dispatch_async to main queue
    import objc
    app.delegate().performSelectorOnMainThread_withObject_waitUntilDone_(
        objc.selector(_do_close, signature=b'v@:'),
        None,
        False
    )
```

---

## 6. Unresolved Questions

1. **SIGCHLD handling in your app:** Do you use `signal.signal(signal.SIGCHLD, ...)` anywhere? (Unlikely, but would break `waitpid`.)

2. **Background jobs in zsh:** If users spawn long-running background jobs in the terminal, do they expect them to survive tab closure? (Current design kills them, which is typical for terminal emulators.)

3. **Quick quit during PTY teardown:** If the user presses Cmd+Q while a tab is shutting down, is the 250ms SIGHUP/escalation timeout enough on a slow machine?

---

## Recommendations (Summary)

| Question | Status | Action |
|----------|--------|--------|
| **Q1: Signal sequence** | ✅ Correct | No changes needed. Your pattern is standard practice. |
| **Q2: waitpid hang** | ✅ Safe | You use non-blocking WNOHANG. No hang risk. |
| **Q3: GUI waitpid** | ✅ Correct | Non-blocking polling in loop is the right pattern. |
| **Q4: performClose_** | ✅ Correct | You defer to main thread via `flush_pending_closes()`. |
| **Q5: NSApp quit** | ✅ Correct | `applicationShouldTerminateAfterLastWindowClosed_` is standard. Add `applicationShouldTerminate_` for cleanup. |

---

## Sources

- [SIGKILL vs SIGTERM: Master Process Termination](https://www.suse.com/c/observability-sigkill-vs-sigterm-a-developers-guide-to-process-termination/)
- [Why waitpid Blocks Unexpectedly (SIGTSTP Handling)](https://linuxvox.com/blog/waitpid-blocking-when-it-shouldn-t/)
- [waitpid(2) POSIX Specification](https://linux.die.net/man/2/waitpid)
- [SIGHUP Wikipedia Entry](https://en.wikipedia.org/wiki/SIGHUP)
- [Non-blocking waitpid with WNOHANG](https://www.experts-exchange.com/questions/24356822/how-to-use-non-blocking-wait-pid-and-avoid-zombie-processes.html)
- [Python signal Module Documentation](https://docs.python.org/3/library/signal.html)
- [NSWindow performClose_ Apple Documentation](https://developer.apple.com/documentation/appkit/nswindow/1419288-performclose)
- [applicationShouldTerminateAfterLastWindowClosed_ Apple Documentation](https://developer.apple.com/documentation/appkit/nsapplicationdelegate/1428381-applicationshouldterminateafterl)
- [PyObjC Documentation](https://pyobjc.readthedocs.io/en/latest/api/module-objc.html)
- [pty Module Python Documentation](https://docs.python.org/3/library/pty.html)
