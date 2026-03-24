/// Loads and manages color themes from JSON files.
///
/// Themes are loaded from the bundle's Resources/Themes/ directory.
/// Supports switching themes by name with fallback to hardcoded default.

import Foundation

final class ThemeManager {
    /// JSON-decodable theme file structure.
    private struct ThemeFile: Decodable {
        let name: String
        let colors: ThemeFileColors
    }
    private struct ThemeFileColors: Decodable {
        let foreground: String
        let background: String
        let cursor: String
        let selection: String
        let ansi: [String]
    }

    /// Available theme names (filename stems).
    private(set) var themeNames: [String] = []
    /// Currently active theme name.
    private(set) var activeThemeName: String = "default-dark"
    /// Loaded theme files keyed by name.
    private var themes: [String: ThemeColors] = [:]

    init() {
        loadThemes()
    }

    // MARK: - Load

    private func loadThemes() {
        // Look for themes in bundle resources
        guard let themesURL = Bundle.main.url(forResource: "Themes", withExtension: nil) else {
            // Fallback: look relative to executable (for swift run during dev)
            loadThemesFromPath(findDevThemesPath())
            return
        }
        loadThemesFromPath(themesURL.path)
    }

    private func loadThemesFromPath(_ path: String?) {
        guard let path = path else { return }
        let url = URL(fileURLWithPath: path)
        guard let files = try? FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil) else { return }

        for file in files where file.pathExtension == "json" {
            let name = file.deletingPathExtension().lastPathComponent
            if let data = try? Data(contentsOf: file),
               let themeFile = try? JSONDecoder().decode(ThemeFile.self, from: data) {
                themes[name] = convertTheme(themeFile.colors)
                themeNames.append(name)
            }
        }
        themeNames.sort()
    }

    /// Find themes dir during development (swift run).
    private func findDevThemesPath() -> String? {
        // Walk up from executable to find Resources/Themes
        let execURL = URL(fileURLWithPath: ProcessInfo.processInfo.arguments[0])
        var dir = execURL.deletingLastPathComponent()
        for _ in 0..<10 {
            let candidate = dir.appendingPathComponent("Resources/Themes")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate.path
            }
            dir = dir.deletingLastPathComponent()
        }
        return nil
    }

    // MARK: - Switch theme

    /// Set active theme by name. Returns the ThemeColors.
    @discardableResult
    func setTheme(_ name: String) -> ThemeColors {
        activeThemeName = name
        return getActiveTheme()
    }

    /// Get the currently active theme colors.
    func getActiveTheme() -> ThemeColors {
        themes[activeThemeName] ?? ThemeColors()
    }

    // MARK: - Convert

    private func convertTheme(_ colors: ThemeFileColors) -> ThemeColors {
        var theme = ThemeColors()
        theme.foreground = hexToRGB(colors.foreground)
        theme.background = hexToRGB(colors.background)
        theme.cursor = hexToRGB(colors.cursor)
        theme.selection = hexToRGB(colors.selection)
        if colors.ansi.count == 16 {
            theme.ansi = colors.ansi.map { hexToRGB($0) }
        }
        return theme
    }

    /// Parse "#RRGGBB" or "RRGGBB" hex string to RGB tuple.
    private func hexToRGB(_ hex: String) -> (UInt8, UInt8, UInt8) {
        let clean = hex.hasPrefix("#") ? String(hex.dropFirst()) : hex
        guard clean.count == 6, let value = UInt32(clean, radix: 16) else {
            return (204, 204, 204)
        }
        return (
            UInt8((value >> 16) & 0xFF),
            UInt8((value >> 8) & 0xFF),
            UInt8(value & 0xFF)
        )
    }
}
