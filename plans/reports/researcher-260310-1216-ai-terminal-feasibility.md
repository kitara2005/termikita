# Feasibility Report: AI-Aware Terminal Emulator in Python/PyObjC

**Date:** 2026-03-10
**Report ID:** researcher-260310-1216-ai-terminal-feasibility
**Scope:** Evaluating architectural feasibility of AI-aware features for Termikita
**Status:** Complete

---

## Executive Summary

**BRUTAL HONEST ASSESSMENT:**

Building an **AI-semantic-aware** terminal in Python/PyObjC is **fundamentally flawed by the wrong abstraction layer**. Claude Code outputs ANSI-formatted text — extracting semantic meaning requires implementing a full terminal emulator AND parsing opaque visual formatting. You'd be reverse-engineering formatting intended for humans.

**Better path:** Build an **excellent standard terminal** that Claude Code will render beautifully into. Termikita should focus on being **fast, responsive, and feature-complete** rather than trying to augment AI output it can't reliably understand.

**Verdict by Feature Group:**
- **Group A (Enhanced Core Terminal):** Feasible but high complexity in Python
- **Group B (AI Streaming Parser):** Possible but fragile; conflicts with ANSI rendering
- **Group C (Claude-Aware Features):** **NOT FEASIBLE** — needs structured data Claude doesn't expose
- **Group D (Developer UX):** Feasible; valuable without AI semantics

---

## Group A: Enhanced Core Terminal

### 1. GPU Text Rendering (Metal via PyObjC)

**Feasibility:** **MODERATE** — Technically possible, performance gains marginal

**Reality Check:**
- Metal **is** exposed via PyObjC (`pyobjc-framework-Metal`)
- Proof-of-concepts exist ([GitHub - jackcook/metallic](https://github.com/jackcook/metallic), [GPU from Python guide](https://alvinwan.com/how-to-use-apple-gpus-from-python/))
- **BUT:** Terminal text rendering does NOT benefit much from GPU acceleration
  - Glyph rendering bottleneck: Rasterizing glyphs to texture atlas (done once per font change)
  - Not per-frame work — already optimized
  - GPU shine in terminal comes from batched screen-to-GPU submission, not glyph compute

**Python/PyObjC specific issues:**
- PyObjC Metal bindings exist but are **thin wrappers**; you write C-like Metal shader code
- Shader compilation, texture management, buffer synchronization = 500+ lines of Objective-C/Metal
- **GIL (Global Interpreter Lock)** blocks simultaneous rendering & input processing unless you thread carefully
- Performance overhead of PyObjC <-> ObjC boundary calls can negate GPU gains if called per-frame

**Practical Recommendation:**
- **Start with CoreText + double buffering** — sufficient for 60 FPS on modern Macs
- Metal optimization **only if profiling shows CoreText is the bottleneck** (unlikely)
- Kitty achieves 400+ FPS with GPU; Alacritty achieves similar with Vulkan; you're targeting 60 FPS
- CoreText rendering is fast enough for that target

**Effort to implement GPU correctly:** 1–2 weeks (if you know Metal); 3–4 weeks learning curve

---

### 2. Glyph Atlas

**Feasibility:** **MODERATE** — Worth implementing, improves performance noticeably

**Reality Check:**
- Glyph atlas = texture containing pre-rasterized characters (A–Z, 0–9, symbols, emoji)
- Each render pass: Look up glyph in texture, copy to screen buffer
- **Benefit:** Cache hit on common chars (huge speedup vs re-rasterizing each frame)
- **Cost:** Memory for texture (2–10 MB), complexity managing fallback fonts

**Python performance:**
- Python can manage the atlas (dictionary of glyph→texture rect)
- **Bottleneck:** Rasterization itself (CoreText) — happens once at startup/font change
- Per-frame rendering (lookups + buffer copies) = **OK in Python** if batched efficiently
- Example: 80×24 terminal = 1,920 glyphs/frame. Python dict lookups are fast enough.

**Implementation Approach:**
1. At startup: Pre-rasterize common ASCII + emoji to CoreText bitmap
2. Store in NSImage or CTImage
3. Per frame: Render grid cells via CoreText → atlas lookup
4. Dynamic fallback: If char not in atlas, rasterize on-demand (slow path, cache result)

**Effort:** 3–5 days for basic atlas; +2 days for dynamic fallback

**Verdict:** **YES, worth doing.** Noticeable improvement, moderate complexity.

---

### 3. Ring Buffer Scrollback (Millions of Lines)

**Feasibility:** **HIGH** — Python handles this well; standard data structure

**Reality Check:**
- Ring buffer = circular array where old lines get overwritten
- 1,000 lines of 80 chars = ~80 KB
- 1 million lines = ~80 MB (acceptable)
- **Key advantage:** Fixed memory footprint; doesn't grow unbounded

**Python implementation:**
- Use `collections.deque(maxlen=1000000)` — **native, optimized**
- Or implement manual ring buffer with `array.array` (lower overhead)
- Memory efficient; no GC pressure with fixed size

**Critical considerations:**
1. **Scrollback search:** Searching 1M lines = **O(N) scan**, slow
   - Mitigation: Index by line number (metadata)
   - Search indexes (Whoosh, SQLite) overkill for terminal
   - **Practical:** 10k–100k line scrollback is sweet spot; 1M is aspirational

2. **Rendering performance:** Scrolling 1M line buffer doesn't redraw all lines
   - Terminal only renders visible 20–30 lines
   - Scrolling is **position update**, not full redraw
   - **OK in Python**

3. **Save/restore on quit:** 80 MB file write = **2–3 seconds**; acceptable

**Verdict:** **YES, feasible.** Python's `deque` is sufficient. Target 100k lines for MVP.

---

## Group B: AI Streaming Parser

### 1. Incremental Markdown Parser

**Feasibility:** **MODERATE** — Works, but conflicts with ANSI rendering

**Reality Check:**
- Tree-sitter Python bindings exist; fast, incremental parsing
- Can parse markdown progressively as chunks arrive
- **CRITICAL PROBLEM:** Claude Code doesn't send raw markdown
  - Claude Code uses **Ink** (React for CLI) → renders markdown to ANSI-formatted text
  - Terminal receives already-formatted output (colors, cursor moves, line breaks)
  - Parsing formatted output ≠ Parsing source

**Example mismatch:**
```
# Input to Claude Code's Ink renderer:
# Code Block
```python
print("hello")
```

# What terminal receives:
ESC[1m## Code BlockESC[0m
ESC[38;5;33mprintESC[0m(ESC[38;5;173m"hello"ESC[0m)
```

**Reversing this flow requires:**
1. Parse ANSI codes → extract text, colors, styles
2. Infer markdown from ANSI (e.g., bold + color = code?)
3. Rebuild semantic structure — **lossy, fragile**

**Python libraries:**
- `tree-sitter` — Fast, supports markdown; but needs raw markdown
- `stransi` — Parse ANSI codes into structured objects
- Combining them = **guessing** what markdown intent was

**Effort:** 2 weeks to implement; 8 weeks to make robust

**Verdict:** **NOT RECOMMENDED.** Architectural mismatch. Focus on rendering ANSI beautifully instead.

---

### 2. Detect Code Blocks, Diffs, Tables from Terminal Output

**Feasibility:** **LOW** — Possible via regex, but unreliable

**Reality Check:**
- **Code blocks** in Claude output: Wrapped in markdown code fence `` ``` `` or syntax-highlighted ANSI
  - But terminal receives only ANSI-formatted text; markdown fence already rendered as text
  - Regex can detect "text with monospace ANSI colors" = probably code
  - **Fragile:** False positives (regular colored output), false negatives (code without color)

- **Diffs** (`git diff` output): Red/green lines with context
  - **Works OK:** Regex for `^+` (green) / `^-` (red) lines is reliable
  - Already shown as text in Claude output
  - **But:** What to do with detected diffs? Collapsible sections need custom UI (not standard terminal)

- **Tables:** ASCII tables with `|` separators
  - Detectable via regex
  - Reliable because ASCII tables are regular
  - **But:** Terminal doesn't support "table widgets" — just rendering text

**Regex Approach:**
```python
# Detect code block (rough heuristic)
if all(line.startswith(ANSI_COLOR_CODE) for line in chunk):
    # Probably code

# Detect diff
if line.startswith(ANSI_RED) and line[0] == '-':
    # Deleted line
```

**Problems:**
1. **Performance:** Scanning every line = CPU overhead during streaming
2. **False positives:** Arbitrary colored output looks like code
3. **No semantic action:** Once detected, what then? Terminal doesn't have collapsible UI primitives
4. **Claude Code doesn't need it:** Already visually clear via syntax highlighting

**Effort:** 1–2 days for basic regex; much longer to make reliable

**Verdict:** **SKIP for MVP.** Regex detection is fragile; benefits unclear. Terminal rendering already makes structure visually obvious.

---

### 3. Syntax Highlighting in Terminal (tree-sitter, Pygments)

**Feasibility:** **MODERATE** — But conflicts with Claude's existing highlighting

**Reality Check:**
- Claude Code already applies syntax highlighting via ANSI codes
- Terminal receives `ESC[38;2;255;0;0mfunction_nameESC[0m` (already colored)
- Re-parsing and re-highlighting = **redundant**

**When might you use tree-sitter:**
1. User pastes raw code (unmarked) into terminal
2. User runs `cat file.py` → raw Python text
3. Terminal applies **additional** syntax highlighting

**Performance issues:**
- Tree-sitter parsing = **fast** (~1 ms for typical code snippet)
- But running per-frame on streaming output = **expensive**
  - Claude Code streams 100+ tokens/sec
  - 100 parse ops/sec × 1 ms = 10% CPU overhead
  - Acceptable, but visible overhead

**Python libraries:**
- `tree-sitter` — Fast, incremental, many languages
- `pygments` — Slower, but more mature
- **Recommendation:** Tree-sitter for performance

**Implementation:**
1. Detect code block (regex)
2. Parse with tree-sitter
3. Re-apply syntax highlighting colors (ANSI SGR codes)
4. **Render result** instead of original

**Conflict with Ink renderer:**
- Claude Code already highlighted the code
- Re-highlighting = **visual flicker** (colors change as tree-sitter parses)
- User sees color shift mid-render = **poor UX**

**Effort:** 1 week to implement basic version; 3 weeks to make robust

**Verdict:** **MAYBE for v2.0.** Useful for raw text (e.g., `cat file.py`), but unnecessary for Claude Code output. Don't prioritize.

---

## Group C: Claude-Aware Features

### **CRITICAL FINDING: This Entire Group is NOT FEASIBLE**

#### Why?

**Claude Code outputs ANSI-formatted text. It does NOT expose structured state.**

The terminal receives:
```
ESC[1mThinking...ESC[0m
⠋ Processing...
ESC[2K\rDone.
```

The terminal **cannot reliably detect:**
- Is Claude thinking or running a tool?
- Which files are being edited?
- How many tokens used?
- What's the task status?

All of this information is **baked into the visual output** (spinner, text position, colors). Extracting it requires:
1. Implementing a full terminal emulator
2. Simulating the rendering
3. Parsing the final visual state
4. Guessing the intent from pixels/characters

This is **fundamentally fragile**.

---

### 1. Claude State Detection (Thinking, Editing, Running)

**Feasibility:** **VERY LOW** — Requires reverse-engineering

**Approach:**
```python
# Heuristic: Detect "Thinking..." text
if "Thinking" in last_output and spinner_visible:
    claude_state = "thinking"
elif "Editing file" in output:
    claude_state = "editing"
elif "Running command" in output:
    claude_state = "running"
```

**Problems:**
1. **String matching is fragile**
   - Claude's output format may change
   - Localizable strings (e.g., non-English output) break detection
   - False positives from user's own text

2. **Timing is wrong**
   - State changes before text appears
   - By the time terminal sees "Thinking...", Claude already started
   - Detecting state end = even harder

3. **No canonical truth source**
   - Only Claude Code itself knows true state
   - Terminal is observing side effects, not state machine

**Effort:** 2 days to hack together; 4 weeks to make production-ready

**Verdict:** **NO.** Fragile heuristics. Not worth maintenance burden.

---

### 2. Task Tracker from AI Output

**Feasibility:** **VERY LOW** — Lossy parsing

**Approach:**
```
Claude output:
1. Create user schema
2. Add authentication
3. Deploy to prod

Heuristic: Parse as task list
```

**Problems:**
1. **Any numbered list looks like tasks**
   - User paste log files with line numbers
   - False positives everywhere

2. **Can't detect task completion**
   - "Completed task 1" = text, not state change
   - Terminal can't know if Claude actually completed it

3. **No semantic linkage**
   - Task 1 depends on task 2?
   - Terminal can only guess from text ordering

4. **Better alternative:** Claude Code CLI already shows this info in structured format
   - Users can read directly from CLI output
   - Terminal overlaying duplicate data = clutter

**Effort:** 3 days to implement; 2 weeks to debug false positives

**Verdict:** **NO.** Redundant with Claude Code's own output; fragile parsing. Skip.

---

### 3. Files Modified Tracker

**Feasibility:** **LOW** — Partial success possible

**Approach:**
```
Parse Claude output for patterns:
- "Creating file: /path/to/file"
- "Editing /path/to/file"
- "Deleted /path/to/file"
```

**Advantages:**
- Somewhat reliable (Claude Code uses consistent phrasing)
- Useful for UI (show file list in sidebar)
- Python regex can detect

**Disadvantages:**
1. **Format dependency**
   - If Claude Code changes output format, tracking breaks
   - No guarantee Claude Code exposes file paths in output

2. **Incomplete picture**
   - Claude Code may edit files but not mention in text
   - Terminal sees: "Modified files" but can't see actual changes

3. **Better alternative:** Monitor filesystem directly
   - Watch `~/.config/` and project directories
   - Detect changes via mtime/ctime
   - Doesn't depend on Claude Code output format

**Effort:** 3 days to implement; 2 weeks to handle edge cases

**Verdict:** **MAYBE for v2.0.** But filesystem watching is more reliable. Low priority.

---

### 4. AI Activity Timeline

**Feasibility:** **VERY LOW** — Impossible without structured data

**What you'd want:**
```
Timeline:
14:30 — Thinking started
14:35 — Tool call: read_file
14:37 — Thinking ended
14:38 — Tool call: bash_run
14:45 — Response complete
```

**Problems:**
1. **Terminal receives:** Already-formatted ANSI text
   - No timestamp metadata
   - No tool invocation records
   - No state transitions

2. **Reconstructing from text:** Unreliable
   - "Running tool: bash_run" = text occurrence
   - Can't match start/end times reliably
   - Parallelized tool calls = can't determine order

3. **Requires Claude Code API integration**
   - Not via terminal output, but via structured API
   - Outside scope of terminal emulator

**Effort:** 3 weeks to implement; likely won't work reliably

**Verdict:** **NO.** Needs structured data from Claude Code API, not terminal output. Out of scope.

---

### 5. Context Usage Monitor

**Feasibility:** **LOW** — Depends on Claude Code exposing this

**Approach:**
```
Parse Claude output for:
"Used 45,000 / 100,000 tokens"
```

**Reality:**
- Claude Code **does** show token usage in status line (visible in terminal)
- User can read it directly
- Terminal overlaying a widget = redundant

**If you wanted to extract/parse:**
- Regex to find usage line
- Parse numbers
- Display in custom widget

**Problems:**
1. **Format not guaranteed**
   - Claude Code may change token display format
   - No official spec for output format

2. **Redundant with UI**
   - Claude Code already shows this
   - Parsing + re-displaying = duplicate information

**Effort:** 1 day; relatively reliable

**Verdict:** **SKIP.** Redundant. Terminal already displays it. Focus on rendering beautifully instead.

---

## Group D: Developer UX

### 1. File Path Detection + Clickable Links

**Feasibility:** **HIGH** — Standard UX pattern

**Approach:**
1. Regex detect file paths: `/path/to/file`, `./src/main.py`, `~/Documents/file.txt`
2. Render as OSC 8 hyperlinks
3. Ctrl+Click or Cmd+Click opens in $EDITOR

**Benefits:**
- Useful for Claude Code output (often mentions file paths)
- Standard in modern terminals (iTerm2, Kitty, WezTerm)
- Not AI-specific; improves all terminal workflows

**Implementation:**
- Regex patterns for common path formats
- OSC 8 hyperlink protocol: `ESC]8;id;file://path\007text\007`
- Handle relative paths (resolve against CWD)

**Considerations:**
1. **False positives:** Arbitrary strings that look like paths
   - Mitigation: Only match known path patterns (starts with `/`, `./`, `~/`, or common prefixes)

2. **Performance:** Regex scanning every line
   - Feasible if batched (process after full output block)

3. **macOS integration:** Click handling
   - PyObjC NSTextView supports hyperlink detection
   - Custom handler to open file in default editor or user-chosen app

**Effort:** 4–5 days

**Verdict:** **YES, definitely implement.** High value, moderate effort, standard UX pattern.

---

### 2. Error/Stacktrace Detection

**Feasibility:** **MODERATE** — Partial success possible

**Approach:**
```python
# Detect common error patterns
patterns = [
    r"^(\w+Error|Exception|TypeError|ValueError|RuntimeError): (.+)$",  # Python
    r"^(\d+):(\d+): error: (.+)$",  # C/C++ compiler
    r"^  at .*\.js:(\d+):(\d+)$",  # JavaScript stack
    r"^Traceback \(most recent call last\):$",  # Python traceback start
]
```

**Benefits:**
- Highlight errors in red/color (already done by ANSI)
- Clickable line numbers → jump to file + line
- Group related error lines

**Considerations:**
1. **Many error formats**
   - Python, JavaScript, Java, Rust, Go, C/C++ all differ
   - Regex needs many patterns
   - Can't catch all

2. **False positives**
   - Regular user text can match error patterns
   - Mitigation: Only match known error prefixes

3. **Useful for:**
   - Build output (gcc errors)
   - Test results (pytest failures)
   - Runtime exceptions (Python tracebacks)

**Effort:** 4–7 days to cover major languages

**Verdict:** **YES, implement v1.1.** Lower priority than file links, but valuable. Regex-based heuristics acceptable.

---

### 3. Collapsible Sections

**Feasibility:** **LOW** — Requires custom UI, breaks terminal abstraction

**What you'd want:**
```
▼ Build Output (42 lines)
  > Warning: unused variable x
  > Error: missing return type

▼ Test Results (150 lines)
  > ✓ test_login
  > ✓ test_api
```

**Problems:**
1. **Terminal doesn't support this natively**
   - Terminal is flat text buffer
   - No interactive UI elements
   - Would need custom widget overlay (NSView)

2. **Breaks standard terminal workflows**
   - Copy/paste includes collapse controls (breaks copying)
   - Scrollback search can't find text in collapsed sections
   - Piping to file loses collapse state

3. **Alternative:** Use standard Unix pagers
   - `less` with `/pattern` search already collapses
   - Pipe output to `less` for navigation
   - Standard, portable, expected UX

4. **Only useful if:**
   - You store state (what's collapsed)
   - User wants persistent collapse (across sessions)
   - Significant output to collapse (>1000 lines typical)

**Effort:** 2 weeks (UI, state management, serialization)

**Verdict:** **NO for MVP.** Breaks terminal abstraction. Standard pagers (`less`) already do this better. Defer to v2.0 if users request.

---

### 4. Code Block Navigation

**Feasibility:** **MODERATE** — Without breaking terminal

**Approach:**
1. Detect code blocks (markdown fence `` ``` `` or syntax-highlighted ANSI text)
2. Add metadata markers (invisible ANSI sequences)
3. Keyboard shortcut: Jump next/prev code block

**Implementation:**
- Insert OSC markers around code blocks: `ESC]1234;code_block_start\007`
- Maintain internal index of blocks
- Cmd+J = next block, Cmd+Shift+J = prev block

**Benefits:**
- Useful for Claude Code output (lots of code blocks)
- Doesn't break standard terminal abstractions
- Copy/paste still works (markers are invisible)

**Considerations:**
1. **Marker format**
   - Choose unused OSC code (terminal won't break)
   - Make markers invisible to user

2. **Block detection**
   - Regex for markdown fences: `` ``` `` / `` ```language ``
   - ANSI color patterns for syntax-highlighted code
   - Can be fragile (color != always code)

3. **Navigation UX**
   - Scroll to block + highlight
   - Keyboard shortcuts (Cmd+J, Cmd+Shift+J)
   - Simple to implement

**Effort:** 5–7 days

**Verdict:** **MAYBE for v1.1.** Useful but not critical. Nice-to-have after file links and error detection.

---

## Performance Analysis: Python vs Native

### Rendering Pipeline Bottlenecks

| Component | Python/PyObjC | Native (Swift/ObjC) | Winner |
|-----------|---|---|---|
| PTY I/O (read bytes) | ~same | ~same | Tie |
| ANSI parsing | Acceptable | Faster | Native |
| Grid update (apply colors) | Acceptable | Faster | Native |
| Text layout (CoreText) | ~same | ~same | Tie |
| Glyph rendering | ~same | ~same | Tie |
| Screen compositing | Good (PyObjC FFI) | Faster | Native |
| **Overall:** | **60 FPS achievable** | **120+ FPS easy** | Native 2x faster |

**Python reality:**
- GIL blocks simultaneous I/O + rendering
- Workaround: Thread I/O on separate thread (releases GIL)
- ANSI parsing in Python = **acceptable** (pyte library is mature)
- CoreText calls via PyObjC = **thin wrappers**, near-native performance

**Practical outcome:**
- Python/PyObjC can achieve **60 FPS for typical terminal workload**
- Claude Code rendering is tolerable but not as smooth as native Kitty/Alacritty
- Startup time ~1–2 seconds (vs Terminal.app's instant, Alacritty's 50ms)

---

## Critical Design Flaw: ANSI Parsing Limit

### The Fundamental Problem

You cannot reliably **extract semantic meaning** from Claude Code's ANSI output because:

1. **ANSI is already rendered**
   - Claude Code generates markdown → renders to ANSI codes
   - Terminal receives pixels-equivalent text + colors
   - Reverse-engineering the markdown = lossy

2. **No metadata**
   - Claude Code state (thinking, editing, etc.) not exposed
   - Only visual representation available
   - Heuristics = fragile

3. **Not a terminal responsibility**
   - Terminal's job: Display text + colors
   - Semantic understanding: Claude Code's responsibility
   - Asking terminal to "understand AI" = scope creep

4. **Better path: Structured output**
   - Claude Code could output structured data (JSON, Protocol Buffers)
   - Terminal parses structured data → displays metadata
   - **But:** Claude Code doesn't do this (by design choice)
   - Terminal can't force this upstream

---

## Recommendation: MVP vs Never-Build

### MVP (v1.0) — IMPLEMENT

**Group A (Core Terminal):**
- ✅ VT100 ANSI parsing (use pyte)
- ✅ CoreText rendering (CPU-based, no Metal)
- ✅ Ring buffer scrollback (100k lines)
- ✅ Multi-tab support
- ✅ Theme system (JSON colors)
- ✅ Font selection + fallback chains

**Group D (Developer UX):**
- ✅ File path detection + OSC 8 links
- ✅ Copy/paste, search in scrollback

**Effort:** 12 days (matches original plan)

---

### v1.1 (Nice-to-Have) — CONSIDER

- ✅ Error/stacktrace highlighting + clickable lines
- ✅ Code block navigation (Cmd+J)
- ✅ Mouse support (SGR protocol)
- ✅ GPU acceleration (Metal) if profiling shows need

**Effort:** 5–7 days each feature

---

### NEVER-BUILD

**Group B (AI Streaming Parser):**
- ❌ Markdown parser (conflicts with ANSI rendering)
- ❌ Syntax highlighting via tree-sitter (redundant with Claude's highlighting)

**Group C (Claude-Aware Features):**
- ❌ **ALL of it**. Requires structured data Claude doesn't expose.

**Why:**
1. **Architectural mismatch:** Can't parse semantic meaning from visual output
2. **Maintenance burden:** Fragile heuristics will break on Claude updates
3. **Marginal value:** Benefits don't justify complexity
4. **Better alternative:** Be an excellent terminal that Claude renders into

---

## Risk Assessment

### High Risk (If Pursued)

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| ANSI parsing is fragile | HIGH | Breaking features on Claude updates | Don't do it |
| Python GIL blocks rendering | MEDIUM | Jank during heavy I/O | Thread I/O separately |
| Startup slowness (1–2s) | MEDIUM | Poor UX vs Terminal.app | Optimize imports, lazy-load |
| Metal GPU complexity | MEDIUM | 2+ weeks wasted | Start with CoreText only |

### Low Risk (Recommended Path)

- Standard terminal architecture = battle-tested
- ANSI parsing via pyte = mature library
- PyObjC + CoreText = industry standard (iTerm2 similar)
- No speculative AI semantics = fewer edge cases

---

## Token Efficiency & Conclusion

**Feasible Path:**
1. Build a **fast, responsive, feature-complete terminal** (Group A + core Group D)
2. **Skip speculative AI semantics** (Group B, C) — architectural mismatch
3. Claude Code will look beautiful in your terminal because you're a good terminal, not because you're "AI-aware"

**Effort Estimate:**
- MVP (Group A + core D): **12 days** ✅
- v1.1 (error detection, code nav): **10 days** ✅
- Never-build (Groups B + C): **5+ weeks wasted** ❌

**Bottom Line:**
You're not building an "AI terminal" — you're building a terminal that happens to run AI CLI tools beautifully. The distinction matters.

---

## Unresolved Questions

1. **Does Claude Code's output format change?** Regex-based detection depends on stable format
2. **Will Claude Code expose structured state in future?** Might enable better integration
3. **How much Python performance loss is acceptable?** (60 vs 120 FPS is perceptible to some users)
4. **Should Termikita prioritize cross-platform (Linux) in v1.0?** (Currently macOS-only)

---

## References

- [PyObjC Metal Framework](https://github.com/jackcook/metallic)
- [GPU Access from Python](https://alvinwan.com/how-to-use-apple-gpus-from-python/)
- [Tree-sitter Python Bindings](https://github.com/tree-sitter/py-tree-sitter)
- [ANSI Parsing with anstyle](https://deepwiki.com/rust-cli/anstyle/2.3-anstyle-parse:-ansi-escape-code-parsing)
- [Extracting Semantic Info from ANSI](https://jvns.ca/blog/2025/03/07/escape-code-standards/)
- [Claude Code Issue #5428 - ANSI Output Contamination](https://github.com/anthropics/claude-code/issues/5428)
- [Modern Terminals Comparison 2026](https://www.slashskill.com/best-terminal-emulators-for-developers/)

---

**Report Status:** Ready for planning integration
**Next Step:** Proceed with MVP (Group A + core D); skip Group B & C entirely
