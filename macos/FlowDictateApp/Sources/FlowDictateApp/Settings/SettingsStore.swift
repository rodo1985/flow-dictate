import Foundation

protocol DotEnvValueLoading {
    func loadValues(at fileURL: URL) -> [String: String]
}

struct DotEnvLoader: DotEnvValueLoading {
    func loadValues(at fileURL: URL) -> [String: String] {
        guard let content = try? String(contentsOf: fileURL, encoding: .utf8) else {
            return [:]
        }

        var values: [String: String] = [:]
        for rawLine in content.split(whereSeparator: \.isNewline) {
            var line = String(rawLine).trimmingCharacters(in: .whitespacesAndNewlines)
            if line.isEmpty || line.hasPrefix("#") {
                continue
            }
            if line.hasPrefix("export ") {
                line = String(line.dropFirst("export ".count))
                    .trimmingCharacters(in: .whitespacesAndNewlines)
            }
            guard let delimiterIndex = line.firstIndex(of: "=") else {
                continue
            }

            let key = String(line[..<delimiterIndex]).trimmingCharacters(in: .whitespacesAndNewlines)
            var value = String(line[line.index(after: delimiterIndex)...])
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if value.count >= 2,
               ((value.hasPrefix("\"") && value.hasSuffix("\""))
                   || (value.hasPrefix("'") && value.hasSuffix("'"))) {
                value = String(value.dropFirst().dropLast())
            }
            if !key.isEmpty {
                values[key] = value
            }
        }

        return values
    }
}

struct SettingsSnapshot: Equatable {
    let appSettings: AppSettings
    let runtimeSettings: AppRuntimeSettings
    let migrationWarning: String?
}

@MainActor
final class SettingsStore {
    private let defaults: UserDefaults
    private let keychainStore: APIKeyStoring
    private let dotenvLoader: DotEnvValueLoading

    init(
        defaults: UserDefaults = .standard,
        keychainStore: APIKeyStoring = KeychainStore(),
        dotenvLoader: DotEnvValueLoading = DotEnvLoader()
    ) {
        self.defaults = defaults
        self.keychainStore = keychainStore
        self.dotenvLoader = dotenvLoader
    }

    func loadSettings(repositoryRootURL: URL) throws -> SettingsSnapshot {
        let migrationWarning = try performOneTimeMigrationIfNeeded(repositoryRootURL: repositoryRootURL)
        let hotkey = try loadHotkeyExpression()
        let apiKey = try keychainStore.loadAPIKey()
        let runtimeSettings = AppRuntimeSettings(hotkeyExpression: hotkey, apiKey: apiKey)
        return SettingsSnapshot(
            appSettings: AppSettings(
                hotkeyExpression: hotkey,
                hasAPIKey: runtimeSettings.hasAPIKey
            ),
            runtimeSettings: runtimeSettings,
            migrationWarning: migrationWarning
        )
    }

    func saveHotkeyExpression(_ expression: String) throws -> String {
        do {
            let canonicalExpression = try HotkeyValidator.validate(expression: expression)
            defaults.set(canonicalExpression, forKey: AppSettingsDefaults.hotkeyDefaultsKey)
            return canonicalExpression
        } catch let validationError as HotkeyValidationError {
            throw AppSettingsError.invalidHotkey(
                validationError.errorDescription ?? "unknown hotkey validation failure"
            )
        }
    }

    func saveAPIKey(_ apiKey: String) throws {
        do {
            try keychainStore.saveAPIKey(apiKey)
        } catch let keychainError as KeychainStoreError {
            throw AppSettingsError.keychainFailure(keychainError.errorDescription ?? "unknown keychain error")
        } catch {
            throw AppSettingsError.keychainFailure(error.localizedDescription)
        }
    }

    func clearAPIKey() throws {
        do {
            try keychainStore.deleteAPIKey()
        } catch let keychainError as KeychainStoreError {
            throw AppSettingsError.keychainFailure(keychainError.errorDescription ?? "unknown keychain error")
        } catch {
            throw AppSettingsError.keychainFailure(error.localizedDescription)
        }
    }

    private func loadHotkeyExpression() throws -> String {
        if let storedHotkey = defaults.string(forKey: AppSettingsDefaults.hotkeyDefaultsKey),
           !storedHotkey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return try saveHotkeyExpression(storedHotkey)
        }

        defaults.set(
            AppSettingsDefaults.defaultHotkeyExpression,
            forKey: AppSettingsDefaults.hotkeyDefaultsKey
        )
        return AppSettingsDefaults.defaultHotkeyExpression
    }

    private func performOneTimeMigrationIfNeeded(repositoryRootURL: URL) throws -> String? {
        if defaults.bool(forKey: AppSettingsDefaults.settingsMigratedDefaultsKey) {
            return nil
        }

        let dotenvValues = dotenvLoader.loadValues(
            at: repositoryRootURL.appendingPathComponent(".env")
        )
        var warning: String?

        do {
            let keychainAPIKey = try keychainStore.loadAPIKey()
            let hasExistingAPIKey = !(keychainAPIKey?
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .isEmpty ?? true)
            if !hasExistingAPIKey,
               let envAPIKey = dotenvValues["OPENAI_API_KEY"],
               !envAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                try keychainStore.saveAPIKey(envAPIKey)
            }
        } catch let keychainError as KeychainStoreError {
            throw AppSettingsError.keychainFailure(keychainError.errorDescription ?? "unknown keychain error")
        } catch {
            throw AppSettingsError.keychainFailure(error.localizedDescription)
        }

        if defaults.string(forKey: AppSettingsDefaults.hotkeyDefaultsKey) == nil {
            if let envHotkey = dotenvValues["FLOW_DICTATE_HOTKEY"],
               !envHotkey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                do {
                    let canonical = try HotkeyValidator.validate(expression: envHotkey)
                    defaults.set(canonical, forKey: AppSettingsDefaults.hotkeyDefaultsKey)
                } catch HotkeyValidationError.modifierOnly {
                    defaults.set(
                        AppSettingsDefaults.defaultHotkeyExpression,
                        forKey: AppSettingsDefaults.hotkeyDefaultsKey
                    )
                    warning = (
                        "Stored .env hotkey was modifier-only and has been replaced with "
                            + "\(AppSettingsDefaults.defaultHotkeyExpression)."
                    )
                } catch {
                    defaults.set(
                        AppSettingsDefaults.defaultHotkeyExpression,
                        forKey: AppSettingsDefaults.hotkeyDefaultsKey
                    )
                }
            } else {
                defaults.set(
                    AppSettingsDefaults.defaultHotkeyExpression,
                    forKey: AppSettingsDefaults.hotkeyDefaultsKey
                )
            }
        }

        defaults.set(true, forKey: AppSettingsDefaults.settingsMigratedDefaultsKey)
        return warning
    }
}
