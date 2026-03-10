# Phase 04: Font Ligatures + Better Typography

## Overview
- **Priority:** P1
- **Status:** TODO
- **Effort:** Low (~50 LOC changes)

## Features

- Enable OpenType ligatures for supported fonts (JetBrains Mono, Fira Code, Cascadia Code)
- Ligatures: `=>`, `!=`, `===`, `->`, `<-`, `>=`, `<=`, `|>`
- Config option: `ligatures: true/false`

## Implementation

CoreText already supports ligatures. Need to:
1. Add `kCTLigatureAttributeName` to attributed string in `text_renderer.py`
2. Add `ligatures` boolean to `config_manager.py`
3. When drawing multi-char sequences, detect ligature pairs and render as single glyph

## Challenge
Terminal renders char-by-char (cell grid). Ligatures span multiple cells.
**Solution:** Pre-scan each line for ligature pairs → render as single glyph spanning 2-3 cells.

## Related Code Files
**Modify:**
- `src/termikita/text_renderer.py` — ligature rendering
- `src/termikita/config_manager.py` — add `ligatures` config
- `src/termikita/cell_draw_helpers.py` — multi-cell glyph support

## Success Criteria
- [ ] `=>` renders as ligature arrow with supported fonts
- [ ] Config toggle works
- [ ] No visual glitches with non-ligature fonts
