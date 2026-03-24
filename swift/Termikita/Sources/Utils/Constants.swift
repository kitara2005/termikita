/// App-wide constants for Termikita terminal emulator.

import Foundation

enum AppConstants {
    static let appName = "Termikita"
    static let bundleID = "com.termikita.app"

    // Terminal grid defaults
    static let defaultCols = 80
    static let defaultRows = 24
    static let defaultScrollback = 100_000

    // Font defaults
    static let defaultFontFamily = "SF Mono"
    static let defaultFontSize: CGFloat = 13.0
    static let fontSizeMin: CGFloat = 8.0
    static let fontSizeMax: CGFloat = 36.0
    static let fontSizeStep: CGFloat = 1.0

    // Terminal padding (points)
    static let terminalPaddingX: CGFloat = 12.0
    static let terminalPaddingY: CGFloat = 8.0

    // Window defaults
    static let defaultWindowWidth: CGFloat = 800.0
    static let defaultWindowHeight: CGFloat = 600.0
    static let minWindowWidth: CGFloat = 400.0
    static let minWindowHeight: CGFloat = 300.0

    // Tab bar
    static let tabBarHeight: CGFloat = 28.0

    // PTY
    static let ptyReadChunkSize = 65536
    static let defaultTerm = "xterm-256color"
    static let defaultColorTerm = "truecolor"

    // Config
    static let configDir = "~/.config/termikita/"
    static let configFile = "config.json"
}
