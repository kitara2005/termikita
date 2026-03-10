---
title: "Vietnamese IME Compatibility Research — Terminal Input Handling"
date: 2026-03-10
researcher: researcher
status: complete
---

# Vietnamese IME Compatibility for Termikita Terminal

## Executive Summary

Vietnamese input methods (IME) on macOS use **composition-based text input** via NSTextInputClient protocol. Termikita must implement NSTextInputClient to properly receive composed characters from Telex/VNI IME systems. Key concerns: marked text (composing state) visibility, NFC normalization, Backspace handling during composition, and compatibility across different Vietnamese input apps (GoTiengViet, EVKey, built-in macOS Vietnamese).

---

## 1. Vietnamese IME Landscape on macOS

### 1.1 Built-in macOS Vietnamese Input Methods

macOS (since OS X Leopard 10.5+) includes native Vietnamese input support with three methods:

- **Simple Telex**: Simplified version, easier learning curve
- **Telex**: Standard method — type base letter + diacritical key combinations
- **VNI**: Vietnamese Numeric Input — number keys encode tones and special letters
- **VIQR**: Vietnamese Quoted Readable — punctuation-based (less common)

### 1.2 Third-Party Vietnamese IME Apps

#### GoTiengViet
- Early macOS Vietnamese input solution (similar to UniKey)
- Supports Telex, VNI, VIQR encodings
- Works through InputMethodKit (IMK) — registered input method server

#### EVKey
- Newer alternative, derived from open-source Unikey codebase
- Free for both Windows and macOS
- Key differentiator: **Application Exclusion** — blacklist apps to disable Vietnamese input (useful for developers)
- Better bug fixes and key handling vs. earlier solutions
- Also uses InputMethodKit framework

### 1.3 Historical Input Apps

- **UniKey**: Original Vietnamese IME (now discontinued for macOS in favor of EVKey)
- **OpenKey**: Legacy option (not widely used on modern macOS)

---

## 2. How Vietnamese IME Works at OS Level

### 2.1 InputMethodKit (IMK) Architecture

macOS uses **InputMethodKit (IMK)** framework for all input methods (built-in and third-party):

**Server-Client Model:**
- **Input Method Server**: Runs as a service in `/Library/Input Methods/` (e.g., `.app` bundle)
  - Registered in macOS via `InputMethodConnectionName` in Info.plist
  - Manages composition state and sends text/marked text to clients
  - Can use CGEventTap or InputMethodKit's own key interception

- **Client Application** (your terminal):
  - Implements NSTextInputClient protocol
  - Receives composition events via NSTextInputContext
  - Renders marked text (composing state) for user feedback

**Inter-process Communication:**
- IMKServer uses NSConnection for IPC with macOS and client apps
- When app has keyboard focus, the IME server receives key events
- Server responds with insertText or setMarkedText calls to client

### 2.2 Composition Flow for Telex IME

**Example: User types "e" + "s" → "é"**

1. User presses 'e' key:
   - IME receives keyDown event
   - 'e' is a valid composition start (vowel with combining marks possible)
   - IME calls `setMarkedText("e", ...)` on the terminal view
   - Terminal renders "e" in marked text style (often underlined/different color)
   - Selection is set within the marked range

2. User presses 's' key (acute accent in Telex):
   - IME interprets "e" + "s" → "é" (precomposed NFC form)
   - IME calls `setMarkedText("é", ...)` — replaces the marked text
   - Terminal re-renders marked range with "é"

3. User presses next key (e.g., space or consonant):
   - IME recognizes composition is complete
   - IME calls `insertText("é", replacementRange:...)`
   - This commits "é" from marked range to actual buffer
   - Terminal calls `unmarkText()` to clear marked range
   - Result: "é" is now in normal text, committed to PTY

**Backspace During Composition:**
- If user types "e" + "s" (now marked as "é") then presses Backspace:
  - IME handles Backspace specially during composition
  - It may create a dummy marked text "a", delete it, then re-mark remaining text
  - Terminal receives unmarkText() + setMarkedText() calls
  - This is why proper marked text handling is critical

### 2.3 Character Replacement Behavior

When IME commits composed text, it uses **NFC (Precomposed) Form**:
- "á" = U+00E1 (single precomposed character, not "a" + combining acute)
- This matches modern macOS text input conventions
- PTY receives the final precomposed character

---

## 3. NSTextInputClient Protocol — What Terminal MUST Implement

### 3.1 Required Core Methods (NSTextInputClient)

A custom NSView must implement the following methods for IME support:

```objc
// Text insertion — called when IME commits final text
- (void)insertText:(id)string replacementRange:(NSRange)replacementRange

// Marked text management — for composition state
- (void)setMarkedText:(id)string selectedRange:(NSRange)selectedRange
         replacementRange:(NSRange)replacementRange
- (void)unmarkText
- (NSRange)markedRange
- (BOOL)hasMarkedText
- (NSRange)selectedRange

// Query methods — IME asks about buffer state
- (NSAttributedString *)attributedSubstringForProposedRange:(NSRange)range
                                                actualRange:(NSRangePointer)actualRange
- (NSUInteger)characterIndexForPoint:(NSPoint)point
- (NSRect)firstRectForCharacterRange:(NSRange)range actualRange:(NSRangePointer)actualRange

// Candidate window positioning
- (void)doCommandBySelector:(SEL)selector
```

### 3.2 What Happens If NOT Implemented?

**If NSView does NOT implement NSTextInputClient:**

- macOS still sends keyDown events to the view
- IME **cannot communicate** composition state (marked text) to terminal
- User sees **only the final committed character**, not the intermediate states
- Result:
  - Telex input appears to work (final "é" appears)
  - BUT user gets no visual feedback during composition (typing "e" then "s" appears as two separate chars briefly)
  - Backspace during composition doesn't work correctly
  - **This is problematic UX but technically functional for final output**

**Can We Skip NSTextInputClient?**
- For a basic terminal: **No**, you should implement it for:
  1. Proper marked text rendering (composing state visible)
  2. Correct Backspace behavior during composition
  3. Candidate window support (some Chinese/Japanese IMEs require this)
  4. Better compatibility with third-party IMEs (GoTiengViet, EVKey)

### 3.3 PyObjC Implementation Pattern

In PyObjC (Python bridge to Objective-C):

```python
from PyObjC import objc
from Cocoa import NSView, NSTextInputClient

class TerminalView(NSView, NSTextInputClient):
    def __init__(self):
        super().__init__()
        self._marked_range = (0, 0)  # NSNotFound, 0 when no marked text
        self._selected_range = (0, 0)
        self.text_buffer = ""  # Simple example, actual impl uses pyte.Screen

    # Required NSTextInputClient methods

    def insertText_replacementRange_(self, string, replacementRange):
        """Called when IME commits final text."""
        # replacementRange: (0, 1) means replace char at 0-1
        # replacementRange: (NSNotFound, 0) means insert at current position
        if replacementRange[0] == NSNotFound:
            # Insert at current position
            pass
        else:
            # Replace specified range
            pass
        # Send to PTY
        self.send_to_pty(string)
        # Clear marked text
        self._marked_range = (NSNotFound, 0)

    def setMarkedText_selectedRange_replacementRange_(self, string, selRange, replRange):
        """Called when IME is composing (marked text phase)."""
        # string: current composition (e.g., "é")
        # selRange: selection within marked text
        # replRange: where to insert this marked text

        # Store marked text state
        self._marked_text = string
        self._marked_range = (0, len(string))
        self._selected_range = selRange

        # Render with different styling (underline, background color)
        self.setNeedsDisplay_(True)  # Trigger redraw

    def unmarkText(self):
        """Clear marked text — composition complete."""
        self._marked_range = (NSNotFound, 0)
        self.setNeedsDisplay_(True)

    def markedRange(self):
        """Return current marked range or (NSNotFound, 0) if none."""
        return self._marked_range

    def hasMarkedText(self):
        """Is composition in progress?"""
        return self._marked_range[1] > 0

    def selectedRange(self):
        """Return selection within marked text (or overall buffer)."""
        return self._selected_range

    def attributedSubstringForProposedRange_actualRange_(self, range_, actualRangePtr):
        """IME queries text in buffer for context."""
        # Return text in specified range (used for candidate selection)
        text = self.text_buffer[range_[0]:range_[0]+range_[1]]
        return text

    def firstRectForCharacterRange_actualRange_(self, range_, actualRangePtr):
        """Return screen position for candidate window."""
        # IME needs to know where to show candidate list
        # Compute the rectangle based on glyph layout
        return NSMakeRect(x, y, width, height)

    def characterIndexForPoint_(self, point):
        """Map screen point to character index in buffer."""
        # Used for mouse-based candidate selection
        return index

    def doCommandBySelector_(self, selector):
        """Handle special key sequences (e.g., Escape, Arrow keys)."""
        # Some IMEs send commands instead of text
        pass
```

---

## 4. Telex/VNI Composition Behavior Deep Dive

### 4.1 Telex Diacritical Key Mappings

In Telex, Vietnamese diacritics use keys that don't appear at word-end in English:

| Diacritic | Key | Example |
|-----------|-----|---------|
| á (acute) | s | muas = muá |
| à (grave) | f | mauf = mà |
| ả (hook) | r | maur = mả |
| ã (tilde) | x | maux = mã |
| ạ (dot below) | j | mauj = mạ |
| â (circumflex) | aa | maa = mâ |
| ê (circumflex e) | ee | mee = mê |
| ô (circumflex o) | oo | moo = mô |
| ơ (horn) | w | maw = mơ |
| ư (horn) | ư | muu = mư |

### 4.2 Real-Time Composition Example: "ươ" (horn-circumflex o)

**Sequence: u → u → o → (final character)**

1. **Keystroke 1: 'u'**
   - IME recognizes 'u' as start of two-letter sequence
   - setMarkedText("u", selectedRange=(0,1))
   - Terminal shows "u" underlined

2. **Keystroke 2: 'u'** (second 'u' → starts "ư" composition)
   - IME interprets "u" + "u" → "ư" (horn combining with u)
   - setMarkedText("ư", selectedRange=(0,1))
   - Terminal updates underlined display to "ư"

3. **Keystroke 3: 'o'**
   - IME interprets "ư" + "o" → "ươ" (horn-circumflex combining with o)
   - setMarkedText("ươ", selectedRange=(0,1))
   - Terminal updates to show "ươ"

4. **Keystroke 4: Space (or next letter)**
   - IME recognizes "ươ" is complete
   - insertText("ươ", replacementRange=currentMarkedRange)
   - unmarkText()
   - Terminal commits "ươ" to buffer, sends to PTY

### 4.3 Backspace During Composition

**Scenario: User types "a" → "a" → "s" (now has "á") → Backspace**

1. After typing "a", "a", "s":
   - Marked text = "á"
   - User presses Backspace

2. IME **handles Backspace specially**:
   - Creates dummy marked text (e.g., setMarkedText("a", ...))
   - Then immediately unmarks it
   - Backtracks composition state to "a" (second 'a' in "aa")
   - Now setMarkedText("â", ...) for the "aa" (circumflex e)

3. **Critical Point**: Terminal MUST support:
   - Quick sequence of unmarkText() → setMarkedText() calls
   - Proper replacement of marked range without moving cursor
   - NOT sending Backspace to PTY during composition state

---

## 5. Known Issues: Vietnamese IME + Terminal Emulators

### 5.1 Alacritty (Rust Terminal)

**Issues:**
- **Lag/Performance**: Switching to Vietnamese input source causes noticeable latency
- **Character Input**: Issues with composition not completing properly
- **Keyboard Switch**: Can't switch input methods while Alacritty has focus (reported in Issue #935)
- **Multi-key Sequences**: Neovim's multi-key input doesn't work with Chinese IME; similar issues reported with Vietnamese

**Root Cause**: Alacritty's minimal Cocoa implementation doesn't properly implement NSTextInputClient, causing IME to fail composition callbacks

### 5.2 iTerm2 (Objective-C Terminal)

**Status**: ✅ Works well with Vietnamese Telex/VNI

**Why it Works:**
- Implements full NSTextInputClient protocol in PTYTextView.m
- Proper marked text rendering (underline + different color)
- Correct insertText + unmarkText sequencing
- Good Backspace handling during composition

**Evidence**: iTerm2 source code includes `PTYTextView.m` with NSTextInputClient methods implemented

### 5.3 macOS Terminal.app

**Status**: ✅ Works but limited

- Supports Vietnamese input via Telex/VNI
- NSTextInputClient implementation exists (standard Cocoa NSView behavior)
- Limited styling for marked text (less visual feedback than iTerm2)

### 5.4 Kitty (Terminal Emulator)

**Status**: Unknown for Vietnamese, but has comprehensive keyboard protocol documentation
- May not properly support NSTextInputClient if using custom rendering

### 5.5 Common Failure Patterns

| Issue | Cause | Impact |
|-------|-------|--------|
| Double characters after composition | Terminal receives both keyDown + insertText | "aá" instead of "á" |
| Missing diacritics | NFC normalization not applied | "a" + combining accent instead of "á" |
| Visible composing state | No marked text styling | User doesn't see intermediate composition |
| Backspace deletes wrong char | Not handling marked range replacement | "aaá" → Backspace → "a" (instead of "â") |
| Candidate window misplaced | firstRectForCharacterRange not implemented | Candidate list appears off-screen |

---

## 6. GoTiengViet & EVKey Specifics

### 6.1 How They Differ from Built-in macOS Vietnamese

**Built-in Telex/VNI:**
- Implemented in macOS's Text Input System
- Uses standard InputMethodKit APIs
- Communicates via NSTextInputClient protocol

**GoTiengViet & EVKey:**
- Also use InputMethodKit framework
- **Registration**: Installed as `.app` bundles in `~/Library/Input Methods/` or `/Library/Input Methods/`
- **Key Interception**: Use InputMethodKit's key event callback system (not CGEventTap)
- **Composition**: Same as built-in — use setMarkedText/insertText/unmarkText sequence

### 6.2 CGEventTap vs InputMethodKit

**CGEventTap Approach** (low-level keyboard interception):
- Intercepts at system level before NSTextInputSystem sees it
- Requires Input Monitoring permission (macOS 10.15+)
- Can modify/block events
- **Not used by most Vietnamese IMEs** (overkill, breaks standard text input)

**InputMethodKit Approach** (IMK server):
- Operates within macOS Text Input System
- Works with NSTextInputClient protocol
- Standard, supported by Apple
- **This is what GoTiengViet & EVKey use**

### 6.3 Text Replacement Behavior

**When EVKey commits text:**
- Calls `insertText("ế", replacementRange:(NSNotFound,0))` directly
- NOT backspace + insertion — it's direct replacement via NSTextInputClient
- This requires terminal to properly implement insertText:replacementRange:

### 6.4 EVKey's Application Exclusion Feature

EVKey allows blacklisting apps that shouldn't use Vietnamese input (e.g., code editors):
- When app is in exclusion list, EVKey passes keystrokes through without composition
- Terminal app receives raw keyDown events instead of insertText
- Useful for developers who want raw input to shell

**For Termikita**: Should we add EVKey exclusion list support? Currently low priority, but could be a settings option.

---

## 7. Unicode Normalization: NFC vs NFD

### 7.1 Why Normalization Matters for Vietnamese

Vietnamese characters use combining marks. Same visual character can have multiple encodings:

**Example: "ế" (e with circumflex + acute)**

**NFC Form** (Composed, RECOMMENDED):
- Single codepoint: U+1EBF
- One character in buffer
- **This is what Telex IME sends**

**NFD Form** (Decomposed):
- Three codepoints: U+0065 (e) + U+0302 (combining circumflex) + U+0301 (combining acute)
- Visually identical but three characters
- **Some terminals drop combining marks in NFD form**

### 7.2 Terminal Rendering Issues

KDE's Konsole has known bug: **drops accents when receiving NFD form Vietnamese text**
- Receives "e + combining circumflex + combining acute"
- Renders only "e" (drops combining marks)

Wez's Terminal (WezTerm) has explicit fix: `normalize_output_to_unicode_nfc` setting
- When enabled, normalizes all PTY output to NFC
- Ensures combining marks are preserved

### 7.3 Recommendation for Termikita

**For text received FROM IME (insertText):**
- Telex/VNI IMEs send NFC form — trust it as-is
- Don't re-normalize (would be wasteful)

**For text received FROM PTY (output from shell commands):**
- Apply NFC normalization before rendering
- Python: `unicodedata.normalize("NFC", text)`
- Prevents display corruption if command outputs NFD form

**For text sent TO PTY (from user input via IME):**
- IME provides NFC form — send directly to PTY
- PTY forwards to shell commands (they handle their own encoding)

---

## 8. Marked Text Rendering Strategy for Termikita

### 8.1 What is "Marked Text" (Composing State)?

**Marked Text** = Text currently being composed by IME, not yet committed

In Telex: "e" → setMarkedText("e") → "s" → setMarkedText("é") [still marked]

Terminal must render marked text **distinctly** so user knows it can still be modified.

### 8.2 Rendering Options

| Style | Implementation | UX |
|-------|-----------------|-----|
| **Underline** | Draw line under marked chars | Good, non-intrusive |
| **Background Color** | Light highlight (e.g., yellow) | Very visible |
| **Dotted Border** | Border around marked text | macOS standard |
| **Inverse Video** | Swap foreground/background | Aggressive |

**macOS Standard**: Dotted underline or light background highlight

### 8.3 Implementation for Termikita

In CoreText-based rendering:

```python
def draw_marked_text(self, context, x, y, marked_text, marked_range):
    """Render text currently being composed by IME."""

    # Draw text normally first
    self.draw_text(context, x, y, marked_text, foreground_color)

    # Add visual indicator for marked text
    # Option 1: Underline
    underline_y = y + line_height - 2
    CGContextSetStrokeColor(context, 0, 0, 0, 1)  # Black
    CGContextSetLineWidth(context, 1.0)
    CGContextMoveToPoint(context, x, underline_y)
    CGContextAddLineToPoint(context, x + text_width, underline_y)
    CGContextStrokePath(context)

    # Option 2: Background highlight (replaces first option)
    # highlight_rect = NSMakeRect(x, y, text_width, line_height)
    # [[NSColor yellowColor] set]
    # NSRectFill(highlight_rect)
```

### 8.4 Marked Range State Management

Terminal must track:
- `markedRange`: (position, length) — where composed text is
- `selectedRange`: Within marked text, which chars are "selected" for next modification
- `hasMarkedText`: Boolean — is composition in progress?

When `unmarkText()` is called → clear marked range, switch to normal rendering

---

## 9. Testing Strategy for Vietnamese IME Compatibility

### 9.1 Test Scenarios

**A. Basic Telex Composition:**
```
User types: "m" "a" "u" "s"
Expected: Renders as "m" → "ma" → "mau" → "maus" (final 's' for acute)
Result: Terminal shows "maus" in buffer
```

**B. Multi-keystroke Composition:**
```
User types: "u" "u" "o" " " (space to commit)
Expected: During composition: "u" (underlined) → "ư" (underlined) → "ươ" (underlined) → " "
Result: "ươ" is committed (not "uuo ")
```

**C. Backspace During Composition:**
```
Setup: User has typed "m" "a" "s" (now marked as "más")
User: Press Backspace
Expected: Revert to "ma" (marked as "â" from "aa"), not "mások"
```

**D. Interleaved Composition & Regular Input:**
```
User: Type "hello" then switch to Vietnamese, type "m" "a" "s", type "world"
Expected: "hellomásworld" (composition doesn't interfere with surrounding text)
```

**E. Copy/Paste from Terminal:**
```
Setup: Terminal shows "Tiếng Việt" (composed via IME)
Action: Copy from terminal, paste to text editor
Expected: Text editor receives "Tiếng Việt" in NFC form, displays correctly
```

**F. Third-Party IME (EVKey):**
```
Setup: EVKey installed and set as input method
User: Type using EVKey (same as Telex)
Expected: Same composition behavior as built-in Telex
```

### 9.2 Validation Checklist

- [ ] setMarkedText() called → text rendered underlined/highlighted
- [ ] unmarkText() called → underline removed, text stays in buffer
- [ ] Backspace during composition → marked range updates correctly
- [ ] insertText() with replacementRange → marked text replaced with final character
- [ ] Cursor position correct after composition
- [ ] Multiple compositions in sequence work (can compose multiple words)
- [ ] Marked text cleared when switching to non-Vietnamese input
- [ ] markedRange() returns correct position after each keystroke
- [ ] NFC form preserved in buffer (test with hexdump)
- [ ] Works with GoTiengViet and EVKey, not just built-in Telex

### 9.3 Tools for Testing

**Test Vietnamese IME Input:**
1. Enable Vietnamese Telex in System Preferences > Keyboard > Input Sources
2. Focus Termikita, type: `maus` (should see "más" composed)
3. Type: `uuo` (should see "ươ" composed, space commits)

**Verify Byte Encoding:**
```bash
# In terminal, type something with Vietnamese
# Copy from terminal, paste into a file
hexdump -C file.txt

# Check for precomposed characters
# NFC: 1E BF (one byte pair for "ế")
# NFD: 65 CC 82 CC 81 (5 bytes: e + circumflex + acute)
```

**Test with Multiple IME Apps:**
- Install GoTiengViet or EVKey
- Switch input source
- Verify same composition behavior works

**Stress Test:**
- Rapid typing with composition
- Fast backspace during composition
- Switch between English and Vietnamese mid-word

---

## 10. Recommendations for Termikita Implementation

### 10.1 Must-Have Features (MVP)

1. **Implement NSTextInputClient protocol** (all required methods)
   - Don't skip this — necessary for proper Vietnamese input
   - PyObjC provides full bindings to NSTextInputClient

2. **Marked Text Rendering**
   - Minimum: Underline composed characters
   - Nice-to-have: Light background highlight
   - Store markedRange state, update display on setMarkedText/unmarkText calls

3. **Correct insertText:replacementRange: Handling**
   - Respect replacementRange parameter (where to replace)
   - Don't blindly insert at cursor position

4. **NFC Normalization on PTY Output**
   - Before rendering text from shell, normalize to NFC
   - Prevents display corruption if shell outputs NFD form

5. **Clear Marked State on Input Source Change**
   - If user switches from Vietnamese to English, unmarkText()
   - Prevents stale marked text if IME switches unexpectedly

### 10.2 Nice-to-Have Features

6. **Candidate Window Support**
   - firstRectForCharacterRange: returns proper position
   - Not critical for Vietnamese Telex (no candidates), but needed for Chinese/Japanese
   - Improves future-proofing

7. **Backspace Handling Edge Cases**
   - Special care during marked text phase
   - Don't send Backspace to PTY if composition is in progress

8. **Application Exclusion Mode**
   - (Optional, low priority) Detect EVKey's exclusion list
   - Or provide setting to disable Vietnamese in certain contexts

### 10.3 Testing Plan

- **Phase 1**: Implement basic NSTextInputClient (insertText, setMarkedText, unmarkText)
- **Phase 2**: Add marked text rendering (underline)
- **Phase 3**: Test with built-in macOS Telex input
- **Phase 4**: Test with GoTiengViet and EVKey
- **Phase 5**: Edge case testing (rapid composition, Backspace, copy/paste)
- **Phase 6**: Validate NFC normalization on PTY output

### 10.4 Architecture Integration Point

Where does NSTextInputClient fit in Termikita?

```
NSWindow
  └─ TerminalView (NSView)
      ├─ Implement NSTextInputClient protocol ← ADD HERE
      │   ├── insertText → forward to TerminalSession
      │   ├── setMarkedText → render underline, don't send to PTY
      │   └── unmarkText → clear styling
      ├─ keyDown: (NSEvent) → call interpretKeyEvents for IME integration
      ├─ CoreText rendering ← update to show marked text styling
      └─ TextInputContext (auto-created if NSTextInputClient adopted)
```

---

## 11. Summary Table: IME Support by Terminal

| Terminal | NSTextInputClient | Marked Text | Works with Telex | Notes |
|----------|-------------------|-------------|------------------|-------|
| **iTerm2** | ✅ Full | ✅ Yes | ✅ Yes | Gold standard for Vietnamese |
| **macOS Terminal.app** | ✅ Partial | ⚠️ Limited | ✅ Yes | Works but minimal UX |
| **Alacritty** | ❌ No | ❌ No | ❌ Issues | Lag, composition fails |
| **Kitty** | ❌ No | ❌ No | ❓ Unknown | Custom rendering may not work |
| **Termikita (Plan)** | 🔲 TBD | 🔲 TBD | 🔲 TBD | Must implement for full support |

---

## 12. Unresolved Questions

1. **Can Termikita rely on raw keyDown events alone?**
   - No. Without NSTextInputClient, marked text feedback breaks. Must implement protocol.

2. **Does EVKey require special handling?**
   - No. EVKey uses standard InputMethodKit → NSTextInputClient flow, same as built-in.

3. **Should Termikita render candidate windows?**
   - Not for Vietnamese Telex (no candidates), but needed for future Chinese/Japanese support.
   - Can defer this, but implement firstRectForCharacterRange: for future-proofing.

4. **Will Termikita work with older GoTiengViet?**
   - If GoTiengViet uses InputMethodKit (it does), yes — same protocol as EVKey and built-in.

5. **What if user has multiple marked text sections?**
   - macOS allows only **one** marked range per NSTextInputClient at a time.
   - Not an issue for Vietnamese.

6. **Should we implement doCommandBySelector:?**
   - Low priority. Handles special key sequences (Escape, Arrows during IME).
   - Basic implementation: `pass` (do nothing, let IME handle it).

---

## References & Sources

### Vietnamese Input Methods
- [Typing in Vietnamese: For Macs](http://typingvietnamese.blogspot.com/p/mac-users-running-os-x-leopard-version.html)
- [How to Type Vietnamese: Complete Guide to Telex & VNI Keyboards](https://vietnameselab.com/blog/vietnamese-typing)
- [Telex Input Method - Wikipedia](https://en.wikipedia.org/wiki/Telex_(input_method))
- [Vietnamese Language and Computers - Wikipedia](https://en.wikipedia.org/wiki/Vietnamese_language_and_computers)
- [Top 3 Best Vietnamese Typing Software for Mac 2025 – Epione](https://epione.vn/en/blogs/cong-nghe/top-3-bo-go-tieng-viet-cho-mac-2025)
- [EVKey Vietnamese Input Method](https://www.phucanh.vn/bo-go-tieng-viet-evkey.html)

### NSTextInputClient Protocol
- [NSTextInputClient | Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nstextinputclient)
- [insertText:replacementRange: | Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nstextinputclient/1438258-inserttext?language=objc)
- [setMarkedText:selectedRange:replacementRange: | Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nstextinputclient/1438246-setmarkedtext?language=objc)
- [Text Editing - Apple Developer Documentation](https://developer.apple.com/library/archive/documentation/TextFonts/Conceptual/CocoaTextArchitecture/TextEditing/TextEditing.html)
- [875674 - Implement NSTextInputClient protocol on Mac - Mozilla Bugzilla](https://bugzilla.mozilla.org/show_bug.cgi?id=875674)
- [TextInputView - Apple Sample Code](https://developer.apple.com/library/archive/samplecode/TextInputView/Introduction/Intro.html)
- [FB13789916: NSTextInputClient.setMarkedText - GitHub](https://gist.github.com/krzyzanowskim/340c5810fc427e346b7c4b06d46b1e10)

### Terminal Emulator Implementations
- [iTerm2/sources/PTYTextView.m - GitHub](https://github.com/gnachman/iTerm2/blob/master/sources/PTYTextView.m)
- [Alacritty Issue #4204: Lag when changing input source](https://github.com/alacritty/alacritty/issues/4204)
- [Alacritty Issue #935: Can't switch keyboards on macOS while focused](https://github.com/alacritty/alacritty/issues/935)
- [macOS: Alacritty lag when change input source](https://github.com/alacritty/alacritty/issues/4204)
- [Chinese characters input troubleshooting - Alacritty](https://github.com/alacritty/alacritty/issues/1040)
- [macOS tip regression: Backspace in active IME composition - Ghostty](https://github.com/ghostty-org/ghostty/issues/7225)

### InputMethodKit Architecture
- [InputMethodKit | Apple Developer Documentation](https://developer.apple.com/documentation/inputmethodkit)
- [Input Method Kit - slideshare](https://www.slideshare.net/slideshow/input-method-kit/11645272)
- [Write your own IME on macOS - Inoki's Blog](https://blog.inoki.cc/2021/06/19/Write-your-own-IME-on-macOS-1/)
- [macOS_IMKitSample_2021 - GitHub](https://github.com/ensan-hcl/macOS_IMKitSample_2021)
- [What is InputMethodKit on macOS? - macOSbin](https://macosbin.com/bin/inputmethodkit)

### Key Event Handling & Composition
- [Handling Key Events - Apple Developer Documentation](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/EventOverview/HandlingKeyEvents/HandlingKeyEvents.html)
- [RFR: TextArea Committing text with ENTER in IME window - OpenJFX](https://www.mail-archive.com/openjfx-dev@openjdk.org/msg10455.html)
- [Comprehensive keyboard handling in terminals - Kitty](https://sw.kovidgoyal.net/kitty/keyboard-protocol/)
- [Event order of keydown/keyup and composition events on macOS - WebKit Bug](https://bugs.webkit.org/show_bug.cgi?id=165004)
- [Use handleEvent instead of interpretKeyEvents - iTerm2 PR #279](https://github.com/gnachman/iTerm2/pull/279)

### Unicode Normalization
- [Unicode Equivalence - Wikipedia](https://en.wikipedia.org/wiki/Unicode_equivalence)
- [Unicode Normalization - win.tue.nl](https://win.tue.nl/~aeb/linux/uc/nfc_vs_nfd.html)
- [Unicode Normalization Explained: NFC vs NFD - Unicode.Live](https://unicode.live/unicode-normalization-explained-nfc-vs-nfd-vs-nfkc-vs-nfkd)
- [Normalization in HTML and CSS - W3C](https://www.w3.org/International/questions/qa-html-css-normalization)
- [normalize_output_to_unicode_nfc - Wez's Terminal Emulator](https://wezterm.org/config/lua/config/normalize_output_to_unicode_nfc.html)
- [Unicode Normalization and Android - Dan Lew's Blog](https://blog.danlew.net/2012/04/10/unicode_normalization_and_android/)

### Keyboard Event Interception
- [Keyboard event interception on macOS - R0uter's Blog](https://www.logcg.com/en/archives/2902.html)
- [EventTapper: CGEventTap-based module - GitHub](https://github.com/usagimaru/EventTapper)
- [CGEvent Taps and Code Signing - Daniel Raffel](https://danielraffel.me/til/2026/02/19/cgevent-taps-and-code-signing-the-silent-disable-race/)
- [Input Monitoring Permission on macOS - Apple Developer Forums](https://developer.apple.com/forums/thread/111112)

### PyObjC References
- [PyObjC - PyPI](https://pypi.org/project/pyobjc/)
- [PyObjC GitHub Repository](https://github.com/ronaldoussoren/pyobjc)
- [NSTextInputClient Example - GitHub](https://github.com/jessegrosjean/NSTextInputClient)

---

**Report Date**: 2026-03-10
**Researcher**: researcher
**Status**: Ready for Termikita implementation planning
