/// Resolves TermColor values to NSColor using the active theme palette.
///
/// Handles: default, 16 ANSI, 256 palette (6×6×6 cube + 24 grayscale),
/// 24-bit RGB, and reverse video swapping.

import AppKit

/// Theme color dictionary — loaded from JSON theme files.
struct ThemeColors {
    var foreground: (UInt8, UInt8, UInt8) = (204, 204, 204)
    var background: (UInt8, UInt8, UInt8) = (28, 28, 28)
    var cursor: (UInt8, UInt8, UInt8) = (204, 204, 204)
    var selection: (UInt8, UInt8, UInt8) = (68, 68, 68)
    /// 16-entry ANSI palette (indices 0-15).
    var ansi: [(UInt8, UInt8, UInt8)] = defaultAnsiPalette
}

/// Default dark ANSI palette (matches Python Termikita).
let defaultAnsiPalette: [(UInt8, UInt8, UInt8)] = [
    (0, 0, 0),       (204, 0, 0),     (0, 204, 0),     (204, 204, 0),
    (0, 0, 204),     (204, 0, 204),   (0, 204, 204),   (204, 204, 204),
    (128, 128, 128), (255, 0, 0),     (0, 255, 0),     (255, 255, 0),
    (0, 0, 255),     (255, 0, 255),   (0, 255, 255),   (255, 255, 255),
]

enum ColorResolver {
    /// Resolve a TermColor to an RGB tuple using the theme.
    static func resolve(_ color: TermColor, theme: ThemeColors, isForeground: Bool) -> (UInt8, UInt8, UInt8) {
        switch color {
        case .default:
            return isForeground ? theme.foreground : theme.background
        case .ansi(let idx):
            if idx >= 0 && idx < theme.ansi.count {
                return theme.ansi[idx]
            }
            return isForeground ? theme.foreground : theme.background
        case .palette(let idx):
            return paletteColor(idx)
        case .rgb(let r, let g, let b):
            return (r, g, b)
        }
    }

    /// Resolve TermColor to NSColor.
    static func resolveNSColor(_ color: TermColor, theme: ThemeColors, isForeground: Bool) -> NSColor {
        let (r, g, b) = resolve(color, theme: theme, isForeground: isForeground)
        return NSColor(
            calibratedRed: CGFloat(r) / 255.0,
            green: CGFloat(g) / 255.0,
            blue: CGFloat(b) / 255.0,
            alpha: 1.0
        )
    }

    /// Resolve foreground and background, applying reverse video if needed.
    static func resolvePair(
        fg: TermColor, bg: TermColor, reverse: Bool, theme: ThemeColors
    ) -> (fg: NSColor, bg: NSColor) {
        let fgRGB = resolve(fg, theme: theme, isForeground: true)
        let bgRGB = resolve(bg, theme: theme, isForeground: false)
        let (finalFG, finalBG) = reverse ? (bgRGB, fgRGB) : (fgRGB, bgRGB)
        return (
            fg: nscolor(finalFG),
            bg: nscolor(finalBG)
        )
    }

    /// 256-color palette lookup (indices 16-231 = 6×6×6 cube, 232-255 = grayscale).
    private static func paletteColor(_ idx: Int) -> (UInt8, UInt8, UInt8) {
        if idx < 16 {
            return idx < defaultAnsiPalette.count ? defaultAnsiPalette[idx] : (204, 204, 204)
        } else if idx < 232 {
            // 6×6×6 color cube
            let ci = idx - 16
            let r = UInt8((ci / 36) * 51)
            let g = UInt8(((ci / 6) % 6) * 51)
            let b = UInt8((ci % 6) * 51)
            return (r, g, b)
        } else if idx < 256 {
            // 24-step grayscale (8, 18, 28, ..., 238)
            let v = UInt8(8 + (idx - 232) * 10)
            return (v, v, v)
        }
        return (204, 204, 204)
    }

    private static func nscolor(_ rgb: (UInt8, UInt8, UInt8)) -> NSColor {
        NSColor(
            calibratedRed: CGFloat(rgb.0) / 255.0,
            green: CGFloat(rgb.1) / 255.0,
            blue: CGFloat(rgb.2) / 255.0,
            alpha: 1.0
        )
    }
}
