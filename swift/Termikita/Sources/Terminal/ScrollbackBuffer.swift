/// Ring buffer for terminal scrollback history.
///
/// Stores lines that scroll off the top of the screen.
/// Uses a circular array with O(1) push and O(1) indexed access.

import Foundation

final class ScrollbackBuffer {
    private var buffer: [[Cell]]
    private var head: Int = 0      // next write position
    private var count_: Int = 0    // current number of stored lines
    let capacity: Int

    /// Number of lines currently in scrollback.
    var count: Int { count_ }

    init(capacity: Int = AppConstants.defaultScrollback) {
        self.capacity = capacity
        self.buffer = [[Cell]](repeating: [], count: capacity)
    }

    /// Push a line into scrollback. Overwrites oldest if full.
    func push(_ line: [Cell]) {
        buffer[head] = line
        head = (head + 1) % capacity
        if count_ < capacity {
            count_ += 1
        }
    }

    /// Get line at index (0 = oldest, count-1 = newest).
    func line(at index: Int) -> [Cell] {
        guard index >= 0 && index < count_ else { return [] }
        // Convert logical index to physical position
        let physicalIndex: Int
        if count_ < capacity {
            physicalIndex = index
        } else {
            physicalIndex = (head + index) % capacity
        }
        return buffer[physicalIndex]
    }

    /// Get a range of lines (for viewport rendering).
    func lines(from start: Int, count: Int) -> [[Cell]] {
        var result: [[Cell]] = []
        let end = min(start + count, count_)
        for i in start..<end {
            result.append(line(at: i))
        }
        return result
    }

    /// Clear all scrollback history.
    func clear() {
        head = 0
        count_ = 0
    }
}
