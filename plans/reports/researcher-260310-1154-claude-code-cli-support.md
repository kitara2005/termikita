# Research Report: Claude Code CLI Terminal Requirements

**Date:** 2026-03-10
**Report ID:** researcher-260310-1154-claude-code-cli-support
**Status:** Complete

## Executive Summary

Claude Code CLI is a production-grade AI coding assistant running in the terminal. It requires robust terminal emulator support for **ANSI escape sequences, streaming output handling, Unicode/emoji support, and interactive prompts**. The tool does NOT use alternate screen buffer mode—instead relies on native terminal rendering with differential updates to reduce flickering. Termikita must support xterm-compatible escape sequences at minimum.

---

## 1. Terminal Capabilities Required

### 1.1 ANSI Escape Sequence Support (CRITICAL)

Claude Code depends heavily on ANSI escape codes for:

| Capability | Escape Sequence | Usage | Status |
|------------|-----------------|-------|--------|
| **Cursor Movement** | CSI (ESC[) positioning like ESC[10;20H | Interactive cursor control, input positioning | **Required** |
| **SGR Color (Foreground/Background)** | SGR codes 30-37, 90-97 (16-color palette) | Status line, syntax highlighting hints | **Required** |
| **256-Color Mode** | SGR codes 38;5;N, 48;5;N | Rich terminal output | **Required** |
| **24-bit Truecolor (RGB)** | SGR codes 38;2;R;G;B, 48;2;R;G;B | Syntax highlighting in code output | **Required** |
| **Text Styling** | SGR codes: 1 (bold), 3 (italic), 4 (underline), 9 (strikethrough) | UI emphasis, diff display | **Required** |
| **Cursor Visibility** | ESC[?25h (show), ESC[?25l (hide) | Spinner/progress indicators | **Required** |
| **Erase in Display** | ESC[2J, ESC[3J (clear screen) | Screen management | **Required** |
| **Erase in Line** | ESC[K, ESC[2K (clear line) | Line-by-line rendering updates | **Required** |
| **Alternate Screen Buffer** | ESC[?1049h/l | **NOT used** (by design choice) | Not needed |

**Known Issues:** ANSI 24-bit true color sequences are sometimes stripped from bash command output. The terminal must preserve these codes during output capture.

### 1.2 Synchronized Output (DEC Mode 2026)

Claude Code team is working upstream to add synchronized output support to eliminate flickering during rapid redraws. This is NOT currently required but represents next-gen optimization.

### 1.3 Unicode and Wide Character Support

| Feature | Requirement | Impact |
|---------|-------------|--------|
| **Unicode Version** | 12.1.0+ recommended, 15.0.0+ ideal | Emoji rendering, CJK characters |
| **Wide Character Handling** | Proper cell width calculation | Spinners, progress indicators, emoji in UI |
| **UTF-8 Encoding** | Full support required | All text input/output |
| **Emoji Rendering** | Should render as 2-cell width in color | Status indicators, visual feedback |

**Known Issues:** Some terminals (xterm.js-based) only support Unicode 12.1.0, causing glyph rendering issues. Symbol fonts (fonts-symbola) may be needed for some emoji.

### 1.4 Keyboard Input Handling

- **Standard Keys:** Arrow keys, Enter, Tab, Backspace, Delete
- **Ctrl Combinations:** Ctrl+C (cancel), Ctrl+D (exit), Ctrl+G (edit in external editor), Ctrl+U (exit bash mode), Ctrl+B (background command)
- **Vi Mode:** Optional but supported for text editing (configurable via `/vim`)
- **History Navigation:** Arrow keys in empty/partial input navigate command history

**Known Issues:** Focus reporting escape sequences ([I and [O) from mouse/modifier keys can leak into input stream in some terminals (e.g., WezTerm).

### 1.5 Mouse Support

- Optional but not currently critical to core functionality
- If implemented, should not interfere with text selection or copy/paste

---

## 2. Streaming Output Performance

### 2.1 Rendering Architecture

Claude Code uses a **differential renderer** with native terminal updates:

```
Input from Claude → Token streaming
    ↓
Real-time incremental rendering
    ↓
Differential update (only changed lines)
    ↓
Terminal ANSI codes written to stdout
```

**Key Points:**
- NOT using alternate screen buffer (deliberate design choice to preserve native terminal UX)
- Renders dozens of times per second during streaming
- Must handle 4,000-6,700 scroll events/sec in multiplexers (tmux/smux)
- Bash command output is buffered (not streaming)—only final result shown

### 2.2 Performance Targets

**Acceptable Rendering:**
- Flicker reduced by ~85% with recent rendering rewrite
- Scrolling/rendering should handle typical token rates (100s of tokens/sec)
- Screen resize (SIGWINCH) must be handled without glitches

**Known Bottleneck:** Terminal multiplexers (tmux) receive excessive scroll events, causing jitter. Optimization targets <100 scrolls/sec for better performance.

### 2.3 Terminal Buffer Requirements

- **Scrollback Buffer:** Large buffer recommended (1,000+ lines)
- **After Extended Use:** Degradation observed in tmux after accumulating thousands of lines
- **Memory:** Must handle long-running sessions (hours)

---

## 3. Interactive Prompts & User Input

Claude Code supports several interactive prompt types:

| Prompt Type | Terminal Requirement | Details |
|-------------|---------------------|---------|
| **Yes/No Prompts** | Standard input/output | Binary choice with timeout |
| **Multi-select** | Cursor movement, styled output | Select multiple items with arrow keys |
| **Text Input** | Full TTY control | Single/multi-line input with history |
| **Streaming Responses** | Non-blocking output | Show progress while waiting for API response |
| **External Editor** | Shell integration (Ctrl+G) | Launch $EDITOR for complex input |

**Terminal Detection:** Ink framework detects `stdout.isTTY` and `CI` environment variables to determine interactivity level.

---

## 4. TERM Variable & Color Support Detection

### 4.1 Recommended TERM Values

**Primary:** `xterm-256color`
**Secondary:** `xterm-truecolor`, `screen-256color`
**Fallback:** `xterm`

### 4.2 Color Capability Detection

```bash
# 256-color detection
if [[ "$TERM" == *"256color" ]]; then
  # Use SGR 38;5;N codes
fi

# Truecolor detection
if [[ "$COLORTERM" == "truecolor" ]] || [[ "$COLORTERM" == "24bit" ]]; then
  # Use SGR 38;2;R;G;B codes
fi
```

**For Termikita:** Advertise `TERM=xterm-256color` at minimum; support `COLORTERM=truecolor` if 24-bit capable.

---

## 5. Specific Features & Escape Sequences Used

### 5.1 Status Line / Header

Claude Code displays a dynamic status line showing:
- Session name with animated spinner during thinking
- Cost information (real-time session costs)
- Mode indicators (bash, vim, etc.)

**Escape Codes Used:**
- Cursor positioning: `ESC[H` (home), `ESC[nG` (column), `ESC[nA/B/C/D` (movement)
- Line clearing: `ESC[K` (clear to end of line)
- SGR styles: bold (`ESC[1m`), color (`ESC[38;5;Nm`)

**Issue:** Spinner animation character width varies, causing terminal tab flicker. Solution: Use fixed-width characters.

### 5.2 Diff Display

When showing code changes:
- Green + lines: `ESC[32m` (SGR green)
- Red - lines: `ESC[31m` (SGR red)
- Context gray: `ESC[90m` (bright black)
- Must preserve context around changes

### 5.3 Progress/Thinking Indicator

Animated ASCII spinner using characters like `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (braille pattern) or similar non-emoji sequence.

**Requirements:**
- Smooth animation without flicker
- Width consistency to avoid tab resizing

---

## 6. Known Terminal Issues with Claude Code

### 6.1 ANSI Color Rendering Issues

**Issue #16790:** True color (24-bit) escape sequences not rendered in bash tool output
- **Root Cause:** SGR codes stripped during output capture
- **Impact:** Syntax highlighting lost in command results
- **Workaround:** Ensure terminal preserves escape codes during piping

**Issue #29706:** Color rendering bugs in certain terminal configurations
- **Impact:** Statusline colors may not appear correctly
- **Mitigation:** Test with xterm-256color, verify SGR support

### 6.2 ANSI Escape Sequence Contamination

**Issue #5428:** PowerLevel10k shell theme injects ANSI codes that interfere with Claude Code parsing
- **Root Cause:** Instant prompt redirects stdin/stdout and pollutes environment
- **Solution:** Use simpler shell prompts or disable instant prompt

**Issue #6635:** Statusline ANSI escape codes not rendering with Unicode terminals
- **Impact:** Raw escape codes visible instead of colors
- **Mitigation:** Ensure proper TERM/COLORTERM variables set

### 6.3 Focus Reporting & Mouse Events (Issue #10375)

**Issue:** Focus reporting sequences `[I` and `[O` leak into input stream
- **Terminals Affected:** WezTerm, possibly others with mouse/modifier support
- **Impact:** Garbled input, parsing failures
- **Mitigation:** Disable focus reporting or filter at terminal level

### 6.4 Scrollback Buffer Performance (Issue #4851)

**Issue:** Excessive lag in tmux after extended use (thousands of lines)
- **Root Cause:** Terminal redrawing entire scrollback buffer
- **Impact:** Sluggish rendering, high CPU
- **Mitigation:** Use terminal with efficient scrollback handling; consider clearing history periodically

### 6.5 Scroll Event Flooding (Issue #9935)

**Issue:** 4,000-6,700 scroll events/sec in tmux causes flickering
- **Root Cause:** Differential renderer sends many updates
- **Mitigation:** Implementation of batched/coalesced scroll events needed

---

## 7. Design Decisions & Tradeoffs

### 7.1 Native Terminal vs. Alternate Screen Buffer

**Decision:** Claude Code uses **native terminal rendering** (not alternate screen buffer)

**Why:**
- Preserves Cmd+F search capability
- Native copy/paste functionality
- Natural scrollback navigation
- Consistent with Unix philosophy

**Tradeoffs:**
- More complex rendering logic (cleared ~85% flicker with recent rewrite)
- Must carefully manage cursor position and screen state
- Differential updates required instead of full rewrites

**Future:** Anthropic may explore alternate screen buffer in future but bar is high.

### 7.2 Streaming vs. Buffering

**Current State:**
- Claude Code responses stream to terminal
- Bash command output is buffered (spinner shown, result at end)

**Rationale:** Bash output buffering prevents interleaving of stderr/stdout; terminal cleanup easier with full output.

### 7.3 Rendering Framework

Claude Code originally used Ink (React for CLI) but rewrote from scratch for better control:
- Ink uses synchronous rendering model
- Claude Code needed fine-grained incremental updates
- React components still used for logic; custom renderer for terminal

---

## 8. Recommendations for Termikita

### 8.1 Required Capabilities (MVP)

```text
✓ ANSI escape sequence support (CSI basics)
✓ SGR color codes (16-color, 256-color)
✓ Cursor positioning & line operations
✓ UTF-8 text input/output
✓ Detect TERM environment variable
✓ TTY detection (isatty)
✓ Keyboard input handling
✓ Standard control flow (Ctrl+C, Ctrl+D)
```

### 8.2 Recommended Enhancements (v1+)

```text
~ 24-bit true color support (SGR 38;2;R;G;B)
~ COLORTERM=truecolor advertisement
~ Unicode 15.0.0+ character support
~ Emoji rendering (2-cell width)
~ Mouse support (optional but clean)
~ Synchronized output (DEC 2026) support
```

### 8.3 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Streaming token display | <10ms latency | Real-time feel |
| Screen redraws/sec | 30-60 FPS | Smooth animations |
| Scroll batching | <100 events/sec | Avoid multiplexer jitter |
| Unicode width calculation | <1ms | Cursor positioning accuracy |

### 8.4 TERM Advertisement

```bash
# Termikita should set/suggest
TERM=xterm-256color        # Minimum
COLORTERM=truecolor        # If 24-bit capable
LANG=en_US.UTF-8           # Or locale-appropriate
```

### 8.5 Testing Checklist

```markdown
- [ ] Colored output renders correctly (16-color, 256-color, 24-bit)
- [ ] Spinners animate without flicker
- [ ] Diff display shows colors correctly
- [ ] Unicode characters (emoji, CJK) display with correct width
- [ ] Copy/paste works in native terminal
- [ ] Cmd+F search works
- [ ] Ctrl+C stops running command
- [ ] Large outputs (>10,000 lines) don't cause lag
- [ ] Terminal resize (SIGWINCH) handled smoothly
- [ ] Multi-line input works correctly
- [ ] Command history navigation (arrow keys) works
```

---

## 9. Security & Stability Considerations

### 9.1 ANSI Injection Risks

- Bash output may contain malicious ANSI codes
- Claude Code should escape or sanitize SGR sequences from untrusted sources
- Cursor positioning codes should be handled carefully

### 9.2 Large Output Handling

- Streaming thousands of lines should not cause memory bloat
- Terminal should handle rapid output without data loss
- Flushing/syncing output critical during long operations

### 9.3 Interactive Mode Security

- Input validation critical for tool invocation (Bash, Read, etc.)
- Terminal must not allow code injection via ANSI sequences
- Focus reporting must not corrupt input state

---

## 10. References & Sources

1. [Claude Code Overview - Official Docs](https://code.claude.com/docs/en/overview)
2. [Claude Code GitHub Repository](https://github.com/anthropics/claude-code)
3. [Ink - React for CLI](https://github.com/vadimdemedes/ink)
4. [ANSI Escape Code Reference](https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797)
5. [Claude Code GitHub Issue #16790 - Truecolor Support](https://github.com/anthropics/claude-code/issues/16790)
6. [Claude Code GitHub Issue #5428 - PowerLevel10k Interference](https://github.com/anthropics/claude-code/issues/5428)
7. [Claude Code GitHub Issue #9935 - Scroll Event Flooding](https://github.com/anthropics/claude-code/issues/9935)
8. [Claude Code GitHub Issue #10375 - Focus Reporting](https://github.com/anthropics/claude-code/issues/10375)
9. [TERM Variable & Color Detection Guide](https://marvinh.dev/blog/terminal-colors/)
10. [Threads Post - Terminal Rendering Rewrite](https://www.threads.com/@boris_cherny/post/DSZbZatiIvJ/)
11. [Claude Code Terminal Configuration Guide](https://code.claude.com/docs/en/terminal-config)
12. [Reverse Engineering Claude's ASCII Spinner](https://medium.com/@kyletmartinez/reverse-engineering-claudes-ascii-spinner-animation-eec2804626e0)

---

## Unresolved Questions

1. **Exact rendering algorithm:** Details of differential renderer not publicly available. Reverse-engineering may be needed.
2. **Synchronized output adoption timeline:** When will DEC 2026 synchronized output be required?
3. **Bash streaming output:** Will Claude Code support true streaming (token-by-token) bash output in future?
4. **Alternate screen buffer:** Under what conditions might Claude Code switch to alternate screen mode?
5. **Terminal multiplexer optimization:** Will Claude Code implement smarter batching for tmux/screen?
6. **Markdown rendering in CLI:** Will Claude Code add native markdown rendering to terminal output?

---

**Report Status:** Ready for implementation planning
**Next Steps:** Use findings for Termikita terminal emulator development
