/// A single character cell in the terminal grid.
///
/// Each cell stores the character, foreground/background colors,
/// and text attributes (bold, italic, underline, etc.).

import Foundation

/// Terminal color — supports default, 16 ANSI, 256 palette, and 24-bit RGB.
enum TermColor: Equatable {
    case `default`
    case ansi(Int)              // 0-15 standard ANSI colors
    case palette(Int)           // 16-255 extended palette
    case rgb(UInt8, UInt8, UInt8)
}

/// Text attributes bitmask for compact storage.
struct CellAttributes: OptionSet {
    let rawValue: UInt8
    static let bold          = CellAttributes(rawValue: 1 << 0)
    static let italic        = CellAttributes(rawValue: 1 << 1)
    static let underline     = CellAttributes(rawValue: 1 << 2)
    static let strikethrough = CellAttributes(rawValue: 1 << 3)
    static let reverse       = CellAttributes(rawValue: 1 << 4)
    static let wide          = CellAttributes(rawValue: 1 << 5)  // CJK double-width
    static let placeholder   = CellAttributes(rawValue: 1 << 6)  // right half of wide char
}

/// Single terminal cell — character + colors + attributes.
struct Cell {
    var char: Character = " "
    var fg: TermColor = .default
    var bg: TermColor = .default
    var attrs: CellAttributes = []

    // Convenience accessors
    var bold: Bool { attrs.contains(.bold) }
    var italic: Bool { attrs.contains(.italic) }
    var underline: Bool { attrs.contains(.underline) }
    var strikethrough: Bool { attrs.contains(.strikethrough) }
    var reverse: Bool { attrs.contains(.reverse) }
    var wide: Bool { attrs.contains(.wide) }
    var placeholder: Bool { attrs.contains(.placeholder) }

    /// Create a blank cell (space, default colors, no attributes).
    static let blank = Cell()
}

/// Cursor shape as reported by DECSCUSR escape sequence.
enum CursorShape {
    case block
    case underline
    case beam
}
