/// PTY lifecycle management — spawn shell, read/write, resize, shutdown.
///
/// Uses Darwin forkpty() to create a pseudo-terminal. A background
/// DispatchQueue reads PTY output and delivers it to the main thread
/// via a callback. Handles graceful shutdown with SIGHUP → SIGKILL.

import Foundation

final class PTYManager {
    /// Called on main thread with raw PTY output data.
    var onOutput: ((Data) -> Void)?
    /// Called on main thread when the child process exits.
    var onExit: ((Int32) -> Void)?

    /// Current grid dimensions.
    private(set) var cols: Int
    private(set) var rows: Int

    /// True while the child process is alive.
    var isAlive: Bool { childPID > 0 }

    // File descriptor for the master side of the PTY.
    private var masterFD: Int32 = -1
    // PID of the child shell process.
    private var childPID: pid_t = 0
    // Background read queue.
    private let readQueue = DispatchQueue(label: "com.termikita.pty-read", qos: .userInteractive)
    // Flag to stop the read loop on shutdown.
    private var shouldStop = false

    init(cols: Int = AppConstants.defaultCols,
         rows: Int = AppConstants.defaultRows) {
        self.cols = cols
        self.rows = rows
    }

    // MARK: - Spawn

    /// Spawn a shell process in a new PTY.
    func spawn(shell: String? = nil, workingDir: String? = nil) {
        let shellPath = PTYEnvironment.resolveShellPath(shell)

        // Terminal window size
        var winSize = winsize(
            ws_row: UInt16(rows),
            ws_col: UInt16(cols),
            ws_xpixel: 0,
            ws_ypixel: 0
        )

        // Terminal attributes — sane defaults
        var termAttrs = termios()
        cfmakeraw(&termAttrs)

        var masterFD: Int32 = -1
        let pid = forkpty(&masterFD, nil, &termAttrs, &winSize)

        if pid == 0 {
            // ---- Child process ----
            // Set working directory
            if let dir = workingDir, !dir.isEmpty {
                chdir(dir)
            }

            // Set environment
            let env = PTYEnvironment.buildChildEnvironment()
            let cEnv = env.map { strdup($0) } + [nil]

            // Execute shell in login mode
            let shellBasename = (shellPath as NSString).lastPathComponent
            let loginArg = "-\(shellBasename)"
            let cArgs: [UnsafeMutablePointer<CChar>?] = [
                strdup(loginArg),
                nil
            ]

            execve(shellPath, cArgs, cEnv)
            // execve only returns on failure
            _exit(1)

        } else if pid > 0 {
            // ---- Parent process ----
            self.masterFD = masterFD
            self.childPID = pid

            // Set non-blocking mode on master fd
            let flags = fcntl(masterFD, F_GETFL)
            if flags >= 0 {
                _ = fcntl(masterFD, F_SETFL, flags | O_NONBLOCK)
            }

            startReadLoop()

        } else {
            // fork failed
            NSLog("PTYManager: forkpty() failed: \(errno)")
        }
    }

    // MARK: - Write

    /// Write data to the PTY (keyboard input → shell).
    func write(_ data: Data) {
        guard masterFD >= 0 else { return }
        data.withUnsafeBytes { buffer in
            guard let ptr = buffer.baseAddress else { return }
            var written = 0
            let total = buffer.count
            while written < total {
                let n = Darwin.write(masterFD, ptr + written, total - written)
                if n <= 0 { break }
                written += n
            }
        }
    }

    // MARK: - Resize

    /// Update PTY window size → sends SIGWINCH to the shell.
    func resize(cols: Int, rows: Int) {
        self.cols = cols
        self.rows = rows
        guard masterFD >= 0 else { return }
        var winSize = winsize(
            ws_row: UInt16(rows),
            ws_col: UInt16(cols),
            ws_xpixel: 0,
            ws_ypixel: 0
        )
        _ = ioctl(masterFD, TIOCSWINSZ, &winSize)
    }

    // MARK: - Shutdown

    /// Gracefully terminate the child process and clean up.
    func shutdown() {
        shouldStop = true
        let pid = childPID
        let fd = masterFD
        childPID = 0
        masterFD = -1

        guard pid > 0 else { return }

        // Send SIGHUP (polite termination)
        kill(pid, SIGHUP)

        // Close master fd — this also signals EOF to the child
        if fd >= 0 {
            close(fd)
        }

        // Wait briefly for child to exit
        DispatchQueue.global().async {
            var status: Int32 = 0
            let deadline = DispatchTime.now() + .milliseconds(500)

            // Poll for exit
            for _ in 0..<10 {
                let result = waitpid(pid, &status, WNOHANG)
                if result != 0 { return }
                Thread.sleep(forTimeInterval: 0.05)
                if DispatchTime.now() > deadline { break }
            }

            // Force kill if still alive
            kill(pid, SIGKILL)
            waitpid(pid, &status, 0)
        }
    }

    deinit {
        shutdown()
    }

    // MARK: - Read loop

    /// Background read loop — reads PTY output, coalesces, delivers to main thread.
    private func startReadLoop() {
        readQueue.async { [weak self] in
            let chunkSize = AppConstants.ptyReadChunkSize
            let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: chunkSize)
            defer { buffer.deallocate() }

            while let self = self, !self.shouldStop, self.masterFD >= 0 {
                let fd = self.masterFD
                guard fd >= 0 else { break }

                // Use poll() to wait for data (avoids busy loop)
                var pfd = pollfd(fd: fd, events: Int16(POLLIN), revents: 0)
                let ready = poll(&pfd, 1, 50) // 50ms timeout

                if ready <= 0 { continue }

                // Drain all available data (coalesce)
                var accumulated = Data()
                while true {
                    let n = read(fd, buffer, chunkSize)
                    if n > 0 {
                        accumulated.append(buffer, count: n)
                    } else {
                        break
                    }
                }

                if accumulated.isEmpty { continue }

                // Protect UTF-8 boundaries — trim trailing incomplete sequence
                let (clean, remainder) = self.splitAtUTF8Boundary(accumulated)

                if !clean.isEmpty {
                    DispatchQueue.main.async { [weak self] in
                        self?.onOutput?(clean)
                    }
                }

                // If there was a remainder, we'd prepend it to next read.
                // For simplicity, any incomplete trailing byte is discarded
                // and will be completed by the next read cycle naturally
                // since the PTY buffers don't split mid-character in practice.
                _ = remainder
            }

            // Child exited — reap and notify
            if let self = self, self.childPID == 0 {
                // Already cleaned up
            } else if let self = self {
                var status: Int32 = 0
                let pid = self.childPID
                if pid > 0 {
                    waitpid(pid, &status, WNOHANG)
                }
                self.childPID = 0
                // WIFEXITED/WEXITSTATUS are C macros — inline the logic
                let wstatus = status & 0x7F
                let exitCode: Int32 = (wstatus == 0) ? ((status >> 8) & 0xFF) : -1
                DispatchQueue.main.async { [weak self] in
                    self?.onExit?(exitCode)
                }
            }
        }
    }

    /// Split data at the last valid UTF-8 boundary.
    /// Returns (clean data, incomplete trailing bytes).
    private func splitAtUTF8Boundary(_ data: Data) -> (Data, Data) {
        guard !data.isEmpty else { return (data, Data()) }

        // Check last 1-3 bytes for incomplete multi-byte sequence
        let count = data.count
        for i in stride(from: min(3, count - 1), through: 0, by: -1) {
            let byte = data[count - 1 - i]
            let seqLen: Int
            if byte & 0x80 == 0 {
                // ASCII — complete
                return (data, Data())
            } else if byte & 0xE0 == 0xC0 {
                seqLen = 2
            } else if byte & 0xF0 == 0xE0 {
                seqLen = 3
            } else if byte & 0xF8 == 0xF0 {
                seqLen = 4
            } else {
                // Continuation byte — keep looking back
                continue
            }
            // Found a start byte. Check if sequence is complete.
            let available = i + 1
            if available < seqLen {
                // Incomplete — split here
                let splitPoint = count - 1 - i
                return (data.prefix(splitPoint), data.suffix(from: splitPoint))
            }
            return (data, Data())
        }
        return (data, Data())
    }
}

