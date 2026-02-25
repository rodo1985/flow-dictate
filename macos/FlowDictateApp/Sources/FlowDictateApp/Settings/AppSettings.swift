import Foundation

struct AppSettings: Equatable {
    let hotkeyExpression: String
    let hasAPIKey: Bool
}

struct AppRuntimeSettings: Equatable {
    let hotkeyExpression: String
    let apiKey: String?

    var hasAPIKey: Bool {
        guard let apiKey else {
            return false
        }
        return !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

enum AppSettingsDefaults {
    static let defaultHotkeyExpression = "cmd+shift+space"
    static let forcedBackend = "api"
    static let forcedOutputMode = "active-app"
    static let forcedInsertionStrategy = "direct-type"
    static let forcedConfigSource = "app-settings"
    static let keychainService = "ai.flowdictate.desktop"
    static let keychainAccount = "OPENAI_API_KEY"
    static let hotkeyDefaultsKey = "FlowDictate.Settings.HotkeyExpression"
    static let settingsMigratedDefaultsKey = "FlowDictate.SettingsMigrated"
}

enum AppSettingsError: LocalizedError, Equatable {
    case missingAPIKey
    case invalidHotkey(String)
    case keychainFailure(String)

    var errorDescription: String? {
        switch self {
        case .missingAPIKey:
            return "OpenAI API key is required. Open Settings and add your key."
        case let .invalidHotkey(reason):
            return "Hotkey is invalid: \(reason)"
        case let .keychainFailure(message):
            return "Unable to read API key from Keychain: \(message)"
        }
    }
}

struct WorkerLaunchConfiguration: Equatable {
    let environment: [String: String]
    let hotkeyExpression: String
    let hasAPIKey: Bool
}

enum AppRuntimeEnvironmentBuilder {
    static func build(
        baseEnvironment: [String: String],
        runtimeSettings: AppRuntimeSettings
    ) throws -> WorkerLaunchConfiguration {
        let canonicalHotkey: String
        do {
            canonicalHotkey = try HotkeyValidator.validate(expression: runtimeSettings.hotkeyExpression)
        } catch let validationError as HotkeyValidationError {
            throw AppSettingsError.invalidHotkey(validationError.errorDescription ?? "unknown hotkey validation failure")
        }

        guard let rawAPIKey = runtimeSettings.apiKey?
            .trimmingCharacters(in: .whitespacesAndNewlines),
            !rawAPIKey.isEmpty else {
            throw AppSettingsError.missingAPIKey
        }

        var environment = baseEnvironment
        environment["FLOW_DICTATE_OUTPUT_MODE"] = AppSettingsDefaults.forcedOutputMode
        environment["FLOW_DICTATE_BACKEND"] = AppSettingsDefaults.forcedBackend
        environment["FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"] = AppSettingsDefaults.forcedInsertionStrategy
        environment["FLOW_DICTATE_HOTKEY"] = canonicalHotkey
        environment["FLOW_DICTATE_DAEMON_CONFIG_SOURCE"] = AppSettingsDefaults.forcedConfigSource
        environment["OPENAI_API_KEY"] = rawAPIKey

        return WorkerLaunchConfiguration(
            environment: environment,
            hotkeyExpression: canonicalHotkey,
            hasAPIKey: true
        )
    }
}
