#if canImport(XCTest)
import XCTest
@testable import FlowDictateApp

final class HotkeyValidatorTests: XCTestCase {
    func testValidateAcceptsCanonicalHotkey() throws {
        let canonical = try HotkeyValidator.validate(expression: "cmd+shift+space")
        XCTAssertEqual(canonical, "cmd+shift+space")
    }

    func testValidateCanonicalizesAliasesAndOrder() throws {
        let canonical = try HotkeyValidator.validate(expression: "option+command+a")
        XCTAssertEqual(canonical, "cmd+alt+a")
    }

    func testValidateRejectsModifierOnlyHotkey() {
        XCTAssertThrowsError(try HotkeyValidator.validate(expression: "ctrl+alt")) { error in
            XCTAssertEqual(error as? HotkeyValidationError, .modifierOnly)
        }
    }

    func testValidateRejectsUnknownTokens() {
        XCTAssertThrowsError(try HotkeyValidator.validate(expression: "cmd+f13")) { error in
            XCTAssertEqual(error as? HotkeyValidationError, .invalidToken("f13"))
        }
    }
}
#endif
