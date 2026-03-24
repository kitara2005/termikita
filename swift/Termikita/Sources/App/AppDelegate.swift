/// NSApplicationDelegate for Termikita — bootstraps the app on launch.

import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var mainWindow: MainWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        mainWindow = MainWindow()
        setupMenuBar()
        mainWindow.show()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - Menu bar (minimal for Phase 01)

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

        NSApp.mainMenu = mainMenu
    }
}
