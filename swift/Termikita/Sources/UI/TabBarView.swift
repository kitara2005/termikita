/// Tab bar NSView — renders clickable tab strip above terminal content.
///
/// Draws tab titles with active-tab highlight and close (×) button per tab.
/// Height: 28px (set by MainWindow).

import AppKit

final class TabBarView: NSView {
    weak var controller: TabController?
    private var hoverTabIndex = -1
    private var hoverClose = false
    private var trackingArea: NSTrackingArea?

    // Layout constants
    private let tabMinWidth: CGFloat = 80
    private let tabMaxWidth: CGFloat = 200
    private let closeAreaWidth: CGFloat = 18
    private let fontSize: CGFloat = 11.5
    private let bgColor = NSColor(calibratedRed: 28/255, green: 28/255, blue: 28/255, alpha: 1)
    private let activeColor = NSColor(calibratedRed: 50/255, green: 50/255, blue: 50/255, alpha: 1)
    private let inactiveColor = NSColor(calibratedRed: 36/255, green: 36/255, blue: 36/255, alpha: 1)
    private let borderColor = NSColor(calibratedRed: 60/255, green: 60/255, blue: 60/255, alpha: 1)
    private let textActive = NSColor(calibratedRed: 220/255, green: 220/255, blue: 220/255, alpha: 1)
    private let textInactive = NSColor(calibratedRed: 140/255, green: 140/255, blue: 140/255, alpha: 1)
    private let hoverCloseColor = NSColor(calibratedRed: 200/255, green: 70/255, blue: 70/255, alpha: 1)

    override var isFlipped: Bool { true }
    override var isOpaque: Bool { true }
    override var acceptsFirstResponder: Bool { false }

    // MARK: - Tracking area

    override func updateTrackingAreas() {
        if let area = trackingArea { removeTrackingArea(area) }
        let area = NSTrackingArea(
            rect: bounds,
            options: [.mouseMoved, .activeInKeyWindow, .inVisibleRect],
            owner: self, userInfo: nil
        )
        addTrackingArea(area)
        trackingArea = area
        super.updateTrackingAreas()
    }

    // MARK: - Drawing

    override func draw(_ dirtyRect: NSRect) {
        guard let controller = controller else { return }
        let tabs = controller.tabs
        let barW = bounds.width
        let barH = bounds.height

        bgColor.setFill()
        bounds.fill()

        guard !tabs.isEmpty else { return }

        let activeIdx = controller.activeTabIndex
        let tabW = tabWidth(barWidth: barW, count: tabs.count)
        let font = NSFont.systemFont(ofSize: fontSize)

        for (i, tab) in tabs.enumerated() {
            let x = CGFloat(i) * tabW
            let isActive = (i == activeIdx)

            // Tab background
            (isActive ? activeColor : inactiveColor).setFill()
            NSRect(x: x, y: 0, width: tabW, height: barH).fill()

            // Right border
            borderColor.setFill()
            NSRect(x: x + tabW - 1, y: 0, width: 1, height: barH).fill()

            // Bottom border (inactive tabs only)
            if !isActive {
                borderColor.setFill()
                NSRect(x: x, y: barH - 1, width: tabW, height: 1).fill()
            }

            // Close button (×)
            let closeX = x + tabW - closeAreaWidth + 3
            let isHoverClose = (hoverTabIndex == i && hoverClose)
            let closeColor = isHoverClose ? hoverCloseColor : (isActive ? textActive : textInactive)
            drawCloseButton(cx: closeX, cy: barH / 2, color: closeColor)

            // Title
            let textX = x + 8
            let textW = tabW - 8 - closeAreaWidth
            let color = isActive ? textActive : textInactive
            drawLabel(tab.title, x: textX, y: 0, w: textW, h: barH, font: font, color: color)
        }

        // Bottom border
        borderColor.setFill()
        NSRect(x: 0, y: barH - 1, width: barW, height: 1).fill()
    }

    private func drawCloseButton(cx: CGFloat, cy: CGFloat, color: NSColor) {
        let r: CGFloat = 4
        color.setStroke()
        let path = NSBezierPath()
        path.lineWidth = 1.5
        path.move(to: NSPoint(x: cx - r, y: cy - r))
        path.line(to: NSPoint(x: cx + r, y: cy + r))
        path.move(to: NSPoint(x: cx + r, y: cy - r))
        path.line(to: NSPoint(x: cx - r, y: cy + r))
        path.stroke()
    }

    private func drawLabel(_ text: String, x: CGFloat, y: CGFloat,
                           w: CGFloat, h: CGFloat, font: NSFont, color: NSColor) {
        let para = NSMutableParagraphStyle()
        para.lineBreakMode = .byTruncatingTail
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font, .foregroundColor: color, .paragraphStyle: para
        ]
        let attrStr = NSAttributedString(string: text, attributes: attrs)
        let textH = attrStr.size().height
        let ty = y + (h - textH) / 2
        attrStr.draw(in: NSRect(x: x, y: ty, width: w, height: textH + 2))
    }

    // MARK: - Mouse events

    override func mouseDown(with event: NSEvent) {
        let (idx, onClose) = hitTest(event)
        guard idx >= 0 else { return }
        if onClose {
            // Defer close to avoid crash during event handling
            let closeIdx = idx
            DispatchQueue.main.async { [weak self] in
                self?.controller?.closeTab(at: closeIdx)
            }
        } else {
            controller?.selectTab(at: idx)
        }
    }

    override func mouseMoved(with event: NSEvent) {
        let (idx, onClose) = hitTest(event)
        if hoverTabIndex != idx || hoverClose != onClose {
            hoverTabIndex = idx
            hoverClose = onClose
            needsDisplay = true
        }
    }

    override func mouseExited(with event: NSEvent) {
        if hoverTabIndex != -1 || hoverClose {
            hoverTabIndex = -1
            hoverClose = false
            needsDisplay = true
        }
    }

    // MARK: - Context menu

    override func menu(for event: NSEvent) -> NSMenu? {
        let (idx, _) = hitTest(event)
        guard idx >= 0, let controller = controller else { return nil }

        let menu = NSMenu()
        menu.autoenablesItems = false

        let newTab = menu.addItem(withTitle: "New Tab", action: #selector(contextNewTab), keyEquivalent: "")
        newTab.target = self

        let closeTab = menu.addItem(withTitle: "Close Tab", action: #selector(contextCloseTab(_:)), keyEquivalent: "")
        closeTab.target = self
        closeTab.tag = idx

        let closeOthers = menu.addItem(withTitle: "Close Other Tabs", action: #selector(contextCloseOthers(_:)), keyEquivalent: "")
        closeOthers.target = self
        closeOthers.tag = idx
        closeOthers.isEnabled = controller.tabs.count > 1

        return menu
    }

    @objc private func contextNewTab() { controller?.addTab() }
    @objc private func contextCloseTab(_ sender: NSMenuItem) { controller?.closeTab(at: sender.tag) }
    @objc private func contextCloseOthers(_ sender: NSMenuItem) { controller?.closeOtherTabs(keeping: sender.tag) }

    // MARK: - Geometry

    private func tabWidth(barWidth: CGFloat, count: Int) -> CGFloat {
        guard count > 0 else { return tabMaxWidth }
        return max(tabMinWidth, min(tabMaxWidth, barWidth / CGFloat(count)))
    }

    private func hitTest(_ event: NSEvent) -> (Int, Bool) {
        guard let controller = controller, !controller.tabs.isEmpty else { return (-1, false) }
        let point = convert(event.locationInWindow, from: nil)
        let tabW = tabWidth(barWidth: bounds.width, count: controller.tabs.count)
        let idx = Int(point.x / tabW)
        guard idx >= 0 && idx < controller.tabs.count else { return (-1, false) }
        let closeStart = CGFloat(idx) * tabW + tabW - closeAreaWidth
        return (idx, point.x >= closeStart)
    }
}
