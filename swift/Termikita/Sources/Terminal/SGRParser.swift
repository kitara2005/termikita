/// SGR (Select Graphic Rendition) parameter parser.
///
/// Handles ESC[...m sequences — text attributes and colors.
/// Supports: reset, bold, italic, underline, strikethrough, reverse,
/// 16 ANSI colors, 256 palette, 24-bit RGB.

import Foundation

enum SGRParser {
    /// Apply SGR parameters to the screen buffer's current attributes.
    static func apply(params: [Int], to screen: ScreenBuffer) {
        var i = 0
        while i < params.count {
            let p = params[i]
            switch p {
            case 0: // Reset all
                screen.currentAttrs = []
                screen.currentFG = .default
                screen.currentBG = .default

            case 1: screen.currentAttrs.insert(.bold)
            case 3: screen.currentAttrs.insert(.italic)
            case 4: screen.currentAttrs.insert(.underline)
            case 7: screen.currentAttrs.insert(.reverse)
            case 9: screen.currentAttrs.insert(.strikethrough)

            case 22: screen.currentAttrs.remove(.bold)
            case 23: screen.currentAttrs.remove(.italic)
            case 24: screen.currentAttrs.remove(.underline)
            case 27: screen.currentAttrs.remove(.reverse)
            case 29: screen.currentAttrs.remove(.strikethrough)

            // Foreground colors (30-37, 90-97)
            case 30...37:
                screen.currentFG = .ansi(p - 30)
            case 90...97:
                screen.currentFG = .ansi(p - 90 + 8)
            case 39:
                screen.currentFG = .default

            // Background colors (40-47, 100-107)
            case 40...47:
                screen.currentBG = .ansi(p - 40)
            case 100...107:
                screen.currentBG = .ansi(p - 100 + 8)
            case 49:
                screen.currentBG = .default

            // Extended foreground: 38;5;n (256) or 38;2;r;g;b (RGB)
            case 38:
                i += 1
                if i < params.count {
                    if params[i] == 5, i + 1 < params.count {
                        i += 1
                        screen.currentFG = .palette(params[i])
                    } else if params[i] == 2, i + 3 < params.count {
                        let r = UInt8(clamping: params[i + 1])
                        let g = UInt8(clamping: params[i + 2])
                        let b = UInt8(clamping: params[i + 3])
                        screen.currentFG = .rgb(r, g, b)
                        i += 3
                    }
                }

            // Extended background: 48;5;n (256) or 48;2;r;g;b (RGB)
            case 48:
                i += 1
                if i < params.count {
                    if params[i] == 5, i + 1 < params.count {
                        i += 1
                        screen.currentBG = .palette(params[i])
                    } else if params[i] == 2, i + 3 < params.count {
                        let r = UInt8(clamping: params[i + 1])
                        let g = UInt8(clamping: params[i + 2])
                        let b = UInt8(clamping: params[i + 3])
                        screen.currentBG = .rgb(r, g, b)
                        i += 3
                    }
                }

            default:
                break // Ignore unknown SGR parameters
            }
            i += 1
        }
    }
}
