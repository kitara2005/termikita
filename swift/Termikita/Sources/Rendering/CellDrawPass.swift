/// 3-pass cell renderer: backgrounds → glyphs → decorations.
///
/// Draws terminal grid content into the current NSGraphicsContext.
/// Uses GlyphAtlas for cached glyph rendering and ColorResolver
/// for theme-aware color resolution.

import AppKit

final class CellDrawPass {
    private let renderer: TextRenderer
    private let theme: ThemeColors
    private let glyphAtlas: GlyphAtlas

    init(renderer: TextRenderer, theme: ThemeColors) {
        self.renderer = renderer
        self.theme = theme
        self.glyphAtlas = GlyphAtlas(renderer: renderer, theme: theme)
    }

    /// Invalidate glyph cache (call on font or theme change).
    func invalidateCache() {
        glyphAtlas.invalidate()
    }

    /// Draw all visible lines into the current graphics context.
    func draw(
        lines: [[Cell]],
        in rect: NSRect,
        paddingX: CGFloat,
        paddingY: CGFloat,
        cursorRow: Int,
        cursorCol: Int,
        cursorVisible: Bool,
        cursorShape: CursorShape,
        cursorBlink: Bool,
        selection: (start: (Int, Int), end: (Int, Int))?
    ) {
        let cw = renderer.cellWidth
        let ch = renderer.cellHeight
        let baseline = renderer.baseline

        // Pass 1: Backgrounds
        drawBackgrounds(lines: lines, cw: cw, ch: ch, px: paddingX, py: paddingY, selection: selection)

        // Pass 2: Glyphs
        drawGlyphs(lines: lines, cw: cw, ch: ch, px: paddingX, py: paddingY, baseline: baseline)

        // Pass 3: Decorations (underline, strikethrough)
        drawDecorations(lines: lines, cw: cw, ch: ch, px: paddingX, py: paddingY)

        // Cursor
        if cursorVisible && !cursorBlink {
            drawCursor(row: cursorRow, col: cursorCol, shape: cursorShape,
                      cw: cw, ch: ch, px: paddingX, py: paddingY)
        }
    }

    // MARK: - Pass 1: Backgrounds

    private func drawBackgrounds(
        lines: [[Cell]], cw: CGFloat, ch: CGFloat,
        px: CGFloat, py: CGFloat,
        selection: (start: (Int, Int), end: (Int, Int))?
    ) {
        let defaultBG = ColorResolver.resolveNSColor(.default, theme: theme, isForeground: false)

        for (row, cells) in lines.enumerated() {
            let y = py + CGFloat(row) * ch

            // Batch consecutive cells with the same background color
            var batchStart = 0
            var batchColor = cellBGColor(cells.first ?? .blank)

            for (col, cell) in cells.enumerated() {
                let color = cellBGColor(cell)
                if color != batchColor {
                    // Flush batch
                    if batchColor != defaultBG {
                        batchColor.setFill()
                        let rect = NSRect(x: px + CGFloat(batchStart) * cw, y: y,
                                         width: CGFloat(col - batchStart) * cw, height: ch)
                        rect.fill()
                    }
                    batchStart = col
                    batchColor = color
                }
            }
            // Flush final batch
            if batchColor != defaultBG {
                batchColor.setFill()
                let rect = NSRect(x: px + CGFloat(batchStart) * cw, y: y,
                                 width: CGFloat(cells.count - batchStart) * cw, height: ch)
                rect.fill()
            }
        }

        // Selection highlight overlay
        if let sel = selection {
            drawSelectionHighlight(sel: sel, lineCount: lines.count,
                                  colCount: lines.first?.count ?? 0,
                                  cw: cw, ch: ch, px: px, py: py)
        }
    }

    private func cellBGColor(_ cell: Cell) -> NSColor {
        let (_, bg) = ColorResolver.resolvePair(
            fg: cell.fg, bg: cell.bg, reverse: cell.reverse, theme: theme
        )
        return bg
    }

    private func drawSelectionHighlight(
        sel: (start: (Int, Int), end: (Int, Int)),
        lineCount: Int, colCount: Int,
        cw: CGFloat, ch: CGFloat, px: CGFloat, py: CGFloat
    ) {
        var (r0, c0) = sel.start
        var (r1, c1) = sel.end
        if (r0, c0) > (r1, c1) { (r0, c0, r1, c1) = (r1, c1, r0, c0) }

        let selColor = NSColor(
            calibratedRed: CGFloat(theme.selection.0) / 255.0,
            green: CGFloat(theme.selection.1) / 255.0,
            blue: CGFloat(theme.selection.2) / 255.0,
            alpha: 0.4
        )
        selColor.setFill()

        for row in r0...min(r1, lineCount - 1) {
            let startCol = (row == r0) ? c0 : 0
            let endCol = (row == r1) ? c1 : colCount
            let rect = NSRect(
                x: px + CGFloat(startCol) * cw,
                y: py + CGFloat(row) * ch,
                width: CGFloat(endCol - startCol) * cw,
                height: ch
            )
            rect.fill()
        }
    }

    // MARK: - Pass 2: Glyphs

    private func drawGlyphs(
        lines: [[Cell]], cw: CGFloat, ch: CGFloat,
        px: CGFloat, py: CGFloat, baseline: CGFloat
    ) {
        for (row, cells) in lines.enumerated() {
            let y = py + CGFloat(row) * ch
            for (col, cell) in cells.enumerated() {
                guard cell.char != " " && !cell.placeholder else { continue }

                let x = px + CGFloat(col) * cw
                let entry = glyphAtlas.entry(for: cell)
                // Draw at baseline position (flipped coordinates)
                entry.attrString.draw(at: NSPoint(x: x, y: y + ch - baseline))
            }
        }
    }

    // MARK: - Pass 3: Decorations

    private func drawDecorations(
        lines: [[Cell]], cw: CGFloat, ch: CGFloat,
        px: CGFloat, py: CGFloat
    ) {
        for (row, cells) in lines.enumerated() {
            let y = py + CGFloat(row) * ch
            for (col, cell) in cells.enumerated() {
                let x = px + CGFloat(col) * cw
                let (fgColor, _) = ColorResolver.resolvePair(
                    fg: cell.fg, bg: cell.bg, reverse: cell.reverse, theme: theme
                )

                if cell.underline {
                    fgColor.setStroke()
                    let path = NSBezierPath()
                    path.lineWidth = 1.0
                    let underY = y + ch - 1.5
                    path.move(to: NSPoint(x: x, y: underY))
                    path.line(to: NSPoint(x: x + cw, y: underY))
                    path.stroke()
                }

                if cell.strikethrough {
                    fgColor.setStroke()
                    let path = NSBezierPath()
                    path.lineWidth = 1.0
                    let strikeY = y + ch * 0.5
                    path.move(to: NSPoint(x: x, y: strikeY))
                    path.line(to: NSPoint(x: x + cw, y: strikeY))
                    path.stroke()
                }
            }
        }
    }

    // MARK: - Cursor

    private func drawCursor(
        row: Int, col: Int, shape: CursorShape,
        cw: CGFloat, ch: CGFloat, px: CGFloat, py: CGFloat
    ) {
        let x = px + CGFloat(col) * cw
        let y = py + CGFloat(row) * ch
        let cursorColor = NSColor(
            calibratedRed: CGFloat(theme.cursor.0) / 255.0,
            green: CGFloat(theme.cursor.1) / 255.0,
            blue: CGFloat(theme.cursor.2) / 255.0,
            alpha: 1.0
        )

        switch shape {
        case .block:
            cursorColor.withAlphaComponent(0.5).setFill()
            NSRect(x: x, y: y, width: cw, height: ch).fill()
        case .underline:
            cursorColor.setFill()
            NSRect(x: x, y: y + ch - 2, width: cw, height: 2).fill()
        case .beam:
            cursorColor.setFill()
            NSRect(x: x, y: y, width: 2, height: ch).fill()
        }
    }
}
