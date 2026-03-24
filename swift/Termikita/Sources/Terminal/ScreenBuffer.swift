/// 2D grid of terminal cells with cursor tracking and scroll region support.
///
/// Provides all grid operations: put character, cursor movement,
/// erase display/line, insert/delete lines, scroll up/down.
/// Uses top-left origin (row 0, col 0 = top-left corner).

import Foundation

final class ScreenBuffer {
    /// Grid dimensions.
    let cols: Int
    let rows: Int

    /// Cursor position (0-based).
    var cursorRow: Int = 0
    var cursorCol: Int = 0

    /// Scroll region (top/bottom inclusive, 0-based).
    var scrollTop: Int = 0
    var scrollBottom: Int

    /// Current text attributes applied to new characters.
    var currentAttrs: CellAttributes = []
    var currentFG: TermColor = .default
    var currentBG: TermColor = .default

    /// The cell grid — rows × cols.
    /// Internal access for VT100Parser (alt screen restore, ECH).
    var grid: [[Cell]]

    /// Dirty row tracking — set of row indices that changed since last clear.
    var dirtyRows: Set<Int> = []

    /// Callback invoked when a line scrolls off the top (for scrollback).
    var onLineScrolledOff: (([Cell]) -> Void)?

    init(cols: Int, rows: Int) {
        self.cols = cols
        self.rows = rows
        self.scrollBottom = rows - 1
        self.grid = Self.makeEmptyGrid(cols: cols, rows: rows)
    }

    // MARK: - Character output

    /// Write a character at the cursor position with current attributes.
    func putChar(_ ch: Character) {
        guard cursorRow >= 0 && cursorRow < rows else { return }

        // Auto-wrap: if cursor is past the last column, wrap to next line
        if cursorCol >= cols {
            cursorCol = 0
            cursorRow += 1
            if cursorRow > scrollBottom {
                scrollUp(count: 1)
                cursorRow = scrollBottom
            }
        }

        guard cursorCol < cols else { return }

        var cell = Cell.blank
        cell.char = ch
        cell.fg = currentFG
        cell.bg = currentBG
        cell.attrs = currentAttrs

        grid[cursorRow][cursorCol] = cell
        dirtyRows.insert(cursorRow)
        cursorCol += 1
    }

    // MARK: - Cursor movement

    func moveCursorTo(row: Int, col: Int) {
        cursorRow = clampRow(row)
        cursorCol = clampCol(col)
    }

    func moveCursorUp(_ n: Int) {
        cursorRow = max(scrollTop, cursorRow - max(1, n))
    }

    func moveCursorDown(_ n: Int) {
        cursorRow = min(scrollBottom, cursorRow + max(1, n))
    }

    func moveCursorForward(_ n: Int) {
        cursorCol = min(cols - 1, cursorCol + max(1, n))
    }

    func moveCursorBackward(_ n: Int) {
        cursorCol = max(0, cursorCol - max(1, n))
    }

    /// Carriage return — move cursor to column 0.
    func carriageReturn() {
        cursorCol = 0
    }

    /// Line feed — move cursor down, scroll if at bottom of scroll region.
    func lineFeed() {
        if cursorRow == scrollBottom {
            scrollUp(count: 1)
        } else if cursorRow < rows - 1 {
            cursorRow += 1
        }
    }

    /// Reverse index — move cursor up, scroll down if at top of scroll region.
    func reverseIndex() {
        if cursorRow == scrollTop {
            scrollDown(count: 1)
        } else if cursorRow > 0 {
            cursorRow -= 1
        }
    }

    // MARK: - Erase operations

    /// Erase display: 0=below cursor, 1=above cursor, 2=entire screen.
    func eraseDisplay(mode: Int) {
        switch mode {
        case 0: // Below cursor
            eraseLineRight()
            for r in (cursorRow + 1)..<rows {
                clearRow(r)
            }
        case 1: // Above cursor
            eraseLineLeft()
            for r in 0..<cursorRow {
                clearRow(r)
            }
        case 2: // Entire screen
            for r in 0..<rows {
                clearRow(r)
            }
        default:
            break
        }
    }

    /// Erase line: 0=right of cursor, 1=left of cursor, 2=entire line.
    func eraseLine(mode: Int) {
        switch mode {
        case 0: eraseLineRight()
        case 1: eraseLineLeft()
        case 2: clearRow(cursorRow)
        default: break
        }
    }

    private func eraseLineRight() {
        guard cursorRow >= 0 && cursorRow < rows else { return }
        for c in cursorCol..<cols {
            grid[cursorRow][c] = Cell.blank
        }
        dirtyRows.insert(cursorRow)
    }

    private func eraseLineLeft() {
        guard cursorRow >= 0 && cursorRow < rows else { return }
        for c in 0...min(cursorCol, cols - 1) {
            grid[cursorRow][c] = Cell.blank
        }
        dirtyRows.insert(cursorRow)
    }

    private func clearRow(_ row: Int) {
        guard row >= 0 && row < rows else { return }
        grid[row] = [Cell](repeating: .blank, count: cols)
        dirtyRows.insert(row)
    }

    // MARK: - Insert / Delete characters

    /// Insert n blank characters at cursor, shifting existing chars right.
    func insertChars(_ n: Int) {
        guard cursorRow >= 0 && cursorRow < rows else { return }
        let count = min(max(1, n), cols - cursorCol)
        var row = grid[cursorRow]
        row.insert(contentsOf: [Cell](repeating: .blank, count: count), at: cursorCol)
        row = Array(row.prefix(cols))
        grid[cursorRow] = row
        dirtyRows.insert(cursorRow)
    }

    /// Delete n characters at cursor, shifting remaining chars left.
    func deleteChars(_ n: Int) {
        guard cursorRow >= 0 && cursorRow < rows else { return }
        let count = min(max(1, n), cols - cursorCol)
        var row = grid[cursorRow]
        row.removeSubrange(cursorCol..<(cursorCol + count))
        row.append(contentsOf: [Cell](repeating: .blank, count: count))
        grid[cursorRow] = Array(row.prefix(cols))
        dirtyRows.insert(cursorRow)
    }

    // MARK: - Insert / Delete lines

    /// Insert n blank lines at cursor row within scroll region.
    func insertLines(_ n: Int) {
        let count = max(1, n)
        guard cursorRow >= scrollTop && cursorRow <= scrollBottom else { return }
        for _ in 0..<count {
            if scrollBottom < rows {
                grid.remove(at: scrollBottom)
            }
            grid.insert([Cell](repeating: .blank, count: cols), at: cursorRow)
        }
        markScrollRegionDirty()
    }

    /// Delete n lines at cursor row within scroll region.
    func deleteLines(_ n: Int) {
        let count = max(1, n)
        guard cursorRow >= scrollTop && cursorRow <= scrollBottom else { return }
        for _ in 0..<count {
            grid.remove(at: cursorRow)
            grid.insert([Cell](repeating: .blank, count: cols), at: scrollBottom)
        }
        markScrollRegionDirty()
    }

    // MARK: - Scrolling

    /// Scroll content up within scroll region. Top line pushed to scrollback.
    func scrollUp(count: Int) {
        for _ in 0..<max(1, count) {
            let scrolledLine = grid[scrollTop]
            onLineScrolledOff?(scrolledLine)
            grid.remove(at: scrollTop)
            grid.insert([Cell](repeating: .blank, count: cols), at: scrollBottom)
        }
        markScrollRegionDirty()
    }

    /// Scroll content down within scroll region.
    func scrollDown(count: Int) {
        for _ in 0..<max(1, count) {
            grid.remove(at: scrollBottom)
            grid.insert([Cell](repeating: .blank, count: cols), at: scrollTop)
        }
        markScrollRegionDirty()
    }

    /// Set scroll region (1-based top/bottom from DECSTBM, converted to 0-based).
    func setScrollRegion(top: Int, bottom: Int) {
        let t = max(0, top - 1)
        let b = min(rows - 1, bottom - 1)
        if t < b {
            scrollTop = t
            scrollBottom = b
        }
    }

    /// Reset scroll region to full screen.
    func resetScrollRegion() {
        scrollTop = 0
        scrollBottom = rows - 1
    }

    // MARK: - Tab stops

    /// Move cursor to the next tab stop (every 8 columns).
    func horizontalTab() {
        let nextTab = ((cursorCol / 8) + 1) * 8
        cursorCol = min(nextTab, cols - 1)
    }

    // MARK: - Helpers

    private func clampRow(_ r: Int) -> Int { max(0, min(rows - 1, r)) }
    private func clampCol(_ c: Int) -> Int { max(0, min(cols - 1, c)) }

    private func markScrollRegionDirty() {
        for r in scrollTop...scrollBottom {
            dirtyRows.insert(r)
        }
    }

    /// Clear dirty tracking (call after rendering).
    func clearDirty() {
        dirtyRows.removeAll()
    }

    /// Mark all rows dirty (full redraw needed).
    func markAllDirty() {
        dirtyRows = Set(0..<rows)
    }

    static func makeEmptyGrid(cols: Int, rows: Int) -> [[Cell]] {
        [[Cell]](repeating: [Cell](repeating: .blank, count: cols), count: rows)
    }
}
