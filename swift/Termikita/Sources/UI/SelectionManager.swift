/// Mouse selection tracking and clipboard operations.
///
/// Tracks selection start/end coordinates from mouse events.
/// Handles copy to pasteboard and paste from pasteboard (with bracketed paste).

import AppKit

final class SelectionManager {
    /// Selection endpoints (row, col). Nil when no selection active.
    var start: (row: Int, col: Int)?
    var end: (row: Int, col: Int)?

    /// Whether there is an active selection.
    var hasSelection: Bool {
        start != nil && end != nil && !tupleEqual(start, end)
    }

    /// Normalized selection bounds (start <= end).
    var normalizedBounds: (start: (Int, Int), end: (Int, Int))? {
        guard let s = start, let e = end, !tupleEqual(start, end) else { return nil }
        if (s.row, s.col) < (e.row, e.col) {
            return ((s.row, s.col), (e.row, e.col))
        }
        return ((e.row, e.col), (s.row, s.col))
    }

    /// Clear selection.
    func clear() {
        start = nil
        end = nil
    }

    // MARK: - Mouse tracking

    func mouseDown(row: Int, col: Int) {
        start = (row, col)
        end = nil
    }

    func mouseDragged(row: Int, col: Int) {
        end = (row, col)
    }

    func mouseUp(row: Int, col: Int) {
        // Collapse zero-length selection
        if let s = start, s.row == row && s.col == col {
            clear()
        }
    }

    // MARK: - Copy

    /// Extract selected text from visible lines and copy to pasteboard.
    func copySelection(from lines: [[Cell]]) {
        guard let bounds = normalizedBounds else { return }
        let (s, e) = bounds
        var parts: [String] = []

        for row in s.0...e.0 {
            guard row < lines.count else { break }
            let cells = lines[row]
            let colStart = (row == s.0) ? s.1 : 0
            let colEnd = (row == e.0) ? e.1 : cells.count
            let segment = cells[colStart..<min(colEnd, cells.count)]
                .map { String($0.char) }
                .joined()
                .replacingOccurrences(of: "\\s+$", with: "", options: .regularExpression)
            parts.append(segment)
        }

        let text = parts.joined(separator: "\n")
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
    }

    // MARK: - Paste

    /// Read text from pasteboard. Returns nil if no text available.
    static func pasteboardText() -> String? {
        NSPasteboard.general.string(forType: .string)
    }

    /// Select all visible lines.
    func selectAll(lineCount: Int, colCount: Int) {
        guard lineCount > 0 else { return }
        start = (0, 0)
        end = (lineCount - 1, colCount)
    }
}

/// Compare optional tuple coordinates.
private func tupleEqual(_ lhs: (row: Int, col: Int)?, _ rhs: (row: Int, col: Int)?) -> Bool {
    switch (lhs, rhs) {
    case (nil, nil): return true
    case let (l?, r?): return l.row == r.row && l.col == r.col
    default: return false
    }
}
