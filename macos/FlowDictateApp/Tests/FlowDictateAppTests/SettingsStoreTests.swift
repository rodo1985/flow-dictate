#if canImport(XCTest)
import Foundation
import XCTest
@testable import FlowDictateApp

private final class MockAPIKeyStore: APIKeyStoring {
    var apiKey: String?
    var saveCount = 0

    func loadAPIKey() throws -> String? {
        apiKey
    }

    func saveAPIKey(_ key: String) throws {
        apiKey = key
        saveCount += 1
    }

    func deleteAPIKey() throws {
        apiKey = nil
    }
}

private final class MockDotEnvLoader: DotEnvValueLoading {
    var values: [String: String]

    init(values: [String: String]) {
        self.values = values
    }

    func loadValues(at fileURL: URL) -> [String: String] {
        _ = fileURL
        return values
    }
}

final class SettingsStoreTests: XCTestCase {
    private func makeDefaults() -> UserDefaults {
        let suiteName = "FlowDictate.SettingsStoreTests.\(UUID().uuidString)"
        guard let defaults = UserDefaults(suiteName: suiteName) else {
            fatalError("Unable to initialize test UserDefaults suite")
        }
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }

    func testLoadSettingsMigratesHotkeyAndAPIKeyFromDotEnv() throws {
        let defaults = makeDefaults()
        let keyStore = MockAPIKeyStore()
        let dotEnvLoader = MockDotEnvLoader(
            values: [
                "OPENAI_API_KEY": "sk-env-123",
                "FLOW_DICTATE_HOTKEY": "control+option+space",
            ]
        )
        let store = SettingsStore(defaults: defaults, keychainStore: keyStore, dotenvLoader: dotEnvLoader)

        let snapshot = try store.loadSettings(repositoryRootURL: URL(fileURLWithPath: "/tmp"))

        XCTAssertTrue(snapshot.appSettings.hasAPIKey)
        XCTAssertEqual(snapshot.appSettings.hotkeyExpression, "ctrl+alt+space")
        XCTAssertEqual(snapshot.runtimeSettings.apiKey, "sk-env-123")
        XCTAssertTrue(defaults.bool(forKey: AppSettingsDefaults.settingsMigratedDefaultsKey))
    }

    func testMigrationRunsOnlyOnce() throws {
        let defaults = makeDefaults()
        let keyStore = MockAPIKeyStore()
        let dotEnvLoader = MockDotEnvLoader(
            values: [
                "OPENAI_API_KEY": "sk-first",
                "FLOW_DICTATE_HOTKEY": "cmd+shift+space",
            ]
        )
        let store = SettingsStore(defaults: defaults, keychainStore: keyStore, dotenvLoader: dotEnvLoader)

        let firstSnapshot = try store.loadSettings(repositoryRootURL: URL(fileURLWithPath: "/tmp"))
        XCTAssertEqual(firstSnapshot.runtimeSettings.apiKey, "sk-first")
        XCTAssertEqual(firstSnapshot.appSettings.hotkeyExpression, "cmd+shift+space")

        dotEnvLoader.values = [
            "OPENAI_API_KEY": "sk-second",
            "FLOW_DICTATE_HOTKEY": "cmd+shift+x",
        ]
        let secondSnapshot = try store.loadSettings(repositoryRootURL: URL(fileURLWithPath: "/tmp"))

        XCTAssertEqual(secondSnapshot.runtimeSettings.apiKey, "sk-first")
        XCTAssertEqual(secondSnapshot.appSettings.hotkeyExpression, "cmd+shift+space")
        XCTAssertEqual(keyStore.saveCount, 1)
    }

    func testModifierOnlyDotEnvHotkeyFallsBackToDefault() throws {
        let defaults = makeDefaults()
        let keyStore = MockAPIKeyStore()
        let dotEnvLoader = MockDotEnvLoader(
            values: [
                "FLOW_DICTATE_HOTKEY": "ctrl+alt",
            ]
        )
        let store = SettingsStore(defaults: defaults, keychainStore: keyStore, dotenvLoader: dotEnvLoader)

        let snapshot = try store.loadSettings(repositoryRootURL: URL(fileURLWithPath: "/tmp"))

        XCTAssertEqual(
            snapshot.appSettings.hotkeyExpression,
            AppSettingsDefaults.defaultHotkeyExpression
        )
        XCTAssertNotNil(snapshot.migrationWarning)
    }
}
#endif
