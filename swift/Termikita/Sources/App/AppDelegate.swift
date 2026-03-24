/// NSApplicationDelegate for Termikita — bootstraps the app on launch.
///
/// Creates the main window, spawns a terminal view with a shell,
/// and builds the menu bar.

import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var mainWindow: MainWindow!
    private var terminalView: TerminalView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        mainWindow = MainWindow()
        setupMenuBar()

        // Create terminal view filling the content area
        let contentView = mainWindow.contentView
        terminalView = TerminalView(frame: contentView.bounds)
        terminalView.autoresizingMask = [.width, .height]
        contentView.addSubview(terminalView)

        // Spawn shell
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
        terminalView.pty.spawn(workingDir: homeDir)

        mainWindow.show()
        mainWindow.window.makeFirstResponder(terminalView)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        terminalView?.pty?.shutdown()
    }

    // MARK: - Menu bar

    private func setupMenuBar() {
        let mainMenu = NSMenu()

        // App menu
        let appMenu = NSMenu(title: AppConstants.appName)
        appMenu.addItem(withTitle: "About \(AppConstants.appName)",
                        action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
                        keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit \(AppConstants.appName)",
                        action: #selector(NSApplication.terminate(_:)),
                        keyEquivalent: "q")
        let appItem = NSMenuItem()
        appItem.submenu = appMenu
        mainMenu.addItem(appItem)

        // Edit menu (Copy/Paste/Select All)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Copy", action: #selector(copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(selectAll(_:)), keyEquivalent: "a")
        let editItem = NSMenuItem()
        editItem.submenu = editMenu
        mainMenu.addItem(editItem)

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Edit menu actions (forwarded to terminal view)

    @objc func copy(_ sender: Any?) {
        // Handled by TerminalView keyDown Cmd+C
    }

    @objc func paste(_ sender: Any?) {
        // Handled by TerminalView keyDown Cmd+V
    }

    @objc func selectAll(_ sender: Any?) {
        // Handled by TerminalView keyDown Cmd+A
    }
}
