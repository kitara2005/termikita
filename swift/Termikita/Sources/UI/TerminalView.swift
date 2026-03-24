/// NSView subclass for terminal display and keyboard input.
///
/// Connects PTYManager + BufferManager + CellDrawPass into a working terminal.
/// Handles: 60fps refresh, cursor blink, keyboard input, mouse selection,
/// scroll wheel, window resize, copy/paste, I-beam cursor.
/// Uses isFlipped=true (top-left origin) so row 0 is at y=0.

import AppKit

final class TerminalView: NSView, NSTextInputClient {
    // Core components
    private(set) var pty: PTYManager!
    private(set) var buffer: BufferManager!
    private(set) var renderer: TextRenderer!
    private var drawPass: CellDrawPass!
    private var selection = SelectionManager()
    var themeColors = ThemeColors()

    // IME (Input Method Editor) state
    private var markedText: String?
    private var _markedRange: NSRange = NSRange(location: NSNotFound, length: 0)
    private var selectedIMERange: NSRange = NSRange(location: 0, length: 0)

    // Timers
    private var refreshTimer: Timer?
    private var cursorBlinkTimer: Timer?
    private var cursorBlinkOn = true

    // Resize debounce
    private var resizeTimer: Timer?
    private var pendingCols = 0
    private var pendingRows = 0

    // Callback for font changes from NSFontPanel
    var onFontChange: ((String, CGFloat) -> Void)?

    // MARK: - Init

    override init(frame: NSRect) {
        super.init(frame: frame)
        setup()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setup()
    }

    private func setup() {
        renderer = TextRenderer()
        drawPass = CellDrawPass(renderer: renderer, theme: themeColors)

        let (cw, ch) = renderer.getCellDimensions()
        let usableW = bounds.width - AppConstants.terminalPaddingX * 2
        let usableH = bounds.height - AppConstants.terminalPaddingY * 2
        let cols = max(1, Int(usableW / cw))
        let rows = max(1, Int(usableH / ch))

        buffer = BufferManager(cols: cols, rows: rows)
        pty = PTYManager(cols: cols, rows: rows)

        // Wire PTY output → buffer → redraw
        pty.onOutput = { [weak self] data in
            self?.buffer.feed(data)
        }
        pty.onExit = { [weak self] _ in
            self?.handlePTYExit()
        }

        // Wire buffer responses → PTY (DA1, DSR)
        buffer.onResponse = { [weak self] data in
            self?.pty.write(data)
        }

        startTimers()
    }

    /// Replace session components (used by TabController).
    func replaceSession(pty: PTYManager, buffer: BufferManager,
                        renderer: TextRenderer, theme: ThemeColors) {
        stopTimers()
        self.pty = pty
        self.buffer = buffer
        self.renderer = renderer
        self.themeColors = theme
        self.drawPass = CellDrawPass(renderer: renderer, theme: theme)
        startTimers()
        needsDisplay = true
    }

    // MARK: - NSView overrides

    override var isFlipped: Bool { true }
    override var isOpaque: Bool { true }
    override var acceptsFirstResponder: Bool { true }
    override func becomeFirstResponder() -> Bool { true }

    override func resetCursorRects() {
        addCursorRect(bounds, cursor: .iBeam)
    }

    // MARK: - Drawing

    override func draw(_ dirtyRect: NSRect) {
        // Fill background
        let bgColor = NSColor(
            calibratedRed: CGFloat(themeColors.background.0) / 255.0,
            green: CGFloat(themeColors.background.1) / 255.0,
            blue: CGFloat(themeColors.background.2) / 255.0,
            alpha: 1.0
        )
        bgColor.setFill()
        bounds.fill()

        let lines = buffer.getVisibleLines()

        drawPass.draw(
            lines: lines,
            in: bounds,
            paddingX: AppConstants.terminalPaddingX,
            paddingY: AppConstants.terminalPaddingY,
            cursorRow: buffer.cursorRow,
            cursorCol: buffer.cursorCol,
            cursorVisible: buffer.cursorVisible && !buffer.isScrolledUp,
            cursorShape: buffer.cursorShape,
            cursorBlink: cursorBlinkOn,
            selection: selection.normalizedBounds
        )
    }

    // MARK: - Timers

    func startTimers() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 1.0/60.0, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            if self.buffer.isDirty {
                self.buffer.clearDirty()
                self.needsDisplay = true
            }
        }
        cursorBlinkTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.cursorBlinkOn.toggle()
            self.needsDisplay = true
        }
    }

    func stopTimers() {
        refreshTimer?.invalidate()
        refreshTimer = nil
        cursorBlinkTimer?.invalidate()
        cursorBlinkTimer = nil
    }

    // MARK: - Keyboard input

    override func keyDown(with event: NSEvent) {
        let mods = event.modifierFlags

        // Cmd+key shortcuts — bypass IME
        if mods.contains(.command) {
            handleCmdShortcut(event)
            return
        }

        // Scroll-to-bottom on input
        buffer.requestScrollToBottom()

        // Ctrl+letter → control character
        if mods.contains(.control), let chars = event.characters, chars.count == 1 {
            let ch = chars.lowercased().first!
            if ch >= "a" && ch <= "z" {
                let code = UInt8(ch.asciiValue! - Character("a").asciiValue! + 1)
                pty.write(Data([code]))
                return
            }
        }

        // Special keys (arrows, function keys, etc.)
        if let seq = KeyMap.escapeSequence(for: event.keyCode) {
            // If IME is composing, handle backspace specially
            if hasMarkedText() {
                if event.keyCode == 0x33 { // Backspace during composition
                    // Let IME shorten the marked text (e.g., "việ" + BS → "vi")
                    inputContext?.handleEvent(event)
                    return
                }
                // Other special keys: commit marked text, then send key
                if let marked = markedText {
                    let normalized = marked.precomposedStringWithCanonicalMapping
                    if let data = normalized.data(using: .utf8) {
                        pty.write(data)
                    }
                }
                markedText = nil
                _markedRange = NSRange(location: NSNotFound, length: 0)
                inputContext?.discardMarkedText()
            }
            pty.write(seq)
            return
        }

        // Route through NSTextInputContext for proper IME composition
        // This is CRITICAL — using interpretKeyEvents would bypass IME lifecycle
        inputContext?.handleEvent(event)
    }

    override func doCommand(by selector: Selector) {
        // Swallow unhandled commands (prevents beep)
    }

    private func handleCmdShortcut(_ event: NSEvent) {
        guard let chars = event.charactersIgnoringModifiers, let key = chars.first else { return }
        let hasShift = event.modifierFlags.contains(.shift)

        switch key.lowercased().first {
        case "c":
            if selection.hasSelection {
                selection.copySelection(from: buffer.getVisibleLines())
            } else {
                pty.write(Data([0x03])) // Ctrl+C
            }
        case "v":
            pasteClipboard()
        case "a":
            selection.selectAll(lineCount: buffer.rows, colCount: buffer.cols)
            needsDisplay = true
        case "k":
            pty.write(Data([0x0C])) // Clear (form feed)
        case "]" where hasShift:
            break // Phase 07: next tab
        case "[" where hasShift:
            break // Phase 07: prev tab
        default:
            break
        }
    }

    private func pasteClipboard() {
        guard let text = SelectionManager.pasteboardText() else { return }
        let normalized = text.precomposedStringWithCanonicalMapping
        guard var data = normalized.data(using: .utf8) else { return }
        if buffer.bracketedPaste {
            data = "\u{1b}[200~".data(using: .utf8)! + data + "\u{1b}[201~".data(using: .utf8)!
        }
        pty.write(data)
    }

    // MARK: - NSTextInputClient — full Vietnamese IME support

    /// IME commits final composed text (or regular key character input).
    func insertText(_ string: Any, replacementRange: NSRange) {
        let text: String
        if let attrStr = string as? NSAttributedString {
            text = attrStr.string
        } else if let str = string as? String {
            text = str
        } else { return }

        markedText = nil
        _markedRange = NSRange(location: NSNotFound, length: 0)

        let normalized = text.precomposedStringWithCanonicalMapping
        if let data = normalized.data(using: .utf8), !data.isEmpty {
            buffer.requestScrollToBottom()
            pty.write(data)
        }
        needsDisplay = true
    }

    /// Called while IME is composing — store marked text for overlay display.
    func setMarkedText(_ string: Any, selectedRange: NSRange, replacementRange: NSRange) {
        if let attrStr = string as? NSAttributedString {
            markedText = attrStr.string.isEmpty ? nil : attrStr.string
        } else if let str = string as? String {
            markedText = str.isEmpty ? nil : str
        } else {
            markedText = nil
        }

        if let marked = markedText {
            _markedRange = NSRange(location: 0, length: marked.count)
        } else {
            _markedRange = NSRange(location: NSNotFound, length: 0)
        }
        selectedIMERange = selectedRange
        needsDisplay = true
    }

    /// Cancel/commit any in-progress IME composition.
    func unmarkText() {
        markedText = nil
        _markedRange = NSRange(location: NSNotFound, length: 0)
        needsDisplay = true
    }

    func hasMarkedText() -> Bool {
        markedText != nil
    }

    func markedRange() -> NSRange {
        _markedRange
    }

    func selectedRange() -> NSRange {
        selectedIMERange
    }

    /// Return screen rect for IME candidate window placement near cursor.
    func firstRect(forCharacterRange range: NSRange, actualRange: NSRangePointer?) -> NSRect {
        let (imeRow, imeCol) = buffer.findVisualCursorForIME()
        let x = AppConstants.terminalPaddingX + CGFloat(imeCol) * renderer.cellWidth
        let y = AppConstants.terminalPaddingY + CGFloat(imeRow) * renderer.cellHeight
        let rect = NSRect(x: x, y: y, width: 0, height: renderer.cellHeight)
        // Convert to screen coordinates
        let windowRect = convert(rect, to: nil)
        return window?.convertToScreen(windowRect) ?? rect
    }

    func attributedSubstring(forProposedRange range: NSRange, actualRange: NSRangePointer?) -> NSAttributedString? {
        nil
    }

    func characterIndex(for point: NSPoint) -> Int {
        0
    }

    func validAttributesForMarkedText() -> [NSAttributedString.Key] {
        []
    }

    // MARK: - Mouse events

    override func mouseDown(with event: NSEvent) {
        let (row, col) = cellPosition(from: event)
        selection.mouseDown(row: row, col: col)
        needsDisplay = true
    }

    override func mouseDragged(with event: NSEvent) {
        let (row, col) = cellPosition(from: event)
        selection.mouseDragged(row: row, col: col)
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        let (row, col) = cellPosition(from: event)
        selection.mouseUp(row: row, col: col)
        needsDisplay = true
    }

    private func cellPosition(from event: NSEvent) -> (Int, Int) {
        let point = convert(event.locationInWindow, from: nil)
        let col = max(0, Int((point.x - AppConstants.terminalPaddingX) / renderer.cellWidth))
        let row = max(0, Int((point.y - AppConstants.terminalPaddingY) / renderer.cellHeight))
        return (row, col)
    }

    // MARK: - Scroll wheel

    override func scrollWheel(with event: NSEvent) {
        let delta = event.scrollingDeltaY
        if delta > 0 {
            buffer.scrollUp(lines: max(1, Int(delta)))
        } else if delta < 0 {
            buffer.scrollDown(lines: max(1, Int(-delta)))
        }
        needsDisplay = true
    }

    // MARK: - Resize

    override func setFrameSize(_ newSize: NSSize) {
        super.setFrameSize(newSize)
        guard renderer != nil else { return }

        let (cw, ch) = renderer.getCellDimensions()
        guard cw > 0, ch > 0 else { return }
        let newCols = max(1, Int((newSize.width - AppConstants.terminalPaddingX * 2) / cw))
        let newRows = max(1, Int((newSize.height - AppConstants.terminalPaddingY * 2) / ch))

        if newCols != buffer.cols || newRows != buffer.rows {
            // Recreate buffer with new size
            let newBuffer = buffer.resize(cols: newCols, rows: newRows)
            // Rewire
            newBuffer.onResponse = { [weak self] data in self?.pty.write(data) }
            self.buffer = newBuffer
            // Debounce PTY resize
            pendingCols = newCols
            pendingRows = newRows
            resizeTimer?.invalidate()
            resizeTimer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: false) { [weak self] _ in
                self?.pty.resize(cols: self?.pendingCols ?? 80, rows: self?.pendingRows ?? 24)
            }
        }
        needsDisplay = true
    }

    // MARK: - PTY exit

    private func handlePTYExit() {
        stopTimers()
        // Notify parent (TabController will close this tab)
    }

    // MARK: - Cleanup

    deinit {
        stopTimers()
    }
}
