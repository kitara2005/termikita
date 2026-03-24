/// NSApplicationDelegate for Termikita — bootstraps the app on launch.
///
/// Creates MainWindow + TabController, spawns the first tab,
/// and builds the menu bar with tab management shortcuts.

import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var mainWindow: MainWindow!
    private var tabController: TabController!

    func applicationDidFinishLaunching(_ notification: Notification) {
        mainWindow = MainWindow()

        tabController = TabController(
            contentView: mainWindow.contentView,
            tabBarView: mainWindow.tabBar,
            theme: ThemeColors()
        )
        tabController.onLastTabClosed = { [weak self] in
            self?.mainWindow.window.close()
        }

        setupMenuBar()

        // Open first tab
        tabController.addTab()

        mainWindow.show()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
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

        // Shell menu
        let shellMenu = NSMenu(title: "Shell")
        shellMenu.addItem(withTitle: "New Tab", action: #selector(newTab(_:)), keyEquivalent: "t")
        shellMenu.addItem(.separator())
        shellMenu.addItem(withTitle: "Close Tab", action: #selector(closeTab(_:)), keyEquivalent: "w")
        let shellItem = NSMenuItem()
        shellItem.submenu = shellMenu
        mainMenu.addItem(shellItem)

        // Edit menu
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Copy", action: #selector(copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(selectAll(_:)), keyEquivalent: "a")
        let editItem = NSMenuItem()
        editItem.submenu = editMenu
        mainMenu.addItem(editItem)

        // View menu
        let viewMenu = NSMenu(title: "View")
        viewMenu.addItem(withTitle: "Bigger", action: #selector(zoomIn(_:)), keyEquivalent: "=")
        viewMenu.addItem(withTitle: "Smaller", action: #selector(zoomOut(_:)), keyEquivalent: "-")
        viewMenu.addItem(withTitle: "Default Size", action: #selector(zoomReset(_:)), keyEquivalent: "0")
        let viewItem = NSMenuItem()
        viewItem.submenu = viewMenu
        mainMenu.addItem(viewItem)

        // Window menu
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        let windowItem = NSMenuItem()
        windowItem.submenu = windowMenu
        mainMenu.addItem(windowItem)

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Actions

    @objc func newTab(_ sender: Any?) { tabController.addTab() }
    @objc func closeTab(_ sender: Any?) { tabController.closeTab(at: tabController.activeTabIndex) }
    @objc func zoomIn(_ sender: Any?) { tabController.zoomIn() }
    @objc func zoomOut(_ sender: Any?) { tabController.zoomOut() }
    @objc func zoomReset(_ sender: Any?) { tabController.zoomReset() }

    // Edit actions — handled by TerminalView via keyDown, but menu needs responders
    @objc func copy(_ sender: Any?) {}
    @objc func paste(_ sender: Any?) {}
    @objc func selectAll(_ sender: Any?) {}
}
