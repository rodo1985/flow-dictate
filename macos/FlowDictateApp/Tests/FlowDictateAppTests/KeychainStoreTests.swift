#if canImport(XCTest)
import Security
import XCTest
@testable import FlowDictateApp

private final class InMemoryKeychainAccess: KeychainAccessing {
    var storedData: Data?
    var copyStatusOverride: OSStatus?
    var updateStatusOverride: OSStatus?
    var addStatusOverride: OSStatus?
    var deleteStatusOverride: OSStatus?

    func copyMatching(_ query: CFDictionary, _ result: UnsafeMutablePointer<CFTypeRef?>?) -> OSStatus {
        _ = query
        if let copyStatusOverride {
            return copyStatusOverride
        }
        guard let storedData else {
            return errSecItemNotFound
        }
        result?.pointee = storedData as CFData
        return errSecSuccess
    }

    func add(_ attributes: CFDictionary, _ result: UnsafeMutablePointer<CFTypeRef?>?) -> OSStatus {
        _ = result
        if let addStatusOverride {
            return addStatusOverride
        }
        let attributesDictionary = attributes as NSDictionary
        storedData = attributesDictionary[kSecValueData as String] as? Data
        return errSecSuccess
    }

    func update(_ query: CFDictionary, _ attributesToUpdate: CFDictionary) -> OSStatus {
        _ = query
        if let updateStatusOverride {
            return updateStatusOverride
        }
        guard storedData != nil else {
            return errSecItemNotFound
        }
        let attributesDictionary = attributesToUpdate as NSDictionary
        storedData = attributesDictionary[kSecValueData as String] as? Data
        return errSecSuccess
    }

    func delete(_ query: CFDictionary) -> OSStatus {
        _ = query
        if let deleteStatusOverride {
            return deleteStatusOverride
        }
        guard storedData != nil else {
            return errSecItemNotFound
        }
        storedData = nil
        return errSecSuccess
    }
}

final class KeychainStoreTests: XCTestCase {
    func testSaveLoadDeleteAPIKey() throws {
        let access = InMemoryKeychainAccess()
        let store = KeychainStore(service: "test-service", account: "test-account", access: access)

        XCTAssertNil(try store.loadAPIKey())

        try store.saveAPIKey("sk-test-key")
        XCTAssertEqual(try store.loadAPIKey(), "sk-test-key")

        try store.deleteAPIKey()
        XCTAssertNil(try store.loadAPIKey())
    }

    func testSaveReturnsTypedErrorForUnexpectedStatus() {
        let access = InMemoryKeychainAccess()
        access.updateStatusOverride = errSecAuthFailed
        let store = KeychainStore(service: "test-service", account: "test-account", access: access)

        XCTAssertThrowsError(try store.saveAPIKey("sk-test-key")) { error in
            guard case let KeychainStoreError.unexpectedStatus(operation, status) = error else {
                XCTFail("Expected KeychainStoreError.unexpectedStatus, got \(error)")
                return
            }
            XCTAssertEqual(operation, "Update API key")
            XCTAssertEqual(status, errSecAuthFailed)
        }
    }
}
#endif
