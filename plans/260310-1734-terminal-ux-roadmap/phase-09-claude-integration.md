# Phase 09: Claude AI Integration

## Overview
- **Priority:** P3
- **Status:** TODO
- **Effort:** Very High (~500 LOC)
- Context menu and keyboard shortcuts for AI actions: explain, fix, refactor.

## Features

### Right-click selected text/error:
```
Explain with Claude     ← sends "explain: {selected text}" to PTY
Fix with Claude         ← sends "fix this error: {error text}"
Refactor with Claude    ← sends "refactor: {selected code}"
Add Tests with Claude   ← sends "write tests for: {selected code}"
```

### How it works
1. User selects text or right-clicks error
2. Menu action constructs a prompt
3. Writes prompt to PTY as if user typed it
4. Works with any Claude CLI session

## Key Design Decision
**Don't call Claude API directly.** Just type into the terminal. This:
- Works with any Claude CLI version
- No API key management needed
- User sees exactly what's sent
- Respects Claude Code's context/permissions

## Implementation
- Construct prompt string from selected text + action type
- Write to PTY: `claude "explain this: {text}"\n`
- Or if already in Claude session, just type the prompt + Enter

## Success Criteria
- [ ] Right-click error → "Fix with Claude" sends prompt
- [ ] Selected code → "Explain with Claude" works
- [ ] Works with active Claude CLI session
- [ ] Prompt visible to user before execution
