#if canImport(XCTest)
import XCTest
@testable import FlowDictateApp

final class AppStateEnvironmentTests: XCTestCase {
    func testBuildEnvironmentForcesAppRuntimePolicy() throws {
        let runtimeSettings = AppRuntimeSettings(
            hotkeyExpression: "command+shift+space",
            apiKey: "sk-live-key"
        )

        let launchConfiguration = try AppRuntimeEnvironmentBuilder.build(
            baseEnvironment: ["PATH": "/usr/bin"],
            runtimeSettings: runtimeSettings
        )

        XCTAssertEqual(launchConfiguration.environment["FLOW_DICTATE_OUTPUT_MODE"], "active-app")
        XCTAssertEqual(launchConfiguration.environment["FLOW_DICTATE_BACKEND"], "api")
        XCTAssertEqual(
            launchConfiguration.environment["FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"],
            "direct-type"
        )
        XCTAssertEqual(launchConfiguration.environment["FLOW_DICTATE_HOTKEY"], "cmd+shift+space")
        XCTAssertEqual(launchConfiguration.environment["FLOW_DICTATE_DAEMON_CONFIG_SOURCE"], "app-settings")
        XCTAssertEqual(launchConfiguration.environment["OPENAI_API_KEY"], "sk-live-key")
    }

    func testBuildEnvironmentBlocksStartupWithoutAPIKey() {
        let runtimeSettings = AppRuntimeSettings(
            hotkeyExpression: "cmd+shift+space",
            apiKey: nil
        )

        XCTAssertThrowsError(
            try AppRuntimeEnvironmentBuilder.build(
                baseEnvironment: [:],
                runtimeSettings: runtimeSettings
            )
        ) { error in
            XCTAssertEqual(error as? AppSettingsError, .missingAPIKey)
        }
    }

    func testBuildEnvironmentRejectsModifierOnlyHotkey() {
        let runtimeSettings = AppRuntimeSettings(
            hotkeyExpression: "ctrl+alt",
            apiKey: "sk-live-key"
        )

        XCTAssertThrowsError(
            try AppRuntimeEnvironmentBuilder.build(
                baseEnvironment: [:],
                runtimeSettings: runtimeSettings
            )
        ) { error in
            guard case let AppSettingsError.invalidHotkey(message) = error else {
                XCTFail("Expected AppSettingsError.invalidHotkey, got \(error)")
                return
            }
            XCTAssertTrue(message.contains("non-modifier"))
        }
    }
}
#endif
