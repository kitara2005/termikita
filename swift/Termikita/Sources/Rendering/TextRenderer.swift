/// Font loading, cell metrics, and bold/italic variant derivation.
///
/// Wraps NSFont and provides cell dimensions used by the terminal grid
/// layout. Derives bold/italic variants via NSFontManager.

import AppKit

final class TextRenderer {
    /// Primary monospace font.
    private(set) var primaryFont: NSFont
    /// Bold variant.
    private(set) var boldFont: NSFont
    /// Italic variant.
    private(set) var italicFont: NSFont
    /// Bold+Italic variant.
    private(set) var boldItalicFont: NSFont

    /// Cell dimensions in points.
    private(set) var cellWidth: CGFloat = 0
    private(set) var cellHeight: CGFloat = 0
    private(set) var baseline: CGFloat = 0

    init(family: String = AppConstants.defaultFontFamily,
         size: CGFloat = AppConstants.defaultFontSize) {
        // Load primary font, fallback to Menlo
        let font = NSFont(name: family, size: size)
            ?? NSFont(name: "Menlo", size: size)
            ?? NSFont.monospacedSystemFont(ofSize: size, weight: .regular)
        self.primaryFont = font

        let fm = NSFontManager.shared
        self.boldFont = fm.convert(font, toHaveTrait: .boldFontMask)
        self.italicFont = fm.convert(font, toHaveTrait: .italicFontMask)
        self.boldItalicFont = fm.convert(
            fm.convert(font, toHaveTrait: .boldFontMask),
            toHaveTrait: .italicFontMask
        )

        calculateMetrics()
    }

    /// Update font family and size, recalculate all metrics.
    func setFont(family: String, size: CGFloat) {
        let font = NSFont(name: family, size: size)
            ?? NSFont(name: "Menlo", size: size)
            ?? NSFont.monospacedSystemFont(ofSize: size, weight: .regular)
        self.primaryFont = font

        let fm = NSFontManager.shared
        self.boldFont = fm.convert(font, toHaveTrait: .boldFontMask)
        self.italicFont = fm.convert(font, toHaveTrait: .italicFontMask)
        self.boldItalicFont = fm.convert(
            fm.convert(font, toHaveTrait: .boldFontMask),
            toHaveTrait: .italicFontMask
        )

        calculateMetrics()
    }

    /// Select the correct font variant for given attributes.
    func font(bold: Bool, italic: Bool) -> NSFont {
        switch (bold, italic) {
        case (true, true):   return boldItalicFont
        case (true, false):  return boldFont
        case (false, true):  return italicFont
        case (false, false): return primaryFont
        }
    }

    /// Get cell dimensions as a tuple.
    func getCellDimensions() -> (width: CGFloat, height: CGFloat) {
        (cellWidth, cellHeight)
    }

    // MARK: - Metrics

    private func calculateMetrics() {
        // Use advance width of "M" for cell width (monospace = all chars same width)
        let attrStr = NSAttributedString(
            string: "M",
            attributes: [.font: primaryFont]
        )
        let line = CTLineCreateWithAttributedString(attrStr)
        var ascent: CGFloat = 0
        var descent: CGFloat = 0
        var leading: CGFloat = 0
        let width = CTLineGetTypographicBounds(line, &ascent, &descent, &leading)

        cellWidth = ceil(width)
        cellHeight = ceil(ascent + descent + leading)
        baseline = ceil(descent)
    }
}
