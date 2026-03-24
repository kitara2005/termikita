/// Multi-tab terminal management.
///
/// Owns a list of TabItems, swaps TerminalViews in the content area,
/// manages tab lifecycle (add/close/select/next/prev), font zoom.

import AppKit

final class TabController {
    private let contentView: NSView
    private let tabBarView: TabBarView
    private var themeColors: ThemeColors
    var onLastTabClosed: (() -> Void)?

    private(set) var tabs: [TabItem] = []
    private(set) var activeTabIndex: Int = -1

    init(contentView: NSView, tabBarView: TabBarView, theme: ThemeColors) {
        self.contentView = contentView
        self.tabBarView = tabBarView
        self.themeColors = theme
        tabBarView.controller = self
    }

    // MARK: - Public API

    @discardableResult
    func addTab(workingDir: String? = nil) -> TabItem {
        let renderer = TextRenderer()
        let (cw, ch) = renderer.getCellDimensions()
        let bounds = contentView.bounds
        let cols = max(1, Int((bounds.width - AppConstants.terminalPaddingX * 2) / cw))
        let rows = max(1, Int((bounds.height - AppConstants.terminalPaddingY * 2) / ch))

        let buffer = BufferManager(cols: cols, rows: rows)
        let pty = PTYManager(cols: cols, rows: rows)

        let view = TerminalView(frame: bounds)
        view.autoresizingMask = [.width, .height]
        view.replaceSession(pty: pty, buffer: buffer, renderer: renderer, theme: themeColors)

        // Wire PTY output → buffer
        pty.onOutput = { [weak buffer] data in buffer?.feed(data) }
        pty.onExit = { [weak self, weak view] _ in
            guard let self = self, let view = view else { return }
            if let idx = self.tabs.firstIndex(where: { $0.view === view }) {
                self.closeTab(at: idx)
            }
        }
        // Wire buffer responses → PTY
        buffer.onResponse = { [weak pty] data in pty?.write(data) }
        // Wire title changes
        buffer.onTitleChange = { [weak self, weak view] title in
            guard let self = self, let view = view else { return }
            if let idx = self.tabs.firstIndex(where: { $0.view === view }) {
                self.tabs[idx].title = title.isEmpty ? "Terminal" : title
                self.tabBarView.needsDisplay = true
                if idx == self.activeTabIndex {
                    self.updateWindowTitle()
                }
            }
        }

        let tab = TabItem(pty: pty, buffer: buffer, view: view)
        tabs.append(tab)

        // Spawn shell
        let dir = workingDir ?? FileManager.default.homeDirectoryForCurrentUser.path
        pty.spawn(workingDir: dir)

        selectTab(at: tabs.count - 1)
        return tab
    }

    func closeTab(at index: Int) {
        guard index >= 0 && index < tabs.count else { return }
        let tab = tabs[index]
        tab.view.stopTimers()
        tab.pty.shutdown()
        tab.view.removeFromSuperview()
        tabs.remove(at: index)

        if tabs.isEmpty {
            onLastTabClosed?()
            return
        }

        let newActive = min(activeTabIndex, tabs.count - 1)
        activeTabIndex = -1
        selectTab(at: newActive)
    }

    func selectTab(at index: Int) {
        guard index >= 0 && index < tabs.count else { return }

        // Remove current view
        if activeTabIndex >= 0 && activeTabIndex < tabs.count {
            tabs[activeTabIndex].view.removeFromSuperview()
        }

        activeTabIndex = index
        let tab = tabs[index]
        tab.view.frame = contentView.bounds
        contentView.addSubview(tab.view)
        contentView.window?.makeFirstResponder(tab.view)

        updateWindowTitle()
        tabBarView.needsDisplay = true
    }

    func nextTab() {
        guard !tabs.isEmpty else { return }
        selectTab(at: (activeTabIndex + 1) % tabs.count)
    }

    func prevTab() {
        guard !tabs.isEmpty else { return }
        selectTab(at: (activeTabIndex - 1 + tabs.count) % tabs.count)
    }

    func closeOtherTabs(keeping index: Int) {
        guard index >= 0 && index < tabs.count else { return }
        let kept = tabs[index]
        for (i, tab) in tabs.enumerated() where i != index {
            tab.view.stopTimers()
            tab.pty.shutdown()
            tab.view.removeFromSuperview()
        }
        tabs = [kept]
        activeTabIndex = -1
        selectTab(at: 0)
    }

    // MARK: - Font zoom

    func zoomIn() {
        let current = AppConstants.defaultFontSize // TODO: read from config
        let newSize = min(current + AppConstants.fontSizeStep, AppConstants.fontSizeMax)
        applyFontSize(newSize)
    }

    func zoomOut() {
        let current = AppConstants.defaultFontSize
        let newSize = max(current - AppConstants.fontSizeStep, AppConstants.fontSizeMin)
        applyFontSize(newSize)
    }

    func zoomReset() {
        applyFontSize(AppConstants.defaultFontSize)
    }

    private func applyFontSize(_ size: CGFloat) {
        for tab in tabs {
            tab.view.renderer.setFont(family: AppConstants.defaultFontFamily, size: size)
            tab.view.setFrameSize(tab.view.frame.size) // triggers resize recalc
        }
    }

    // MARK: - Theme

    func setTheme(_ theme: ThemeColors) {
        themeColors = theme
        for tab in tabs {
            tab.view.themeColors = theme
            tab.view.needsDisplay = true
        }
    }

    // MARK: - Helpers

    private func updateWindowTitle() {
        guard activeTabIndex >= 0 && activeTabIndex < tabs.count else { return }
        let title = tabs[activeTabIndex].title
        contentView.window?.title = title.isEmpty ? AppConstants.appName : title
    }
}
