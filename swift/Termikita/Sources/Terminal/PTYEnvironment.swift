/// Builds the environment variable array for the child shell process.
///
/// Sets TERM, COLORTERM, LANG, and suppresses zsh end-of-line mark
/// to avoid rendering artifacts after partial output.

import Foundation

enum PTYEnvironment {
    /// Build C-compatible environment for execve.
    /// Returns array of "KEY=VALUE" strings.
    static func buildChildEnvironment() -> [String] {
        var env: [String] = []

        env.append("TERM=\(AppConstants.defaultTerm)")
        env.append("COLORTERM=\(AppConstants.defaultColorTerm)")

        // Inherit LANG from parent or use UTF-8 default
        if let lang = ProcessInfo.processInfo.environment["LANG"], !lang.isEmpty {
            env.append("LANG=\(lang)")
        } else {
            env.append("LANG=en_US.UTF-8")
        }

        // Suppress zsh end-of-line mark (%) that breaks terminal rendering
        env.append("PROMPT_EOL_MARK=")

        // Inherit HOME and USER
        if let home = ProcessInfo.processInfo.environment["HOME"] {
            env.append("HOME=\(home)")
        }
        if let user = ProcessInfo.processInfo.environment["USER"] {
            env.append("USER=\(user)")
        }
        if let logname = ProcessInfo.processInfo.environment["LOGNAME"] {
            env.append("LOGNAME=\(logname)")
        }

        // Inherit PATH
        if let path = ProcessInfo.processInfo.environment["PATH"] {
            env.append("PATH=\(path)")
        } else {
            env.append("PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
        }

        // Inherit SHELL so child knows its own shell
        if let shell = ProcessInfo.processInfo.environment["SHELL"] {
            env.append("SHELL=\(shell)")
        }

        return env
    }

    /// Resolve the shell path: explicit override → $SHELL → /bin/zsh fallback.
    static func resolveShellPath(_ override: String? = nil) -> String {
        if let explicit = override, !explicit.isEmpty,
           FileManager.default.isExecutableFile(atPath: explicit) {
            return explicit
        }
        if let shell = ProcessInfo.processInfo.environment["SHELL"],
           FileManager.default.isExecutableFile(atPath: shell) {
            return shell
        }
        return "/bin/zsh"
    }
}
