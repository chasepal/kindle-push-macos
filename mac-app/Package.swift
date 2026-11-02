// swift-tools-version: 6.0
import PackageDescription
let package = Package(
    name: "KindlePush",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "KindlePush", targets: ["KindlePush"])],
    targets: [.executableTarget(name: "KindlePush")],
    swiftLanguageModes: [.v5]
)
