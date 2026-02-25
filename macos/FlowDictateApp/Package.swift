// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "FlowDictateApp",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(
            name: "FlowDictateApp",
            targets: ["FlowDictateApp"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "FlowDictateApp"
        ),
    ]
)
