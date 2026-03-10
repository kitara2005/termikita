# Phase 08: Command Block Rendering

## Overview
- **Priority:** P3
- **Status:** TODO
- **Effort:** Very High (~800 LOC, major architecture change)
- Render each command + output as a distinct visual block (like Warp).

## Concept
Instead of continuous text stream, each command becomes a collapsible block:
```
┌─ $ npm run build ────────────────── ✓ ─┐
│ Building...                             │
│ Build complete in 2.3s                  │
└─────────────────────────────────────────┘

┌─ $ npm run test ─────────────────── ✗ ─┐
│ FAIL src/auth.test.ts                   │
│ Expected: true, Received: false         │
└─────────────────────────────────────────┘
```

## Major Challenge
Requires fundamental change to rendering pipeline:
- Current: cell grid, no structure awareness
- Needed: command boundary detection + block-level rendering
- Shell integration needed (shell prompt detection or shell integration protocol)

## Prerequisite
- Phase 02 (Status Bar — CWD/shell detection)
- Phase 06 (Syntax Highlighting)

## Success Criteria
- [ ] Commands rendered as distinct blocks
- [ ] Blocks collapsible
- [ ] Exit code badge (✓/✗)
- [ ] Re-run command button
