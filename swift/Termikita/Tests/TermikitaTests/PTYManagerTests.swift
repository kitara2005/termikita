/// Integration tests for PTYManager — spawn shell, echo, resize, shutdown.

import XCTest
@testable import Termikita

final class PTYManagerTests: XCTestCase {

    func testSpawnAndEcho() throws {
        let pty = PTYManager(cols: 80, rows: 24)
        let expectation = self.expectation(description: "Receive echo output")
        var received = Data()

        pty.onOutput = { data in
            received.append(data)
            // Look for "hello_pty" in accumulated output
            if let text = String(data: received, encoding: .utf8),
               text.contains("hello_pty") {
                expectation.fulfill()
            }
        }

        pty.spawn()
        XCTAssertTrue(pty.isAlive)

        // Wait for shell prompt to appear, then send command
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            pty.write("echo hello_pty\n".data(using: .utf8)!)
        }

        wait(for: [expectation], timeout: 5.0)
        pty.shutdown()
    }

    func testResize() {
        let pty = PTYManager(cols: 80, rows: 24)
        pty.spawn()

        // Resize should not crash
        pty.resize(cols: 120, rows: 40)
        XCTAssertEqual(pty.cols, 120)
        XCTAssertEqual(pty.rows, 40)

        pty.shutdown()
    }

    func testShutdownNoZombie() {
        let pty = PTYManager(cols: 80, rows: 24)
        pty.spawn()
        XCTAssertTrue(pty.isAlive)

        pty.shutdown()
        // After shutdown, isAlive should be false
        XCTAssertFalse(pty.isAlive)
    }
}
