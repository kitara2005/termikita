/// NSApplicationDelegate for Termikita — bootstraps the app on launch.
///
/// Creates MainWindow + TabController, spawns the first tab,
/// builds the full menu bar with theme picker and context menus.

import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private var mainWindow: MainWindow!
    private var tabController: TabController!
    private var config: ConfigManager!
    private var themeMgr: ThemeManager!
    private var editMenu: NSMenu?
    private var themeMenu: NSMenu?

    func applicationDidFinishLaunching(_ notification: Notification) {
        config = ConfigManager()
        themeMgr = ThemeManager()
        let themeColors = themeMgr.setTheme(config.theme)

        mainWindow = MainWindow(width: config.windowWidth, height: config.windowHeight)

        tabController = TabController(
            contentView: mainWindow.contentView,
            tabBarView: mainWindow.tabBar,
            theme: themeColors
        )
        tabController.onLastTabClosed = { [weak self] in
            self?.mainWindow.window.close()
        }

        setupMenuBar()
        tabController.addTab()

        mainWindow.show()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
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

        // Edit menu — delegate strips system-injected items
        let edit = NSMenu(title: "Edit")
        edit.delegate = self
        self.editMenu = edit
        populateEditMenu(edit)
        let editItem = NSMenuItem()
        editItem.submenu = edit
        mainMenu.addItem(editItem)

        // View menu — zoom + theme picker
        let viewMenu = NSMenu(title: "View")
        viewMenu.addItem(withTitle: "Bigger", action: #selector(zoomIn(_:)), keyEquivalent: "=")
        viewMenu.addItem(withTitle: "Smaller", action: #selector(zoomOut(_:)), keyEquivalent: "-")
        viewMenu.addItem(withTitle: "Default Size", action: #selector(zoomReset(_:)), keyEquivalent: "0")
        viewMenu.addItem(.separator())

        // Theme submenu
        let themeSub = NSMenu(title: "Theme")
        self.themeMenu = themeSub
        rebuildThemeMenu()
        let themeHolder = NSMenuItem(title: "Theme", action: nil, keyEquivalent: "")
        themeHolder.submenu = themeSub
        viewMenu.addItem(themeHolder)

        let viewItem = NSMenuItem()
        viewItem.submenu = viewMenu
        mainMenu.addItem(viewItem)

        // Format menu — font panel
        let formatMenu = NSMenu(title: "Format")
        let fontSub = NSMenu(title: "Font")
        fontSub.addItem(withTitle: "Show Fonts",
                        action: #selector(NSFontManager.orderFrontFontPanel(_:)),
                        keyEquivalent: "")
        let fontHolder = NSMenuItem(title: "Font", action: nil, keyEquivalent: "")
        fontHolder.submenu = fontSub
        formatMenu.addItem(fontHolder)
        let formatItem = NSMenuItem()
        formatItem.submenu = formatMenu
        mainMenu.addItem(formatItem)

        // Window menu
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize",
                           action: #selector(NSWindow.performMiniaturize(_:)),
                           keyEquivalent: "m")
        let windowItem = NSMenuItem()
        windowItem.submenu = windowMenu
        mainMenu.addItem(windowItem)

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Edit menu delegate — strip system-injected items

    private func populateEditMenu(_ menu: NSMenu) {
        menu.addItem(withTitle: "Copy", action: #selector(copy(_:)), keyEquivalent: "c")
        menu.addItem(withTitle: "Paste", action: #selector(paste(_:)), keyEquivalent: "v")
        menu.addItem(withTitle: "Select All", action: #selector(selectAll(_:)), keyEquivalent: "a")
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        guard menu === editMenu else { return }
        menu.removeAllItems()
        populateEditMenu(menu)
    }

    // MARK: - Theme picker

    private func rebuildThemeMenu() {
        guard let menu = themeMenu else { return }
        menu.removeAllItems()
        let active = config.theme
        for name in themeMgr.themeNames {
            let label = name.replacingOccurrences(of: "-", with: " ").capitalized
            let item = NSMenuItem(title: label, action: #selector(selectTheme(_:)), keyEquivalent: "")
            item.representedObject = name
            item.target = self
            if name == active { item.state = .on }
            menu.addItem(item)
        }
    }

    @objc func selectTheme(_ sender: NSMenuItem) {
        guard let name = sender.representedObject as? String else { return }
        let colors = themeMgr.setTheme(name)
        config.set(\.theme, name)
        config.save()
        tabController.setTheme(colors)
        rebuildThemeMenu()
    }

    // MARK: - Actions

    @objc func newTab(_ sender: Any?) { tabController.addTab() }
    @objc func closeTab(_ sender: Any?) { tabController.closeTab(at: tabController.activeTabIndex) }
    @objc func zoomIn(_ sender: Any?) { tabController.zoomIn() }
    @objc func zoomOut(_ sender: Any?) { tabController.zoomOut() }
    @objc func zoomReset(_ sender: Any?) { tabController.zoomReset() }
    @objc func copy(_ sender: Any?) {}
    @objc func paste(_ sender: Any?) {}
    @objc func selectAll(_ sender: Any?) {}
}
