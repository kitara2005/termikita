/// VT100/xterm escape sequence parser — byte-by-byte state machine.
///
/// Parses CSI (ESC[), OSC (ESC]), and basic control characters.
/// Dispatches actions to ScreenBuffer for grid operations.

import Foundation

final class VT100Parser {
    /// The screen buffer to apply parsed commands to.
    weak var screen: ScreenBuffer?

    /// Callbacks for events that go beyond screen buffer.
    var onTitleChange: ((String) -> Void)?
    var onBell: (() -> Void)?
    /// Write response back to PTY (e.g., DA1 reply).
    var onResponse: ((Data) -> Void)?

    // DEC private mode state
    var cursorVisible: Bool = true
    var cursorShape: CursorShape = .block
    var bracketedPaste: Bool = false
    var synchronizedOutput: Bool = false
    var altScreenActive: Bool = false

    // Saved state for alt screen
    private var savedMainScreen: [[Cell]]?
    private var savedCursorRow: Int = 0
    private var savedCursorCol: Int = 0

    // Parser state machine
    private enum State {
        case ground
        case escape         // Got ESC
        case csiEntry       // Got ESC[
        case csiParam       // Collecting CSI parameters
        case csiPrivate     // Got ESC[? (DEC private mode)
        case oscString      // Collecting OSC string
    }

    private var state: State = .ground
    private var csiParams: [Int] = []
    private var currentParam: Int = 0
    private var hasParam: Bool = false
    private var isPrivate: Bool = false
    private var oscPayload: String = ""

    // MARK: - Feed bytes

    /// Feed raw bytes from PTY output. Call from main thread.
    func feed(_ data: Data) {
        for byte in data {
            processByte(byte)
        }
    }

    private func processByte(_ byte: UInt8) {
        // Handle C0 control characters in any state
        if byte < 0x20 && state != .oscString {
            if handleControlChar(byte) { return }
        }

        switch state {
        case .ground:
            if byte == 0x1B { // ESC
                state = .escape
            } else if byte >= 0x20 {
                // Printable character — decode UTF-8 and put on screen
                feedPrintable(byte)
            }

        case .escape:
            handleEscape(byte)

        case .csiEntry, .csiParam, .csiPrivate:
            handleCSI(byte)

        case .oscString:
            handleOSC(byte)
        }
    }

    // MARK: - Control characters

    /// Returns true if the control char was handled and should not be processed further.
    private func handleControlChar(_ byte: UInt8) -> Bool {
        guard let screen = screen else { return false }
        switch byte {
        case 0x07: // BEL
            onBell?()
            if state == .oscString {
                dispatchOSC()
                state = .ground
            }
            return true
        case 0x08: // BS (backspace)
            screen.moveCursorBackward(1)
            return true
        case 0x09: // HT (horizontal tab)
            screen.horizontalTab()
            return true
        case 0x0A, 0x0B, 0x0C: // LF, VT, FF
            screen.lineFeed()
            return true
        case 0x0D: // CR
            screen.carriageReturn()
            return true
        case 0x1B: // ESC
            state = .escape
            return true
        default:
            return false
        }
    }

    // MARK: - Escape sequences

    private func handleEscape(_ byte: UInt8) {
        switch byte {
        case 0x5B: // [ → CSI
            state = .csiEntry
            resetCSI()
        case 0x5D: // ] → OSC
            state = .oscString
            oscPayload = ""
        case 0x4D: // M → Reverse Index (move cursor up, scroll if needed)
            screen?.reverseIndex()
            state = .ground
        case 0x37: // 7 → Save cursor (DECSC)
            saveCursor()
            state = .ground
        case 0x38: // 8 → Restore cursor (DECRC)
            restoreCursor()
            state = .ground
        case 0x63: // c → Full reset (RIS)
            fullReset()
            state = .ground
        default:
            state = .ground
        }
    }

    // MARK: - CSI sequences

    private func resetCSI() {
        csiParams = []
        currentParam = 0
        hasParam = false
        isPrivate = false
    }

    private func handleCSI(_ byte: UInt8) {
        switch byte {
        case 0x3F: // ? — DEC private mode prefix
            isPrivate = true
        case 0x30...0x39: // 0-9 — parameter digit
            hasParam = true
            currentParam = currentParam * 10 + Int(byte - 0x30)
        case 0x3B: // ; — parameter separator
            csiParams.append(hasParam ? currentParam : 0)
            currentParam = 0
            hasParam = false
        case 0x40...0x7E: // @ to ~ — final byte (command)
            if hasParam { csiParams.append(currentParam) }
            dispatchCSI(finalByte: byte)
            state = .ground
        default:
            // Intermediate bytes or unknown — ignore
            break
        }
    }

    private func dispatchCSI(finalByte: UInt8) {
        guard let screen = screen else { return }
        let p = csiParams
        let n = p.first ?? 1 // Default first param to 1

        if isPrivate {
            dispatchDECPrivate(finalByte: finalByte, params: p)
            return
        }

        switch finalByte {
        case 0x41: // A — CUU (cursor up)
            screen.moveCursorUp(max(1, n))
        case 0x42: // B — CUD (cursor down)
            screen.moveCursorDown(max(1, n))
        case 0x43: // C — CUF (cursor forward)
            screen.moveCursorForward(max(1, n))
        case 0x44: // D — CUB (cursor backward)
            screen.moveCursorBackward(max(1, n))
        case 0x48, 0x66: // H, f — CUP (cursor position)
            let row = max(1, p.count > 0 ? p[0] : 1) - 1
            let col = max(1, p.count > 1 ? p[1] : 1) - 1
            screen.moveCursorTo(row: row, col: col)
        case 0x4A: // J — ED (erase display)
            screen.eraseDisplay(mode: p.first ?? 0)
        case 0x4B: // K — EL (erase line)
            screen.eraseLine(mode: p.first ?? 0)
        case 0x4C: // L — IL (insert lines)
            screen.insertLines(max(1, n))
        case 0x4D: // M — DL (delete lines)
            screen.deleteLines(max(1, n))
        case 0x40: // @ — ICH (insert characters)
            screen.insertChars(max(1, n))
        case 0x50: // P — DCH (delete characters)
            screen.deleteChars(max(1, n))
        case 0x53: // S — SU (scroll up)
            screen.scrollUp(count: max(1, n))
        case 0x54: // T — SD (scroll down)
            screen.scrollDown(count: max(1, n))
        case 0x6D: // m — SGR (text attributes)
            if p.isEmpty {
                SGRParser.apply(params: [0], to: screen)
            } else {
                SGRParser.apply(params: p, to: screen)
            }
        case 0x72: // r — DECSTBM (set scroll region)
            let top = p.count > 0 ? p[0] : 1
            let bottom = p.count > 1 ? p[1] : screen.rows
            screen.setScrollRegion(top: top, bottom: bottom)
            screen.moveCursorTo(row: 0, col: 0)
        case 0x63: // c — DA1 (device attributes)
            onResponse?("\u{1b}[?62;22c".data(using: .utf8)!)
        case 0x6E: // n — DSR (device status report)
            if n == 6 {
                let response = "\u{1b}[\(screen.cursorRow + 1);\(screen.cursorCol + 1)R"
                onResponse?(response.data(using: .utf8)!)
            }
        case 0x64: // d — VPA (vertical position absolute)
            screen.moveCursorTo(row: max(1, n) - 1, col: screen.cursorCol)
        case 0x47: // G — CHA (cursor horizontal absolute)
            screen.moveCursorTo(row: screen.cursorRow, col: max(1, n) - 1)
        case 0x58: // X — ECH (erase characters)
            let count = max(1, n)
            for c in screen.cursorCol..<min(screen.cursorCol + count, screen.cols) {
                screen.grid[screen.cursorRow][c] = .blank
            }
            screen.dirtyRows.insert(screen.cursorRow)
        default:
            break
        }
    }

    // MARK: - DEC Private modes

    private func dispatchDECPrivate(finalByte: UInt8, params: [Int]) {
        let isSet = (finalByte == 0x68) // h = set, l = reset
        guard finalByte == 0x68 || finalByte == 0x6C else { return }

        for mode in params {
            switch mode {
            case 25: // DECTCEM — cursor visibility
                cursorVisible = isSet
            case 2004: // Bracketed paste
                bracketedPaste = isSet
            case 2026: // Synchronized output
                synchronizedOutput = isSet
            case 1049: // Alt screen buffer
                if isSet {
                    enterAltScreen()
                } else {
                    leaveAltScreen()
                }
            case 1: // DECCKM — cursor keys mode (application vs normal)
                break // TODO: implement when needed for arrow key handling
            case 12: // Cursor blink
                break
            default:
                break
            }
        }
    }

    // MARK: - Alt screen

    private func enterAltScreen() {
        guard let screen = screen, !altScreenActive else { return }
        altScreenActive = true
        savedMainScreen = screen.grid
        savedCursorRow = screen.cursorRow
        savedCursorCol = screen.cursorCol
        screen.eraseDisplay(mode: 2)
        screen.moveCursorTo(row: 0, col: 0)
    }

    private func leaveAltScreen() {
        guard let screen = screen, altScreenActive else { return }
        altScreenActive = false
        if let saved = savedMainScreen {
            for r in 0..<min(saved.count, screen.rows) {
                let row = saved[r]
                screen.grid[r] = Array(row.prefix(screen.cols))
                    + [Cell](repeating: .blank, count: max(0, screen.cols - row.count))
            }
        }
        screen.cursorRow = savedCursorRow
        screen.cursorCol = savedCursorCol
        savedMainScreen = nil
        screen.markAllDirty()
    }

    // MARK: - OSC sequences

    private func handleOSC(_ byte: UInt8) {
        if byte == 0x07 { // BEL terminates OSC
            dispatchOSC()
            state = .ground
        } else if byte == 0x1B {
            // ESC might start ST (ESC \) — simplified: treat ESC as terminator
            dispatchOSC()
            state = .escape
        } else if byte == 0x9C { // ST (String Terminator)
            dispatchOSC()
            state = .ground
        } else {
            oscPayload.append(Character(UnicodeScalar(byte)))
        }
    }

    private func dispatchOSC() {
        // Parse "N;text" format
        guard let sepIndex = oscPayload.firstIndex(of: ";") else { return }
        let codeStr = oscPayload[oscPayload.startIndex..<sepIndex]
        let text = String(oscPayload[oscPayload.index(after: sepIndex)...])

        guard let code = Int(codeStr) else { return }
        switch code {
        case 0, 2: // Set window title
            onTitleChange?(text)
        case 8: // Hyperlink — store but don't render yet
            break
        default:
            break
        }
    }

    // MARK: - Cursor save/restore

    private var savedCursorState: (row: Int, col: Int, fg: TermColor, bg: TermColor, attrs: CellAttributes)?

    private func saveCursor() {
        guard let screen = screen else { return }
        savedCursorState = (screen.cursorRow, screen.cursorCol, screen.currentFG, screen.currentBG, screen.currentAttrs)
    }

    private func restoreCursor() {
        guard let screen = screen, let saved = savedCursorState else { return }
        screen.moveCursorTo(row: saved.row, col: saved.col)
        screen.currentFG = saved.fg
        screen.currentBG = saved.bg
        screen.currentAttrs = saved.attrs
    }

    private func fullReset() {
        guard let screen = screen else { return }
        screen.eraseDisplay(mode: 2)
        screen.moveCursorTo(row: 0, col: 0)
        screen.resetScrollRegion()
        screen.currentAttrs = []
        screen.currentFG = .default
        screen.currentBG = .default
        cursorVisible = true
        cursorShape = .block
        bracketedPaste = false
        synchronizedOutput = false
        state = .ground
    }

    // MARK: - UTF-8 printable character handling

    private var utf8Buffer: [UInt8] = []
    private var utf8Expected: Int = 0

    private func feedPrintable(_ byte: UInt8) {
        if byte < 0x80 {
            // ASCII — emit directly
            screen?.putChar(Character(UnicodeScalar(byte)))
            return
        }

        if byte & 0xC0 == 0xC0 {
            // Start of multi-byte sequence
            utf8Buffer = [byte]
            if byte & 0xE0 == 0xC0 { utf8Expected = 2 }
            else if byte & 0xF0 == 0xE0 { utf8Expected = 3 }
            else if byte & 0xF8 == 0xF0 { utf8Expected = 4 }
            else { utf8Buffer = []; utf8Expected = 0 }
            return
        }

        if byte & 0xC0 == 0x80 && !utf8Buffer.isEmpty {
            // Continuation byte
            utf8Buffer.append(byte)
            if utf8Buffer.count == utf8Expected {
                if let str = String(bytes: utf8Buffer, encoding: .utf8),
                   let ch = str.first {
                    // NFC normalize for Vietnamese diacritics
                    let normalized = String(ch).precomposedStringWithCanonicalMapping
                    for c in normalized {
                        screen?.putChar(c)
                    }
                }
                utf8Buffer = []
                utf8Expected = 0
            }
            return
        }

        // Invalid byte — reset
        utf8Buffer = []
        utf8Expected = 0
    }
}
