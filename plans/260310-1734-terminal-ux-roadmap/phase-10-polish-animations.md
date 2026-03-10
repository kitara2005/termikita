# Phase 10: Polish & Animations

## Overview
- **Priority:** P3
- **Status:** TODO
- **Effort:** Low (~150 LOC)
- Small UX improvements that make the terminal feel polished.

## Features

1. **Smooth cursor animation** — cursor slides between positions instead of jumping
2. **Tab switch animation** — subtle fade/slide on tab change
3. **Hover file preview** — tooltip showing first lines of file when hovering `file:line`
4. **Claude thinking indicator** — detect "Thinking..." in output, show animated dots
5. **Selection highlight animation** — smooth highlight appearance
6. **Scroll momentum** — smoother scroll deceleration

## Implementation Notes
- Use `NSAnimationContext` for smooth transitions
- Keep animations <200ms — terminal should feel instant
- All animations disableable via config: `animations: false`

## Success Criteria
- [ ] Cursor movement is smooth
- [ ] Animations are subtle, not distracting
- [ ] Can be disabled in config
- [ ] No performance impact on rendering
