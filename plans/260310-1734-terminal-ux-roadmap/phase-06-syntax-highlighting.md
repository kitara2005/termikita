# Phase 06: Syntax Highlighting for Code Blocks

## Overview
- **Priority:** P2
- **Status:** TODO
- **Effort:** High (~400 LOC)
- Detect code blocks in terminal output (especially Claude CLI responses) and apply syntax highlighting.

## Approach

1. Detect fenced code blocks (``` markers) in terminal output stream
2. Use `pygments` library to tokenize and colorize
3. Override cell colors for detected code regions
4. Add new dependency: `pygments>=2.17`

## Key Challenge
Terminal output is a stream of characters, not structured markdown. Need to:
- Track state: "inside code block" vs "outside"
- Detect language from ` ```ts ` / ` ```python ` markers
- Map pygments tokens to terminal ANSI colors

## Architecture
- `syntax_highlighter.py` — code block state machine + pygments integration
- Hook into `buffer_manager.py` post-processing after VT100 parsing
- Only colorize cells that don't already have explicit ANSI colors

## Success Criteria
- [ ] Fenced code blocks from Claude CLI are syntax-highlighted
- [ ] Language auto-detection from fence markers
- [ ] Doesn't interfere with existing ANSI-colored output
- [ ] Performance: <1ms per code block highlight pass
