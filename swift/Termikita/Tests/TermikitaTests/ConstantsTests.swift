/// Basic smoke tests for Termikita constants.

import XCTest
@testable import Termikita

final class ConstantsTests: XCTestCase {
    func testAppName() {
        XCTAssertEqual(AppConstants.appName, "Termikita")
    }

    func testDefaultGridSize() {
        XCTAssertEqual(AppConstants.defaultCols, 80)
        XCTAssertEqual(AppConstants.defaultRows, 24)
    }

    func testFontSizeBounds() {
        XCTAssertTrue(AppConstants.fontSizeMin < AppConstants.fontSizeMax)
        XCTAssertTrue(AppConstants.defaultFontSize >= AppConstants.fontSizeMin)
        XCTAssertTrue(AppConstants.defaultFontSize <= AppConstants.fontSizeMax)
    }
}
