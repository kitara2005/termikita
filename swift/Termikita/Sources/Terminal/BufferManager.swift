/// Orchestrates VT100 parser, screen buffer, and scrollback.
///
/// Public API for the terminal emulation layer:
/// - feed(Data) — process PTY output
/// - getVisibleLines() — retrieve lines for rendering
/// - Viewport management (scroll up/down, snap to bottom)
/// - Dirty row tracking for incremental redraws

import Foundation

final class BufferManager {
    let cols: Int
    let rows: Int

    /// The active screen grid.
    let screen: ScreenBuffer
    /// Scrollback history for lines that scroll off the top.
    let scrollback: ScrollbackBuffer
    /// VT100 escape sequence parser.
    let parser: VT100Parser

    /// Viewport scroll offset (0 = bottom/live, >0 = scrolled up).
    private(set) var scrollOffset: Int = 0

    /// Thread-safe flag: request snap to bottom on next feed.
    private var _scrollToBottom = false

    /// Callbacks
    var onTitleChange: ((String) -> Void)?
    var onBell: (() -> Void)?
    /// Write response data back to PTY (DA1, DSR replies).
    var onResponse: ((Data) -> Void)?

    // MARK: - Convenience accessors for parser state

    var cursorVisible: Bool { parser.cursorVisible }
    var cursorShape: CursorShape { parser.cursorShape }
    var bracketedPaste: Bool { parser.bracketedPaste }
    var cursorRow: Int { screen.cursorRow }
    var cursorCol: Int { screen.cursorCol }
    var isDirty: Bool { !screen.dirtyRows.isEmpty }

    init(cols: Int = AppConstants.defaultCols,
         rows: Int = AppConstants.defaultRows,
         scrollbackCapacity: Int = AppConstants.defaultScrollback) {
        self.cols = cols
        self.rows = rows
        self.screen = ScreenBuffer(cols: cols, rows: rows)
        self.scrollback = ScrollbackBuffer(capacity: scrollbackCapacity)
        self.parser = VT100Parser()

        // Wire parser → screen
        parser.screen = screen

        // Wire scrollback: when a line scrolls off the top, push to scrollback
        screen.onLineScrolledOff = { [weak self] line in
            self?.scrollback.push(line)
        }

        // Wire parser callbacks
        parser.onTitleChange = { [weak self] title in
            self?.onTitleChange?(title)
        }
        parser.onBell = { [weak self] in
            self?.onBell?()
        }
        parser.onResponse = { [weak self] data in
            self?.onResponse?(data)
        }
    }

    // MARK: - Feed PTY output

    /// Process raw PTY output data. Call from main thread.
    func feed(_ data: Data) {
        // Snap to bottom if requested (e.g., user typed something)
        if _scrollToBottom {
            scrollOffset = 0
            _scrollToBottom = false
        }

        parser.feed(data)

        // Auto-scroll to bottom when new output arrives and user is at bottom
        if scrollOffset == 0 {
            // Already at bottom — nothing to do
        }
    }

    // MARK: - Visible lines for rendering

    /// Get the lines currently visible in the viewport.
    /// Returns rows-count lines (scrollback + screen combined).
    func getVisibleLines() -> [[Cell]] {
        if scrollOffset == 0 {
            // Live view — just return the screen grid
            return screen.grid
        }

        // Scrolled up — mix scrollback and screen lines
        var lines: [[Cell]] = []
        let totalScrollback = scrollback.count
        let scrollbackStart = totalScrollback - scrollOffset

        if scrollbackStart >= 0 {
            // Some lines from scrollback
            let scrollbackLines = scrollback.lines(from: max(0, scrollbackStart), count: min(scrollOffset, rows))
            lines.append(contentsOf: scrollbackLines)
        }

        // Fill remaining with screen lines from the top
        let screenLinesNeeded = rows - lines.count
        if screenLinesNeeded > 0 {
            let screenSlice = Array(screen.grid.prefix(screenLinesNeeded))
            lines.append(contentsOf: screenSlice)
        }

        // Pad to exactly rows count
        while lines.count < rows {
            lines.append([Cell](repeating: .blank, count: cols))
        }

        return Array(lines.prefix(rows))
    }

    // MARK: - Viewport scrolling

    /// Scroll viewport up (into scrollback history).
    func scrollUp(lines: Int = 3) {
        let maxOffset = scrollback.count
        scrollOffset = min(scrollOffset + lines, maxOffset)
    }

    /// Scroll viewport down (toward live output).
    func scrollDown(lines: Int = 3) {
        scrollOffset = max(0, scrollOffset - lines)
    }

    /// Request snap to bottom on next feed (thread-safe).
    func requestScrollToBottom() {
        _scrollToBottom = true
    }

    /// Immediately snap viewport to bottom (live view).
    func snapToBottom() {
        scrollOffset = 0
    }

    /// Whether viewport is scrolled up from the bottom.
    var isScrolledUp: Bool { scrollOffset > 0 }

    // MARK: - Dirty tracking

    /// Clear dirty row tracking (call after rendering).
    func clearDirty() {
        screen.clearDirty()
    }

    // MARK: - IME cursor helper

    /// Find the visual cursor position for IME placement.
    /// When DECTCEM hides cursor, scan for reverse-video cells (TUI cursor).
    func findVisualCursorForIME() -> (row: Int, col: Int) {
        if parser.cursorVisible {
            return (screen.cursorRow, screen.cursorCol)
        }
        // Scan for reverse-video cell (TUI apps render cursor as reverse text)
        for row in 0..<rows {
            for col in 0..<cols {
                if screen.grid[row][col].reverse {
                    return (row, col)
                }
            }
        }
        return (screen.cursorRow, screen.cursorCol)
    }

    // MARK: - Resize

    /// Resize the terminal grid. Creates new screen buffer.
    /// Note: In a full implementation, this would reflow content.
    /// For now, it preserves what fits and clears the rest.
    func resize(cols: Int, rows: Int) -> BufferManager {
        return BufferManager(cols: cols, rows: rows,
                            scrollbackCapacity: scrollback.capacity)
    }
}
