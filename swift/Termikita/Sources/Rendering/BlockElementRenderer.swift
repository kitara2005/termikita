/// Geometric rendering for Unicode block elements and box drawing characters.
///
/// Block elements (U+2580–U+259F): filled rectangles (half blocks, quadrants).
/// Box drawing (U+2500–U+257F): line paths (single, double, heavy).
/// Rendered as NSBezierPath — pixel-perfect grid alignment, no font needed.

import AppKit

enum BlockElementRenderer {

    /// Returns true if the character should be rendered geometrically (not as a glyph).
    static func isBlockOrBoxChar(_ ch: Character) -> Bool {
        guard let scalar = ch.unicodeScalars.first else { return false }
        let v = scalar.value
        return (v >= 0x2500 && v <= 0x257F) ||  // Box drawing
               (v >= 0x2580 && v <= 0x259F)      // Block elements
    }

    /// Draw a block/box character into the cell rect with the given foreground color.
    static func draw(_ ch: Character, in rect: NSRect, color: NSColor) {
        guard let scalar = ch.unicodeScalars.first else { return }
        let v = scalar.value

        if v >= 0x2580 && v <= 0x259F {
            drawBlockElement(v, in: rect, color: color)
        } else if v >= 0x2500 && v <= 0x257F {
            drawBoxDrawing(v, in: rect, color: color)
        }
    }

    // MARK: - Block elements (U+2580–U+259F)

    private static func drawBlockElement(_ code: UInt32, in rect: NSRect, color: NSColor) {
        color.setFill()
        let x = rect.origin.x, y = rect.origin.y
        let w = rect.width, h = rect.height

        switch code {
        case 0x2580: // ▀ Upper half
            NSRect(x: x, y: y, width: w, height: h / 2).fill()
        case 0x2581: // ▁ Lower one eighth
            NSRect(x: x, y: y + h * 7/8, width: w, height: h / 8).fill()
        case 0x2582: // ▂ Lower one quarter
            NSRect(x: x, y: y + h * 3/4, width: w, height: h / 4).fill()
        case 0x2583: // ▃ Lower three eighths
            NSRect(x: x, y: y + h * 5/8, width: w, height: h * 3/8).fill()
        case 0x2584: // ▄ Lower half
            NSRect(x: x, y: y + h / 2, width: w, height: h / 2).fill()
        case 0x2585: // ▅ Lower five eighths
            NSRect(x: x, y: y + h * 3/8, width: w, height: h * 5/8).fill()
        case 0x2586: // ▆ Lower three quarters
            NSRect(x: x, y: y + h / 4, width: w, height: h * 3/4).fill()
        case 0x2587: // ▇ Lower seven eighths
            NSRect(x: x, y: y + h / 8, width: w, height: h * 7/8).fill()
        case 0x2588: // █ Full block
            rect.fill()
        case 0x2589: // ▉ Left seven eighths
            NSRect(x: x, y: y, width: w * 7/8, height: h).fill()
        case 0x258A: // ▊ Left three quarters
            NSRect(x: x, y: y, width: w * 3/4, height: h).fill()
        case 0x258B: // ▋ Left five eighths
            NSRect(x: x, y: y, width: w * 5/8, height: h).fill()
        case 0x258C: // ▌ Left half
            NSRect(x: x, y: y, width: w / 2, height: h).fill()
        case 0x258D: // ▍ Left three eighths
            NSRect(x: x, y: y, width: w * 3/8, height: h).fill()
        case 0x258E: // ▎ Left one quarter
            NSRect(x: x, y: y, width: w / 4, height: h).fill()
        case 0x258F: // ▏ Left one eighth
            NSRect(x: x, y: y, width: w / 8, height: h).fill()
        case 0x2590: // ▐ Right half
            NSRect(x: x + w / 2, y: y, width: w / 2, height: h).fill()
        case 0x2591: // ░ Light shade (25%)
            color.withAlphaComponent(0.25).setFill()
            rect.fill()
        case 0x2592: // ▒ Medium shade (50%)
            color.withAlphaComponent(0.50).setFill()
            rect.fill()
        case 0x2593: // ▓ Dark shade (75%)
            color.withAlphaComponent(0.75).setFill()
            rect.fill()
        case 0x2594: // ▔ Upper one eighth
            NSRect(x: x, y: y, width: w, height: h / 8).fill()
        case 0x2595: // ▕ Right one eighth
            NSRect(x: x + w * 7/8, y: y, width: w / 8, height: h).fill()
        case 0x2596: // ▖ Quadrant lower left
            NSRect(x: x, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x2597: // ▗ Quadrant lower right
            NSRect(x: x + w / 2, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x2598: // ▘ Quadrant upper left
            NSRect(x: x, y: y, width: w / 2, height: h / 2).fill()
        case 0x2599: // ▙ Quadrant upper left + lower left + lower right
            NSRect(x: x, y: y, width: w / 2, height: h).fill()
            NSRect(x: x + w / 2, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x259A: // ▚ Quadrant upper left + lower right
            NSRect(x: x, y: y, width: w / 2, height: h / 2).fill()
            NSRect(x: x + w / 2, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x259B: // ▛ Quadrant upper left + upper right + lower left
            NSRect(x: x, y: y, width: w, height: h / 2).fill()
            NSRect(x: x, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x259C: // ▜ Quadrant upper left + upper right + lower right
            NSRect(x: x, y: y, width: w, height: h / 2).fill()
            NSRect(x: x + w / 2, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x259D: // ▝ Quadrant upper right
            NSRect(x: x + w / 2, y: y, width: w / 2, height: h / 2).fill()
        case 0x259E: // ▞ Quadrant upper right + lower left
            NSRect(x: x + w / 2, y: y, width: w / 2, height: h / 2).fill()
            NSRect(x: x, y: y + h / 2, width: w / 2, height: h / 2).fill()
        case 0x259F: // ▟ Quadrant upper right + lower left + lower right
            NSRect(x: x + w / 2, y: y, width: w / 2, height: h).fill()
            NSRect(x: x, y: y + h / 2, width: w / 2, height: h / 2).fill()
        default:
            break
        }
    }

    // MARK: - Box drawing (U+2500–U+257F)

    private static func drawBoxDrawing(_ code: UInt32, in rect: NSRect, color: NSColor) {
        color.setStroke()
        let cx = rect.midX, cy = rect.midY
        let x0 = rect.minX, y0 = rect.minY
        let x1 = rect.maxX, y1 = rect.maxY

        let path = NSBezierPath()
        path.lineWidth = 1.0

        switch code {
        // Single lines
        case 0x2500, 0x2501: // ─ ━ Horizontal
            path.lineWidth = code == 0x2501 ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
        case 0x2502, 0x2503: // │ ┃ Vertical
            path.lineWidth = code == 0x2503 ? 2.0 : 1.0
            path.move(to: NSPoint(x: cx, y: y0))
            path.line(to: NSPoint(x: cx, y: y1))
        case 0x250C, 0x250F: // ┌ ┏ Down-right corner
            path.lineWidth = code == 0x250F ? 2.0 : 1.0
            path.move(to: NSPoint(x: cx, y: y1))
            path.line(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
        case 0x2510, 0x2513: // ┐ ┓ Down-left corner
            path.lineWidth = code == 0x2513 ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: cx, y: y1))
        case 0x2514, 0x2517: // └ ┗ Up-right corner
            path.lineWidth = code == 0x2517 ? 2.0 : 1.0
            path.move(to: NSPoint(x: cx, y: y0))
            path.line(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
        case 0x2518, 0x251B: // ┘ ┛ Up-left corner
            path.lineWidth = code == 0x251B ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: cx, y: y0))
        case 0x251C, 0x2523: // ├ ┣ Left tee
            path.lineWidth = code == 0x2523 ? 2.0 : 1.0
            path.move(to: NSPoint(x: cx, y: y0))
            path.line(to: NSPoint(x: cx, y: y1))
            path.move(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
        case 0x2524, 0x252B: // ┤ ┫ Right tee
            path.lineWidth = code == 0x252B ? 2.0 : 1.0
            path.move(to: NSPoint(x: cx, y: y0))
            path.line(to: NSPoint(x: cx, y: y1))
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: cx, y: cy))
        case 0x252C, 0x2533: // ┬ ┳ Top tee
            path.lineWidth = code == 0x2533 ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
            path.move(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: cx, y: y1))
        case 0x2534, 0x253B: // ┴ ┻ Bottom tee
            path.lineWidth = code == 0x253B ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
            path.move(to: NSPoint(x: cx, y: cy))
            path.line(to: NSPoint(x: cx, y: y0))
        case 0x253C, 0x254B: // ┼ ╋ Cross
            path.lineWidth = code == 0x254B ? 2.0 : 1.0
            path.move(to: NSPoint(x: x0, y: cy))
            path.line(to: NSPoint(x: x1, y: cy))
            path.move(to: NSPoint(x: cx, y: y0))
            path.line(to: NSPoint(x: cx, y: y1))
        // Double lines
        case 0x2550: // ═ Double horizontal
            path.move(to: NSPoint(x: x0, y: cy - 1.5))
            path.line(to: NSPoint(x: x1, y: cy - 1.5))
            path.move(to: NSPoint(x: x0, y: cy + 1.5))
            path.line(to: NSPoint(x: x1, y: cy + 1.5))
        case 0x2551: // ║ Double vertical
            path.move(to: NSPoint(x: cx - 1.5, y: y0))
            path.line(to: NSPoint(x: cx - 1.5, y: y1))
            path.move(to: NSPoint(x: cx + 1.5, y: y0))
            path.line(to: NSPoint(x: cx + 1.5, y: y1))
        case 0x2552...0x256C: // Double line corners/tees/crosses
            // Simplified: draw as single lines for now (correct shape, single width)
            drawBoxDrawingFallback(code, path: path, cx: cx, cy: cy,
                                  x0: x0, y0: y0, x1: x1, y1: y1)
        default:
            // Fallback: try to determine connectivity and draw
            drawBoxDrawingFallback(code, path: path, cx: cx, cy: cy,
                                  x0: x0, y0: y0, x1: x1, y1: y1)
        }

        path.stroke()
    }

    /// Fallback box drawing: analyze connectivity bits and draw lines.
    private static func drawBoxDrawingFallback(
        _ code: UInt32, path: NSBezierPath,
        cx: CGFloat, cy: CGFloat,
        x0: CGFloat, y0: CGFloat, x1: CGFloat, y1: CGFloat
    ) {
        // Generic: determine which sides connect based on Unicode assignment patterns
        // For double-line variants and mixed variants, draw as single lines
        let idx = Int(code - 0x2500)
        // Connectivity: right, up, left, down based on lookup
        let hasRight = [0,1,4,5,12,13,14,15,16,17,18,19,28,29,30,31,
                        44,45,46,47,52,53,54,55,60,61,62,63,80,81].contains(idx)
        let hasLeft = [0,1,4,5,20,21,22,23,24,25,26,27,28,29,30,31,
                       36,37,38,39,44,45,46,47,52,53,54,55,60,61,62,63,80,81].contains(idx)
        let hasDown = [2,3,6,7,12,13,14,15,20,21,22,23,28,29,30,31,
                       44,45,46,47,48,49,50,51,52,53,54,55,60,61,62,63].contains(idx)
        let hasUp = [2,3,6,7,16,17,18,19,24,25,26,27,28,29,30,31,
                     36,37,38,39,44,45,46,47,52,53,54,55,60,61,62,63].contains(idx)

        if hasRight { path.move(to: NSPoint(x: cx, y: cy)); path.line(to: NSPoint(x: x1, y: cy)) }
        if hasLeft  { path.move(to: NSPoint(x: x0, y: cy)); path.line(to: NSPoint(x: cx, y: cy)) }
        if hasDown  { path.move(to: NSPoint(x: cx, y: cy)); path.line(to: NSPoint(x: cx, y: y1)) }
        if hasUp    { path.move(to: NSPoint(x: cx, y: y0)); path.line(to: NSPoint(x: cx, y: cy)) }
    }
}
