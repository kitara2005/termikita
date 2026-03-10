# Phase 05: Smart File/URL Detection & Click

## Overview
- **Priority:** P1
- **Status:** TODO
- **Effort:** Medium (~200 LOC)

## Features

- Auto-detect file paths and URLs in terminal output
- Underline on Cmd+hover (like VS Code terminal)
- Cmd+click opens file/URL
- Color clickable links differently (subtle underline)

## Implementation

1. New `link_detector.py` — regex patterns for files/URLs
2. In `terminal_view_draw.py` — render detected links with underline when Cmd held
3. In `terminal_view_input.py` — handle Cmd+click to open

## Detection Patterns
```python
URL_RE = r'https?://[^\s<>"\')}\]]+'
FILE_RE = r'(?:\.?/)?(?:[\w.-]+/)*[\w.-]+\.\w{1,10}(?::\d+(?::\d+)?)?'
```

## Interaction
- **Cmd+hover**: Underline link, show hand cursor
- **Cmd+click**: Open file in editor / URL in browser
- **No modifier**: Normal selection (no link behavior)

## Related Code Files
**Create:**
- `src/termikita/link_detector.py`

**Modify:**
- `src/termikita/terminal_view_draw.py` — link underline rendering
- `src/termikita/terminal_view_input.py` — Cmd+click handling
- `src/termikita/terminal_view.py` — forward new mouse methods

## Success Criteria
- [ ] URLs underlined on Cmd+hover
- [ ] Cmd+click URL opens browser
- [ ] File paths detected and openable
- [ ] `file:line:col` opens editor at position
- [ ] Normal click/selection unaffected
