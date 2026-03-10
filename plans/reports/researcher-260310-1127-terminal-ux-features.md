# Terminal Emulator UX Features Research Report

**Date:** 2026-03-10
**Researcher:** Claude (Agent)
**Focus:** Essential UX patterns for modern macOS terminal emulator

---

## Executive Summary

Modern terminal emulators balance **functional minimalism** with **polished interactions**. Success hinges on fast startup, responsive rendering, sensible defaults, and deep Unix tool integration. This report synthesizes patterns from leading terminals: iTerm2 (macOS standard), Warp (modern cloud-native), Kitty (high-performance), Alacritty (GPU-accelerated), and Terminal.app (baseline).

---

## 1. Must-Have Use Cases

### 1.1 Shell Interaction (Critical)
**Supported shells:** bash, zsh, fish, tcsh, ksh
**Requirements:**
- Proper shell auto-detection from system login shell
- Support for shell configuration files (.bashrc, .zshrc, .config/fish)
- Preserve shell state across splits/tabs
- Signal handling: SIGCHLD, SIGWINCH for resize, SIGTERM for graceful shutdown
- PTY (pseudo-terminal) management per tab/split — each gets own PTY file descriptor
- Environment variable passing (TERM, COLORTERM=truecolor, LANG, LC_*)
- Job control: Ctrl+C (SIGINT), Ctrl+Z (SIGTSTP), fg/bg commands

**Implementation detail:** Use `forkpty()` or `posix_openpt()` to spawn each shell in isolated TTY. macOS libc provides robust PTY handling via `<util.h>` openpty/forkpty.

### 1.2 SSH Connections (High Priority)
**Requirements:**
- Shell into SSH seamlessly (spawn login shell via `ssh user@host`)
- Character encoding: UTF-8, preserve SSH session state
- Terminal type negotiation: Send correct TERM value (xterm-256color default)
- Agent support: SSH_AUTH_SOCK passthrough for key management
- Local/remote key binding distinction (Cmd key locally, Alt/Meta remotely)
- Keep-alive: Prevent idle session timeouts (SSH ServerAliveInterval config)
- Mouse support passthrough (SGR mouse protocol, xterm mouse protocol)

**Observation:** Warp, iTerm2 both excel here — they wrap SSH seamlessly, inherit shell config, support password/key auth. Kitty's SSH integration less polished.

### 1.3 CLI Tools Integration (Core)
**Essential tools:** git, docker, npm, python, rust (cargo), brew, aws-cli, kubectl

**Requirements:**
- ANSI color output (16-color + 256-color + 24-bit/true-color)
- Proper exit code handling (used by shells for conditional logic)
- Pipes and redirects fully functional (>, >>, |, <)
- TTY detection: `isatty(1)` must return true for color output
- Signal delivery: Ctrl+C kills running process, not terminal
- Subprocess output capture: Tools like `jq`, `grep`, `awk` work correctly
- Unicode support: Emoji, CJK characters, ligatures in output

**Testing approach:** Run `git status`, `docker ps`, `npm list` — verify colors render, output aligns correctly.

### 1.4 Text Editing in Terminal (Important)
**Editors:** vim, nano, emacs, helix

**Requirements:**
- Mouse support: Click to position cursor (SGR 1006 or xterm protocol)
- Mode switching: Vi normal/insert modes render correctly
- Alternate screen buffer: Editors use `smcup`/`rmcup` sequences to preserve scrollback
- Status line: Bottom bar stays visible during editing
- Scrolling during edit mode preserved
- Background colors, bold, underline, reverse video rendering

**Critical:** Terminal must handle ESC sequences for cursor positioning (ANSI cursor movement codes). Vim/nano use these extensively.

### 1.5 File Management (Baseline)
**Commands:** `ls`, `cd`, `cp`, `mv`, `rm`, `find`, `tree`

**Requirements:**
- `ls --color` output renders properly (ANSI color codes)
- File icons optional but nice-to-have (macOS integration)
- Wide character support for file names (Unicode)
- Tab completion working (shell dependency, but terminal mustn't interfere)

### 1.6 Process Management (Important)
**Commands:** `ps`, `top`, `htop`, `kill`, `jobs`, `fg`, `bg`

**Requirements:**
- Live screen updates: `top` and `htop` use alternate screen buffer + cursor positioning
- Real-time rendering: No flickering on refresh (use double buffering)
- Color support for process status (running, sleeping, zombie)
- CPU/memory monitoring tools require responsive scrollback

### 1.7 Scrollback Buffer & History (Critical)
**Requirements:**
- Configurable scrollback lines: 1000–10,000 typical (user preference)
- Search function: Cmd+F to find text in scrollback (regex or literal)
- Copy/paste from scrollback without affecting clipboard
- Performance: Scrolling 10k lines shouldn't stutter
- Memory efficient: Ring buffer or file-based scrollback for >100k lines
- Clear screen doesn't lose scrollback (Cmd+K clears visible, scrollback intact)
- Selection modes: Line, word, block (rectangular)

**UX detail:** iTerm2 allows dragging to select, middle-click to paste (macOS convention). Most terminals support Shift+Click to extend selection.

---

## 2. Multi-Tab UX Patterns

### 2.1 Tab Bar Design

**Location:** Top of terminal window (macOS standard), below menu bar

**Visual elements:**
- Tab title: Shows directory or custom title (set via `echo -ne "\033]0;Title\007"`)
- Activity indicator: Dot or small animation when output received in non-active tab
- Close button (x) on hover or visible always (preference)
- New tab button (+) at end of tab bar
- Tab separators (hairline dividers)

**Styling:**
- Background: Match theme (light/dark)
- Text: Contrasting color for readability
- Active tab: Brighter or different background, bold text
- Inactive tab: Dimmed
- Hover effect: Slight color shift

### 2.2 Tab Keyboard Navigation

**Standard shortcuts (macOS/iTerm2 compatible):**
- `Cmd+T` — New tab (in current window)
- `Cmd+W` — Close current tab
- `Cmd+N` — New window
- `Cmd+Shift+W` — Close window
- `Cmd+Option+Right/Left` — Next/Previous tab (fast switching)
- `Cmd+1` through `Cmd+9` — Jump to tab 1–9
- `Cmd+0` — Jump to last tab
- `Ctrl+Tab` / `Ctrl+Shift+Tab` — Cycle next/previous (less common on macOS)
- `Cmd+L` — Clear screen (shell-agnostic)
- `Cmd+K` — Clear scrollback and visible screen

**Note:** `Cmd+Option+Right` is powerful for power users, avoids "tab switcher" modal.

### 2.3 Tab Context Menu

**Right-click on tab shows:**
- Edit Title…
- Rename… (edit current tab title)
- Clone Tab (duplicate session with same directory/shell)
- Close Tab
- Move Tab to New Window (iTerm2 feature)

### 2.4 Tab Title Management

**Auto-title sources (in priority order):**
1. Manual title (user set via escape sequence)
2. Current directory (if `PS1` or shell prompt doesn't set title)
3. Executable name (current running process)
4. Fallback: "Terminal" or "Bash"

**Implementation:** Monitor process changes via `/proc` (Linux) or `libproc` (macOS). iTerm2 uses dynamic process monitoring.

### 2.5 Tab Restoration

**Session persistence (optional but valuable):**
- Save tab directory, shell history, environment on quit
- Restore on reopen
- Warp and iTerm2 support this; most terminals don't

**Consideration:** Adds complexity, risk of stale state. YAGNI suggests starting without this.

---

## 3. Theme System Design

### 3.1 Color Model Hierarchy

Terminals support three color depth modes:

**16-color (basic ANSI):**
- 8 standard colors (black, red, green, yellow, blue, magenta, cyan, white)
- 8 bright variants
- Used by: `ls`, simple CLI output
- Lowest common denominator

**256-color (xterm-256):**
- 16 basic colors (above)
- 216 RGB colors (6×6×6 cube)
- 24 grayscale colors
- Default for modern terminals, set TERM=xterm-256color
- Used by: vim, syntax highlighting, most modern CLI tools

**24-bit true color (TrueColor / RGB):**
- 16.7M colors (8 bits each: R, G, B)
- Set TERM=xterm-truecolor or screen-256color-bce
- Used by: Modern CLI tools, Neovim, modern IDEs in terminal
- Warp, iTerm2, Kitty all support this

**Color selection logic:**
```
if COLORTERM=truecolor:
    use 24-bit colors
elif TERM contains "256color":
    use 256-color palette
else:
    use 16-color ANSI
```

### 3.2 Theme File Format

**No universal standard. Popular formats:**

**JSON (modern, easy to parse):**
```json
{
  "name": "Dracula",
  "background": "#282a36",
  "foreground": "#f8f8f2",
  "cursor": "#f8f8f2",
  "cursorAccent": "#282a36",
  "selection": "#44475a",
  "colors": [
    "#000000",  // black
    "#ff5555",  // red
    "#50fa7b",  // green
    "#f1fa8c",  // yellow
    "#bd93f9",  // blue
    "#ff79c6",  // magenta
    "#8be9fd",  // cyan
    "#bfbfbf",  // white
    "#4d4d4d",  // bright black
    "#ff6e6e",  // bright red
    "#69ff94",  // bright green
    "#ffffa5",  // bright yellow
    "#d6acff",  // bright blue
    "#ff92df",  // bright magenta
    "#a4ffff",  // bright cyan
    "#ffffff"   // bright white
  ]
}
```

**TOML (used by Kitty, Alacritty):**
```toml
[colors]
primary = { background = "#282a36", foreground = "#f8f8f2" }
cursor = { text = "#282a36", cursor = "#f8f8f2" }
normal = [
  "#000000", "#ff5555", "#50fa7b", "#f1fa8c",
  "#bd93f9", "#ff79c6", "#8be9fd", "#bfbfbf"
]
bright = [
  "#4d4d4d", "#ff6e6e", "#69ff94", "#ffffa5",
  "#d6acff", "#ff92df", "#a4ffff", "#ffffff"
]
```

**Recommendation for this project:** JSON + TOML both viable. JSON is simpler to parse, TOML more human-friendly. Start with JSON.

### 3.3 Essential Theme Attributes

**Minimal theme requires:**
1. `background` — Main terminal background (hex #RRGGBB)
2. `foreground` — Default text color
3. `cursor` — Cursor color
4. `selection` — Selected text background
5. `colors[0-15]` — ANSI color palette (16 colors)

**Nice-to-have attributes:**
- `cursorAccent` — Color when cursor is blinking (optional, defaults to foreground)
- `boldText` — Separate bright color for bold text (optional)
- `dimText` — Dimmed text color
- `tab.background` / `tab.foreground` — Tab bar colors
- `scrollbar.background` / `scrollbar.thumb` — Scrollbar colors (if present)

**Bold handling:** Two approaches:
1. Use brighter variant of normal colors (most common)
2. Use `colors[8-15]` (bright variants) when bold flag set
3. Some terminals support both

### 3.4 Popular Terminal Themes

**Well-designed themes to study:**
- Dracula — Dark, purple accent, widely available
- Gruvbox — Warm browns, excellent contrast
- Nord — Cool blues/grays, professional
- Solarized Dark/Light — Optimized for human eyes, by Ethan Schoonover
- Monokai — Dark background, colorful syntax
- Catppuccin — Vibrant pastels, modern aesthetic
- One Dark — Clean, dark background with pops of color

**Characteristic:** All use hex colors, clear contrast ratios (WCAG AA minimum 4.5:1), consistent hue families.

### 3.5 Theme Storage & Discovery

**Location:** `~/.config/terminal-emulator/themes/` or `~/.terminal-emulator/themes/`

**Format:**
```
~/.config/terminal-emulator/themes/
├── dracula.json
├── gruvbox.json
├── nord.json
└── user-custom.json
```

**Discovery mechanism:**
- Scan themes directory at startup
- Allow user to select via preferences UI
- Store selection in config file (JSON/TOML)
- Hot-reload: Changing theme applies immediately (nice-to-have)

---

## 4. Font Handling

### 4.1 Monospace Requirement

**Why monospace mandatory:**
- Each character occupies same width (important for alignment)
- ASCII art, tables, code formatting depends on fixed width
- Terminal rendering assumes monospace (each char = 1 width unit)
- Using proportional fonts breaks all alignment

**Test:** Run `echo "iii|||"` — characters must align vertically.

### 4.2 Font Fallback Chain

**Challenge:** Single font doesn't cover all Unicode (emoji, CJK, symbols)

**Solution: Fallback chain**
```
Primary: JetBrains Mono (covers Latin, symbols)
  ↓ (glyph not found)
Fallback 1: Noto Sans Mono CJK (covers CJK, Japanese, Chinese)
  ↓ (glyph not found)
Fallback 2: Apple Color Emoji (emoji support)
  ↓ (glyph not found)
Fallback 3: Menlo (macOS system monospace)
```

**Implementation:** Use CoreText on macOS — specify font cascade fallback list. This is non-trivial; requires native font APIs.

**Popular fallback chains:**
- JetBrains Mono → Noto Sans Mono CJK → Apple Color Emoji
- Fira Code → DejaVu Sans Mono → Emoji One Color
- SF Mono (macOS) → Noto Sans CJK → Apple Color Emoji

### 4.3 Popular Terminal Fonts

| Font | Characteristics | Ligatures | CJK Support | Free |
|------|-----------------|-----------|------------|------|
| **JetBrains Mono** | Modern, clean, excellent hinting | Yes | No (get CJK fallback) | Yes |
| **Fira Code** | Distinctive, good ligatures | Yes | No | Yes |
| **Cascadia Code** | Microsoft modern, monospace | Yes | No | Yes |
| **SF Mono** | macOS native, clean | No | No | Bundled with macOS |
| **Hack** | Simple, readable, excellent for accessibility | No | No | Yes |
| **Menlo** | macOS classic, safe default | No | No | Bundled with macOS |
| **Inconsolata** | Geometric, minimalist | No | No | Yes |
| **DejaVu Sans Mono** | Excellent Unicode coverage | No | Partial | Yes |
| **IBM Plex Mono** | IBM's monospace, professional | No | Yes (partial) | Yes |
| **Noto Sans Mono** | Google's monospace, extensive Unicode | No | Yes | Yes |

**Recommendation:** Default to SF Mono (macOS built-in), offer JetBrains Mono or Fira Code as suggested upgrades.

### 4.4 Ligature Support

**What are ligatures?**
Stylistic replacements for character sequences:
- `->` → (single glyph)
- `=>` ⇒ (single glyph)
- `::` ∷ (single glyph)
- `!=` ≠ (single glyph)

**Pros:** Aesthetically pleasing, improves readability in code
**Cons:** Can confuse in terminal (not standard), adds rendering complexity

**Decision:** Optional feature, toggle in preferences. Not critical for MVP (YAGNI).

**Fonts with good ligature support:** JetBrains Mono, Fira Code, Cascadia Code, Hack.

### 4.5 Font Metrics Configuration

**User-configurable:**
- Font family (dropdown or text field)
- Font size (points, 8–32 typical range; default 12pt)
- Line height (multiplier: 1.0, 1.2, 1.5; affects vertical spacing)
- Letter spacing (optional, typically 0)

**Storage:** Save in config file as:
```json
{
  "font": {
    "family": "SF Mono",
    "size": 12,
    "lineHeight": 1.2,
    "letterSpacing": 0
  }
}
```

**Rendering note:** Line height multiplier directly affects vertical glyph spacing. 1.0 = tight, 1.5 = spacious. Default ~1.2 for comfort.

---

## 5. Keyboard Shortcuts

### 5.1 Core macOS Terminal Conventions

| Shortcut | Action | Note |
|----------|--------|------|
| `Cmd+T` | New tab | Standard macOS (Safari, Chrome, etc.) |
| `Cmd+W` | Close tab | macOS standard |
| `Cmd+N` | New window | macOS standard |
| `Cmd+Shift+W` | Close window | macOS standard |
| `Cmd+,` | Preferences | macOS standard |
| `Cmd+Q` | Quit | macOS standard |
| `Cmd+H` | Hide | macOS standard |
| `Cmd+M` | Minimize | macOS standard |
| `Cmd+Option+Esc` | Force Quit | macOS standard (external) |

### 5.2 Tab Navigation

| Shortcut | Action | Rationale |
|----------|--------|-----------|
| `Cmd+Option+Right` | Next tab | Fast switching for power users |
| `Cmd+Option+Left` | Previous tab | Mirrors right navigation |
| `Cmd+1` through `Cmd+9` | Jump to tab N | Vim-like, fast direct access |
| `Cmd+0` | Jump to last tab | Convenience |
| `Cmd+{` / `Cmd+}` | Prev/Next tab | Vim alternative |

**Design note:** Avoid `Ctrl+Tab` (less macOS-native), prefer `Cmd+Option+Right/Left`.

### 5.3 Text Selection & Editing

| Shortcut | Action | Terminal-specific |
|----------|--------|-------------------|
| `Cmd+A` | Select all | Selects visible text, not input |
| `Cmd+C` | Copy | Copy selected text (if any) or Ctrl+C (interrupt) if no selection |
| `Cmd+V` | Paste | Paste from clipboard |
| `Cmd+Z` | Undo | *Not recommended* — conflicts with shell suspend (Ctrl+Z) |
| `Option+Up/Down` | Scroll up/down | Alternative to scrollbar |
| `Fn+Up/Down` | Page up/down | Alternative scroll (if no fn key, use Shift+PgUp/PgDn) |
| `Cmd+Home/End` | Jump to top/bottom | Scroll to start/end of buffer |

**Design consideration:** `Cmd+C` must intelligently detect: if text selected, copy it; if no selection, send Ctrl+C to shell. Warp does this well.

### 5.4 Search & Navigation

| Shortcut | Action | Behavior |
|----------|--------|----------|
| `Cmd+F` | Find in scrollback | Opens search bar, highlights matches |
| `Enter` / `Escape` | Next match / Close search | Standard find dialog |
| `Cmd+G` / `Cmd+Shift+G` | Next/Previous match | Standard macOS find |

### 5.5 Window & Screen Management

| Shortcut | Action | Note |
|----------|--------|------|
| `Cmd+Shift+D` | Split pane vertically (optional) | iTerm2 feature, nice-to-have |
| `Cmd+D` | Split pane horizontally (optional) | iTerm2 feature, nice-to-have |
| `Cmd+Option+Up/Down/Left/Right` | Navigate splits (optional) | iTerm2 feature, nice-to-have |
| `Cmd+;` | Save/name window (optional) | iTerm2 feature |
| `Cmd+K` | Clear screen | Standard, clears only visible terminal |
| `Cmd+Shift+K` or `Cmd+L` | Clear scrollback | Clears both visible and history |

**Priority:** Core shortcuts (Cmd+T/W/N/Q) are essential. Split panes = nice-to-have for MVP.

### 5.6 Shell-level Shortcuts (Not Terminal Control)

**These are sent to shell, not handled by terminal:**
- `Ctrl+C` — SIGINT (interrupt process)
- `Ctrl+Z` — SIGTSTP (suspend process)
- `Ctrl+D` — EOF (end of input)
- `Ctrl+A` — Start of line (readline)
- `Ctrl+E` — End of line (readline)
- `Ctrl+R` — Reverse history search (bash/zsh)
- `Ctrl+L` — Clear screen (shell command, not terminal)

**Important:** Terminal must NOT intercept these; pass them through to shell.

---

## 6. Minimal but Polished UI

### 6.1 What Makes a Terminal Feel "Lightweight"

**Principles:**
1. **Startup time < 500ms** — User tolerance threshold
2. **Instant responsiveness** — No lag on keystroke
3. **Memory footprint < 50MB** — Idle terminal with one tab
4. **Minimal visual chrome** — No unnecessary UI elements
5. **Sensible defaults** — Works well out of the box
6. **No animations** — Except optional subtle transitions

**Benchmarks (reference):**
- Terminal.app: ~30MB, instant
- iTerm2: ~50-80MB, 200-300ms startup
- Warp: ~100-150MB (Rust + features)
- Kitty: ~20-30MB, instant (GPU-accelerated)
- Alacritty: ~10-15MB, instant (GPU-accelerated)

### 6.2 Rendering Performance

**Bottleneck:** Terminal output rendering (text + colors)

**Optimization strategies:**

**1. GPU acceleration (modern approach)**
- Use Metal (macOS), Vulkan (Linux), DirectX (Windows)
- Render glyphs to texture atlas once, reuse
- Update only changed cells (dirty rectangle optimization)
- Kitty, Alacritty use this approach

**2. CPU-based rendering (simpler, slower)**
- Draw each character using CoreGraphics/Quartz (macOS)
- Redraw entire screen on update (or dirty regions)
- Acceptable for most use cases if optimized
- Terminal.app, iTerm2 do this (with optimizations)

**3. Double buffering (essential)**
- Render to off-screen buffer
- Swap buffers atomically
- Prevents flicker on fast output (e.g., `tree -f /large/dir`)

**Result:** Scrolling should feel smooth even at 10k+ line scrollback.

### 6.3 Visual Design Philosophy

**Minimal UI elements:**
```
┌─────────────────────────────────────┐
│ [+] Tab 1   Tab 2   Tab 3      [─][⬜][⬛] │  ← Tab bar, window controls
├─────────────────────────────────────┤
│                                     │
│  $ ls -la                           │  ← Terminal content
│  total 42                           │     (no padding, full width)
│  drwxr-xr-x  5 user staff   160 ... │
│                                     │
└─────────────────────────────────────┘
```

**Key principles:**
- **Tab bar:** Minimal design, white/dark background matching theme
- **No status bar:** Keep bottom clean (use tab title for status)
- **No menu bar in full-screen:** Activate on Fn key or gesture
- **Scrollbar (optional):** Show only on hover, thin (8-10px), non-intrusive
- **No toolbar:** Preferences accessed via Cmd+, or menu

### 6.4 UI Polish Touches

**Subtle enhancements (not bloat):**

1. **Activity indicator** — Small dot on tab when output received
   - Visual feedback that background tab has new content
   - Crucial for multitasking (watching build logs in tab 2 while working in tab 1)

2. **Tab title context** — Show directory or SSH host
   - User sets via prompt: `echo -ne "\033]0;Directory: ~/Code\007"`
   - Or auto-detect from PWD if shell supports it

3. **Font anti-aliasing** — Use subpixel rendering on LCD displays (Quartz default)
   - Makes text sharp and readable

4. **Cursor styles:**
   - Block (default)
   - Underline
   - Beam (vertical line)
   - User-configurable, application can request via ESC sequences

5. **Cursor blinking (optional)** — Configurable, default off (reduces distraction)

6. **Window transparency (optional)** — Subtle, default 0% (opaque)
   - iTerm2 feature; most users turn off because it reduces readability

7. **Quick theme switching** — Keyboard shortcut or menu (dark/light mode sync)
   - System appearance change → terminal adapts automatically (optional)

### 6.5 Avoiding Bloat

**Anti-patterns (YAGNI):**
- File browser sidebar — Use shell `ls` command instead
- Integrated text editor — Use vim/nano inside terminal
- Built-in search/replace — Terminal is I/O layer, not editor
- Integrated REPL — Run Python/Node directly
- Plugins system (v1.0) — Complex, adds startup overhead
- Fancy animations — Tab switching, window opening (skip, instant is better)
- Translucent backgrounds — Looks cool, kills readability
- Custom rendering of ANSI codes — Just display them correctly

**Minimal feature checklist:**
- ✅ Multi-tab support
- ✅ Theme system (colors)
- ✅ Font configuration
- ✅ Scrollback buffer
- ✅ Copy/paste
- ✅ Search in scrollback
- ✅ SSH seamless integration
- ❌ Built-in file manager (use shell)
- ❌ Built-in editor (use vim)
- ❌ Plugin system (defer to v2)

---

## 7. SSH Integration Deep Dive

### 7.1 Seamless SSH UX

**Goal:** `ssh user@host` should feel native, not like "opening connection"

**Implementation:**
1. Spawn SSH process as shell: `ssh user@host`
2. SSH wraps shell on remote: `/bin/bash` (or user's shell)
3. Terminal treats SSH+shell as single process
4. All ANSI codes, mouse, colors work across SSH

**Benefits:**
- No special SSH UI needed
- Works with existing shell scripts
- SSH session title updates dynamically
- Native key binding support (send Alt locally, Meta to remote)

### 7.2 SSH Configuration

**Read from `~/.ssh/config`:**
```
Host myserver
    HostName server.example.com
    User myuser
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

**Features:**
- Auto-complete SSH hosts (completion provider)
- Use identity files from config automatically
- Respect keep-alive settings

### 7.3 Terminal Type Negotiation

**Problem:** Remote server may not recognize TERM value
**Solution:**

1. **Send sensible TERM:** `xterm-256color` (widely supported)
2. **Let SSH pick:** `SendEnv TERM` in ~/.ssh/config
3. **Fallback:** Remote server suggests xterm if TERM not recognized
4. **Test:** `echo $TERM` on remote should show correct value

**Standard progression:**
```
TERM=xterm-256color (preferred, 256-color support)
TERM=xterm (fallback, basic support)
TERM=vt100 (last resort, minimal support)
```

### 7.4 Key-based Authentication UI

**Best practice:** Show key selection, don't force single default

**UI flow:**
1. User runs `ssh user@host` in terminal
2. SSH checks `~/.ssh/config` for IdentityFile
3. If multiple keys available, SSH tries them in order
4. If passphrase-protected key, SSH prompts in terminal: `Enter passphrase for key…`
5. Terminal sends passphrase to SSH process (not visible on screen)

**No terminal-level UI needed** — SSH handles it. Terminal just passes through.

### 7.5 SSH Agent Support

**Enable SSH agent:** Terminal app should NOT manage SSH keys, let system SSH do it.

**User setup (one-time):**
```bash
ssh-add ~/.ssh/id_ed25519  # Enter passphrase, agent caches it
```

**Automatic detection:** Terminal passes `SSH_AUTH_SOCK` env var to SSH, which uses system agent. Works automatically.

### 7.6 Mouse Support Over SSH

**Challenge:** Mouse events must be encoded and sent over SSH

**Standard protocol:** SGR (Select Graphic Rendition) extended mouse protocol
- Terminal captures mouse click → encodes as escape sequence
- SSH transmits to remote → remote `vim` or `less` receives and acts
- Works seamlessly if both terminal and remote app support SGR

**Implementation:** Terminal must:
1. Send `\033[?1006h` to enable SGR mouse mode
2. Capture mouse clicks → encode as `\033[<button;x;y;M` (for click) or `m` (for release)
3. Send to PTY

**Assumption:** Most modern terminals support this; Vim 8.0+ supports SGR. Alacritty, Kitty, iTerm2 all implement this.

---

## 8. Technical Stack Recommendations

### 8.1 Rendering Backend

**Option 1: Metal (GPU-accelerated, native macOS)**
**Pros:**
- Excellent performance
- Native macOS integration
- Best for modern Macs
**Cons:**
- macOS-only, requires Metal API knowledge
- More complex code

**Option 2: CoreGraphics (CPU-based, simpler)**
**Pros:**
- Works on all macOS versions
- Simpler to implement
- Sufficient for most use cases
**Cons:**
- Slower rendering (but still acceptable)
- Less future-proof

**Recommendation for MVP:** Start with CoreGraphics + double buffering. Optimize with Metal if performance needed.

### 8.2 Text Rendering

**macOS native:**
- **CoreText** — Primary font engine, handles fallback chains, ligatures
- **CTFont, CTLine, CTRun** — Font object model
- **NSFont** — Higher-level wrapper (AppKit)

**Approach:**
1. Create CTFont with font name and size
2. For each character, create CTLine
3. Get glyph info from CTRun
4. Render glyph to texture or screen

**Fallback chain:** Use font cascade descriptor to specify multiple fonts.

### 8.3 PTY Management (macOS libc)

**API:** `<util.h>` library
```c
#include <util.h>

pid_t pid;
int master_fd, slave_fd;
struct winsize ws = {rows, cols, 0, 0};

// Fork child in PTY
pid = forkpty(&master_fd, NULL, NULL, &ws);

if (pid == 0) {
    // Child process: exec shell
    execl("/bin/bash", "bash", NULL);
} else {
    // Parent: read/write from/to shell
    read(master_fd, buffer, size);
    write(master_fd, buffer, size);
}
```

**Window size updates:** Send SIGWINCH when terminal resizes, PTY auto-updates child's TIOCSWINSZ ioctl.

### 8.4 Configuration Storage

**File format:** JSON or TOML
**Location:** `~/.config/terminal-app/config.json`

**Minimal config structure:**
```json
{
  "theme": "dracula",
  "font": {
    "family": "SF Mono",
    "size": 12
  },
  "window": {
    "width": 800,
    "height": 600,
    "opacity": 1.0
  },
  "terminal": {
    "scrollback": 3000,
    "bellVolume": 0
  },
  "shortcuts": {
    "newTab": "cmd+t",
    "nextTab": "cmd+option+right"
  }
}
```

### 8.5 ANSI Escape Sequence Handling

**Essential sequences to support:**

**Cursor movement:**
- `\033[H` — Move cursor to home (0, 0)
- `\033[{row};{col}H` — Move to row, col
- `\033[A/B/C/D` — Move up/down/right/left
- `\033[s` / `\033[u` — Save/restore cursor

**Scrolling:**
- `\033[{lines}S` — Scroll up
- `\033[{lines}T` — Scroll down

**Colors:**
- `\033[{code}m` — Select graphic rendition (colors, bold, dim, etc.)
- `\033[38;2;R;G;Bm` — Set RGB foreground color
- `\033[48;2;R;G;Bm` — Set RGB background color

**Screen control:**
- `\033[2J` — Clear entire screen
- `\033[K` — Clear to end of line
- `\033[?1049h` / `\033[?1049l` — Alternate screen buffer on/off
- `\033[?25h` / `\033[?25l` — Show/hide cursor

**Library recommendation:** Use existing ANSI parser library (e.g., libvte for reference) or implement custom parser (not too complex).

---

## 9. Key Insights & Design Decisions

### 9.1 MVP Scope

**Essential for v1.0:**
1. ✅ Multi-tab support with keyboard navigation
2. ✅ Color support (16, 256, 24-bit)
3. ✅ Font selection + size adjustment
4. ✅ Scrollback buffer (3000–5000 lines)
5. ✅ Copy/paste
6. ✅ Search in scrollback
7. ✅ SSH transparent integration
8. ✅ ANSI escape sequence rendering
9. ✅ Sensible theme system (light/dark)
10. ✅ Standard macOS keyboard shortcuts

**Nice-to-have (v1.1+):**
- Split panes (Cmd+D, Cmd+Shift+D)
- Session restoration on quit
- Custom themes (user editable)
- Shell profiles (pre-configured shells)
- Plugin system

### 9.2 Why Terminal.app is Weak

- Slow rendering (CPU-based, not optimized)
- Limited features (no split panes, limited themes)
- Dated UI (native Cocoa, but minimal polish)
- Poor SSH integration (basic)
- No multi-key bind shortcuts
- Theme system is poor (plist format, limited colors)

**Opportunity:** Build something faster, more feature-rich, better UX.

### 9.3 Why iTerm2 is Strong

- Comprehensive feature set (splits, triggers, arrangements, etc.)
- Excellent SSH integration
- Fast enough (native Objective-C, optimized)
- Extensive theming (color schemes, fonts, etc.)
- Power-user features (advanced hotkeys, scriptability)

**Downside:** Bloated for casual users, slow startup (lots of features to load).

### 9.4 Why Warp is Modern

- AI/cloud features (built-in command search, feedback)
- Slick UI (modern design language, animations)
- Good UX defaults (context detection, smart copy/paste)
- Responsive (Rust-based, performant)

**Downside:** Cloud-dependent, privacy concerns, relatively new (fewer users, less battle-tested).

### 9.5 Why Kitty is Technical

- Fastest rendering (custom GPU protocol, optimized rendering)
- Small footprint (~20MB)
- Innovative protocol (custom control sequences for images, graphics)
- Linux-native (macOS support is secondary)

**Downside:** Less polished UI, smaller ecosystem, Linux-first mindset.

### 9.6 Design Philosophy for This Project

**Goal: Build a terminal that is:**
1. **Fast** — Startup < 500ms, rendering instantly responsive
2. **Modern** — GPU-accelerated rendering, polished UI
3. **Focused** — Essential features only, no bloat
4. **Approachable** — Works out of the box with sensible defaults
5. **Extensible** — Theme system, future plugin support

**Key differentiator:** Blend of iTerm2's UX polish with Kitty's performance and Warp's modern design language.

---

## 10. Research Findings Summary

| Area | Key Finding | Implication |
|------|------------|-------------|
| **Use Cases** | SSH, git, docker, vim are critical | Terminal is I/O layer, not editor/IDE |
| **Tabs** | Cmd+Option+Right/Left = power user standard | Implement this, users expect it |
| **Colors** | 24-bit truecolor = modern standard | Support all 3 (16, 256, 24-bit), auto-detect |
| **Fonts** | Fallback chains required for Unicode | Use CoreText, not simple font selection |
| **Rendering** | GPU acceleration needed for perceived performance | GPU polish worth complexity cost |
| **Shortcuts** | macOS conventions matter (Cmd+T, Cmd+,) | Copy Apple's patterns, not reinvent |
| **Themes** | JSON easiest to parse and distribute | Start with JSON, extend to TOML later |
| **Scrollback** | 3000–5000 lines = reasonable default | Ring buffer or memory-mapped file for scaling |
| **SSH** | Works transparently if terminal is correct | No SSH-specific UI needed, just good TTY handling |
| **Polish** | Activity indicator + sensible defaults > animations | Subtle UX beats flashy features |

---

## Unresolved Questions

1. **Split panes:** Include in MVP or defer to v1.1? (High complexity, medium user demand)
2. **Theme distribution:** Bundle themes in-app or pull from external repo?
3. **Shell profile management:** Auto-detect shells or require user config?
4. **Linux support:** macOS-only for MVP, or support Linux from day 1?
5. **Plugin system:** Custom PTY hooks for extensions, or CLI-based only?
6. **Performance target:** GPU required, or optimized CPU rendering sufficient?
7. **Session persistence:** Save/restore terminal state on quit, or stateless?
8. **Accessibility:** Screen reader support, high-contrast modes, dyslexia-friendly fonts?

