/// JSON config persistence at ~/.config/termikita/config.json.
///
/// Atomic writes (temp file + rename), owner-only permissions (0o600),
/// fallback to defaults on corrupt/missing file.

import Foundation

final class ConfigManager {
    /// Persisted settings with Codable for JSON serialization.
    struct Settings: Codable {
        var fontFamily: String = AppConstants.defaultFontFamily
        var fontSize: CGFloat = AppConstants.defaultFontSize
        var theme: String = "default-dark"
        var scrollbackLines: Int = AppConstants.defaultScrollback
        var windowWidth: CGFloat = AppConstants.defaultWindowWidth
        var windowHeight: CGFloat = AppConstants.defaultWindowHeight
        var shell: String = ""
    }

    private(set) var settings: Settings
    private let configPath: URL

    init() {
        let configDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".config/termikita")
        self.configPath = configDir.appendingPathComponent("config.json")

        // Ensure config directory exists
        try? FileManager.default.createDirectory(at: configDir, withIntermediateDirectories: true)

        // Load existing config or use defaults
        if let data = try? Data(contentsOf: configPath),
           let loaded = try? JSONDecoder().decode(Settings.self, from: data) {
            self.settings = loaded
        } else {
            self.settings = Settings()
        }
    }

    // MARK: - Property accessors

    var fontFamily: String { settings.fontFamily }
    var fontSize: CGFloat { settings.fontSize }
    var theme: String { settings.theme }
    var scrollbackLines: Int { settings.scrollbackLines }
    var windowWidth: CGFloat { settings.windowWidth }
    var windowHeight: CGFloat { settings.windowHeight }
    var shell: String { settings.shell }

    // MARK: - Mutators

    func set<T>(_ keyPath: WritableKeyPath<Settings, T>, _ value: T) {
        settings[keyPath: keyPath] = value
    }

    /// Persist settings to disk with atomic write and owner-only permissions.
    func save() {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(settings) else { return }

        // Atomic write: write to temp file, then rename
        let tmpPath = configPath.deletingLastPathComponent()
            .appendingPathComponent(".config.json.tmp")
        do {
            try data.write(to: tmpPath, options: .atomic)
            // Set owner-only permissions (0o600)
            try FileManager.default.setAttributes(
                [.posixPermissions: 0o600], ofItemAtPath: tmpPath.path
            )
            // Rename to final path
            _ = try FileManager.default.replaceItemAt(configPath, withItemAt: tmpPath)
        } catch {
            // Fallback: write directly
            try? data.write(to: configPath, options: .atomic)
        }
    }
}
