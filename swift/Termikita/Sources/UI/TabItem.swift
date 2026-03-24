/// One terminal tab: owns a PTY + buffer + view + display title.

import Foundation

final class TabItem {
    let pty: PTYManager
    let buffer: BufferManager
    let view: TerminalView
    var title: String

    init(pty: PTYManager, buffer: BufferManager, view: TerminalView, title: String = "Terminal") {
        self.pty = pty
        self.buffer = buffer
        self.view = view
        self.title = title
    }
}
