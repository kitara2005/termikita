/// LRU glyph cache for fast repeated character rendering.
///
/// Keys on (Character, bold, italic) → cached NSAttributedString.
/// Evicts least-recently-used entries when capacity exceeded.

import AppKit

final class GlyphAtlas {
    /// Cache entry — attributed string ready for drawing.
    struct Entry {
        let attrString: NSAttributedString
        let advanceWidth: CGFloat
    }

    /// Cache key — character + style flags.
    struct Key: Hashable {
        let char: Character
        let bold: Bool
        let italic: Bool
    }

    private var cache: [Key: Entry] = [:]
    private var accessOrder: [Key] = []  // LRU: most recent at end
    private let capacity: Int
    private let renderer: TextRenderer
    private let theme: ThemeColors

    init(renderer: TextRenderer, theme: ThemeColors, capacity: Int = 8192) {
        self.renderer = renderer
        self.theme = theme
        self.capacity = capacity
    }

    /// Get or create a cached attributed string for a cell.
    func entry(for cell: Cell) -> Entry {
        let key = Key(char: cell.char, bold: cell.bold, italic: cell.italic)

        if let existing = cache[key] {
            // Move to end of access order (most recently used)
            if let idx = accessOrder.firstIndex(of: key) {
                accessOrder.remove(at: idx)
            }
            accessOrder.append(key)
            return existing
        }

        // Create new entry
        let font = renderer.font(bold: cell.bold, italic: cell.italic)
        let fgColor = ColorResolver.resolveNSColor(cell.fg, theme: theme, isForeground: true)

        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: fgColor,
        ]
        let attrStr = NSAttributedString(string: String(cell.char), attributes: attrs)

        // Measure advance width
        let line = CTLineCreateWithAttributedString(attrStr)
        var ascent: CGFloat = 0, descent: CGFloat = 0, leading: CGFloat = 0
        let width = CTLineGetTypographicBounds(line, &ascent, &descent, &leading)

        let entry = Entry(attrString: attrStr, advanceWidth: CGFloat(width))

        // Evict if at capacity
        if cache.count >= capacity, let oldest = accessOrder.first {
            accessOrder.removeFirst()
            cache.removeValue(forKey: oldest)
        }

        cache[key] = entry
        accessOrder.append(key)
        return entry
    }

    /// Invalidate all cached glyphs (call on font or theme change).
    func invalidate() {
        cache.removeAll()
        accessOrder.removeAll()
    }
}
