import Foundation
import Security

protocol APIKeyStoring {
    func loadAPIKey() throws -> String?
    func saveAPIKey(_ key: String) throws
    func deleteAPIKey() throws
}

protocol KeychainAccessing {
    func copyMatching(_ query: CFDictionary, _ result: UnsafeMutablePointer<CFTypeRef?>?) -> OSStatus
    func add(_ attributes: CFDictionary, _ result: UnsafeMutablePointer<CFTypeRef?>?) -> OSStatus
    func update(_ query: CFDictionary, _ attributesToUpdate: CFDictionary) -> OSStatus
    func delete(_ query: CFDictionary) -> OSStatus
}

struct SystemKeychainAccess: KeychainAccessing {
    func copyMatching(
        _ query: CFDictionary,
        _ result: UnsafeMutablePointer<CFTypeRef?>?
    ) -> OSStatus {
        SecItemCopyMatching(query, result)
    }

    func add(_ attributes: CFDictionary, _ result: UnsafeMutablePointer<CFTypeRef?>?) -> OSStatus {
        SecItemAdd(attributes, result)
    }

    func update(_ query: CFDictionary, _ attributesToUpdate: CFDictionary) -> OSStatus {
        SecItemUpdate(query, attributesToUpdate)
    }

    func delete(_ query: CFDictionary) -> OSStatus {
        SecItemDelete(query)
    }
}

enum KeychainStoreError: LocalizedError, Equatable {
    case emptyValue
    case unexpectedStatus(operation: String, status: OSStatus)
    case invalidData

    var errorDescription: String? {
        switch self {
        case .emptyValue:
            return "OpenAI API key cannot be empty."
        case let .unexpectedStatus(operation, status):
            return "\(operation) failed with keychain status \(status): \(Self.statusDescription(status))."
        case .invalidData:
            return "Stored OpenAI API key is not valid UTF-8 data."
        }
    }

    private static func statusDescription(_ status: OSStatus) -> String {
        guard let message = SecCopyErrorMessageString(status, nil) as String? else {
            return "Unknown Security framework error."
        }
        return message
    }
}

struct KeychainStore: APIKeyStoring {
    private let service: String
    private let account: String
    private let access: KeychainAccessing

    init(
        service: String = AppSettingsDefaults.keychainService,
        account: String = AppSettingsDefaults.keychainAccount,
        access: KeychainAccessing = SystemKeychainAccess()
    ) {
        self.service = service
        self.account = account
        self.access = access
    }

    func loadAPIKey() throws -> String? {
        var result: CFTypeRef?
        let status = access.copyMatching(baseQuery(returnData: true) as CFDictionary, &result)

        if status == errSecItemNotFound {
            return nil
        }
        guard status == errSecSuccess else {
            throw KeychainStoreError.unexpectedStatus(operation: "Load API key", status: status)
        }
        guard let data = result as? Data else {
            throw KeychainStoreError.invalidData
        }
        guard let value = String(data: data, encoding: .utf8) else {
            throw KeychainStoreError.invalidData
        }
        return value
    }

    func saveAPIKey(_ key: String) throws {
        let normalizedKey = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedKey.isEmpty else {
            throw KeychainStoreError.emptyValue
        }

        let valueData = Data(normalizedKey.utf8)
        let updateStatus = access.update(
            baseQuery(returnData: false) as CFDictionary,
            [kSecValueData as String: valueData] as CFDictionary
        )
        if updateStatus == errSecSuccess {
            return
        }
        if updateStatus != errSecItemNotFound {
            throw KeychainStoreError.unexpectedStatus(
                operation: "Update API key",
                status: updateStatus
            )
        }

        var attributes = baseQuery(returnData: false)
        attributes[kSecValueData as String] = valueData
        let addStatus = access.add(attributes as CFDictionary, nil)
        guard addStatus == errSecSuccess else {
            throw KeychainStoreError.unexpectedStatus(operation: "Save API key", status: addStatus)
        }
    }

    func deleteAPIKey() throws {
        let status = access.delete(baseQuery(returnData: false) as CFDictionary)
        if status == errSecSuccess || status == errSecItemNotFound {
            return
        }
        throw KeychainStoreError.unexpectedStatus(operation: "Delete API key", status: status)
    }

    private func baseQuery(returnData: Bool) -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        if returnData {
            query[kSecReturnData as String] = true
            query[kSecMatchLimit as String] = kSecMatchLimitOne
        }
        return query
    }
}
