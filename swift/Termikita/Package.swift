// swift-tools-version: 5.9
// Termikita — Native macOS terminal emulator

import PackageDescription

let package = Package(
    name: "Termikita",
    platforms: [
        .macOS(.v13)
    ],
    targets: [
        .executableTarget(
            name: "Termikita",
            path: "Sources",
            resources: [
                .copy("../Resources/Themes")
            ]
        ),
        .testTarget(
            name: "TermikitaTests",
            dependencies: ["Termikita"],
            path: "Tests/TermikitaTests"
        ),
    ]
)
