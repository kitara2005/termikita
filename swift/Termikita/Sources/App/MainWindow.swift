/// NSWindow setup for Termikita — centered, dark background, resizable.

import AppKit

final class MainWindow {
    let window: NSWindow
    /// Content area below the tab bar where TerminalView is placed.
    let contentView: NSView
    /// Tab bar strip at the top of the window.
    let tabBarView: NSView

    init(width: CGFloat = AppConstants.defaultWindowWidth,
         height: CGFloat = AppConstants.defaultWindowHeight) {
        // Create window
        let frame = NSRect(x: 0, y: 0, width: width, height: height)
        window = NSWindow(
            contentRect: frame,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = AppConstants.appName
        window.minSize = NSSize(
            width: AppConstants.minWindowWidth,
            height: AppConstants.minWindowHeight
        )
        window.isReleasedWhenClosed = false
        window.center()

        // Root view fills the entire window content area
        let rootView = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        rootView.autoresizingMask = [.width, .height]
        window.contentView = rootView

        // Tab bar at the top (fixed height)
        let tabBarHeight = AppConstants.tabBarHeight
        let tabBar = NSView(frame: NSRect(
            x: 0,
            y: height - tabBarHeight,
            width: width,
            height: tabBarHeight
        ))
        tabBar.autoresizingMask = [.width, .minYMargin]
        tabBar.wantsLayer = true
        tabBar.layer?.backgroundColor = NSColor(
            calibratedRed: 28/255, green: 28/255, blue: 28/255, alpha: 1
        ).cgColor
        rootView.addSubview(tabBar)
        self.tabBarView = tabBar

        // Content view below the tab bar (fills remaining space)
        let content = NSView(frame: NSRect(
            x: 0,
            y: 0,
            width: width,
            height: height - tabBarHeight
        ))
        content.autoresizingMask = [.width, .height]
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.black.cgColor
        rootView.addSubview(content)
        self.contentView = content
    }

    /// Show the window and make it key.
    func show() {
        window.makeKeyAndOrderFront(nil)
    }
}
