/// Keycode → escape sequence mapping for special keys.
///
/// Maps macOS virtual keycodes to VT100/xterm escape sequences
/// that the shell expects for arrow keys, function keys, etc.

import Foundation

enum KeyMap {
    /// Map macOS keyCode to escape sequence bytes. Returns nil for unmapped keys.
    static func escapeSequence(for keyCode: UInt16) -> Data? {
        return keyMap[keyCode]
    }

    private static let keyMap: [UInt16: Data] = [
        // Arrow keys
        0x7E: d("\u{1b}[A"),   // Up
        0x7D: d("\u{1b}[B"),   // Down
        0x7C: d("\u{1b}[C"),   // Right
        0x7B: d("\u{1b}[D"),   // Left

        // Function keys
        0x7A: d("\u{1b}OP"),   // F1
        0x78: d("\u{1b}OQ"),   // F2
        0x63: d("\u{1b}OR"),   // F3
        0x76: d("\u{1b}OS"),   // F4
        0x60: d("\u{1b}[15~"), // F5
        0x61: d("\u{1b}[17~"), // F6
        0x62: d("\u{1b}[18~"), // F7
        0x64: d("\u{1b}[19~"), // F8
        0x65: d("\u{1b}[20~"), // F9
        0x6D: d("\u{1b}[21~"), // F10
        0x67: d("\u{1b}[23~"), // F11
        0x6F: d("\u{1b}[24~"), // F12

        // Navigation
        0x73: d("\u{1b}[H"),   // Home
        0x77: d("\u{1b}[F"),   // End
        0x74: d("\u{1b}[5~"),  // Page Up
        0x79: d("\u{1b}[6~"),  // Page Down

        // Editing
        0x75: d("\u{1b}[3~"),  // Forward Delete
        0x33: d("\u{7f}"),     // Backspace (DEL)
        0x24: d("\r"),         // Return
        0x30: d("\t"),         // Tab
        0x35: d("\u{1b}"),     // Escape
    ]

    private static func d(_ s: String) -> Data {
        s.data(using: .utf8)!
    }
}
