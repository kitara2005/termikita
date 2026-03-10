# Phase 01: Smart Context Menu (Content Detection)

## Overview
- **Priority:** P0
- **Status:** TODO
- **Effort:** Medium (~200 LOC new)
- Enhance right-click menu with context-aware items based on text under cursor.

## Key Insight
Current menu is static. Smart menu detects what's under the cursor (file path, URL, error line) and shows relevant actions.

## Menu Items by Context

### When cursor is over a file path (e.g. `src/auth/login.ts`)
```
Open in Default Editor    ← NSWorkspace openFile
Reveal in Finder          ← NSWorkspace selectFile
Copy Path                 ← clipboard
───────────────────
[standard items]
```

### When cursor is over a URL (e.g. `https://github.com/...`)
```
Open URL                  ← NSWorkspace openURL
Copy URL                  ← clipboard
───────────────────
[standard items]
```

### When cursor is over an error location (e.g. `auth.ts:32:5`)
```
Open at Line              ← open editor at line
Copy Error                ← clipboard
───────────────────
[standard items]
```

### Default (no special content detected)
```
[existing standard items - Copy/Paste/Select All/Clear/tabs]
```

## Architecture

New module: `content_detector.py` (~80 LOC)
- `detect_content(text: str) -> ContentMatch`
- Returns: `ContentMatch(type=FILE|URL|ERROR|NONE, value=str, metadata=dict)`
- Regex patterns for:
  - File paths: `/path/to/file`, `./relative/path`, `src/file.ext`
  - URLs: `http(s)://...`, `ftp://...`
  - Error locations: `filename:line:col`, `filename:line`
  - Validate file exists on disk before showing "Open" items

## Related Code Files

**Create:**
- `src/termikita/content_detector.py`

**Modify:**
- `src/termikita/terminal_view_input.py` — extend `menuForEvent_()` to detect content at click position
- `src/termikita/terminal_view.py` — forward new action selectors

## Implementation Steps

1. Create `content_detector.py` with regex-based detection
2. In `menuForEvent_()`, get text at click position from buffer
3. Run detection → prepend context-specific items to menu
4. Add action methods:
   - `openFile_` → `NSWorkspace.sharedWorkspace().openFile_(path)`
   - `revealInFinder_` → `NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_()`
   - `openURL_` → `NSWorkspace.sharedWorkspace().openURL_()`
   - `copyPath_` / `copyURL_` → clipboard
5. For "Open at Line": use `open -a "Visual Studio Code" --args --goto file:line`

## Helper: Get Text at Click Position

```python
def _get_text_at_position(self, row, col):
    """Extract word/token at (row, col) from buffer."""
    lines = self._session.buffer.get_visible_lines()
    if row >= len(lines):
        return ""
    line_cells = lines[row]
    # Expand from col left/right to find word boundary
    text = "".join(c.char for c in line_cells).strip()
    # Find the token containing col
    # Use whitespace splitting + position mapping
    ...
```

## Success Criteria
- [ ] Right-click on file path shows Open/Reveal/Copy Path
- [ ] Right-click on URL shows Open URL/Copy URL
- [ ] Right-click on error location shows Open at Line
- [ ] Right-click on plain text shows standard menu
- [ ] File existence check before showing "Open File"
