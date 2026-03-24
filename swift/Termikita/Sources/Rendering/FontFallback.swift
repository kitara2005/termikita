/// Font fallback cascade and Nerd Font detection.
///
/// Uses CTFontCreateForString to find fonts for missing glyphs.
/// Detects installed Nerd Fonts for PUA (Private Use Area) characters.
/// PUA chars (U+E000-U+F8FF): Powerline/NerdFont icons — isolated in
/// single-cell rendering to prevent grid displacement.

import AppKit
import CoreText

final class FontFallback {
    private let primaryFont: CTFont
    /// LRU cache: Character → resolved CTFont (or nil = use space).
    private var cache: [Character: CTFont?] = [:]
    /// Detected Nerd Font descriptors for PUA fallback.
    private var nerdFontDescriptors: [CTFontDescriptor] = []

    init(primaryFont: NSFont) {
        self.primaryFont = primaryFont as CTFont
        detectNerdFonts()
    }

    // MARK: - PUA detection

    /// Returns true if the character is in the Private Use Area (Powerline/NerdFont).
    static func isPUA(_ ch: Character) -> Bool {
        guard let scalar = ch.unicodeScalars.first else { return false }
        let v = scalar.value
        return (v >= 0xE000 && v <= 0xF8FF)
    }

    // MARK: - Font resolution

    /// Find the best font for a character. Returns nil if no font has the glyph.
    func resolve(_ ch: Character) -> CTFont? {
        if let cached = cache[ch] { return cached }

        let font: CTFont?
        if FontFallback.isPUA(ch) {
            font = resolvePUA(ch)
        } else {
            font = resolveNonPUA(ch)
        }

        // LRU eviction (keep cache under 4096)
        if cache.count > 4096 {
            // Remove ~25% of entries (simple eviction)
            let removeCount = cache.count / 4
            for key in cache.keys.prefix(removeCount) {
                cache.removeValue(forKey: key)
            }
        }

        cache[ch] = font
        return font
    }

    /// Resolve non-PUA character via CTFontCreateForString.
    private func resolveNonPUA(_ ch: Character) -> CTFont? {
        let str = String(ch) as CFString
        let range = CFRange(location: 0, length: CFStringGetLength(str))
        let resolved = CTFontCreateForString(primaryFont, str, range)
        return resolved
    }

    /// Resolve PUA character — try Nerd Font descriptors first, then system fallback.
    private func resolvePUA(_ ch: Character) -> CTFont? {
        let str = String(ch) as CFString
        let range = CFRange(location: 0, length: CFStringGetLength(str))

        // Try Nerd Font descriptors first
        for desc in nerdFontDescriptors {
            let size = CTFontGetSize(primaryFont)
            let candidate = CTFontCreateWithFontDescriptor(desc, size, nil)
            // Check if this font has a glyph for the character
            var glyph = CGGlyph(0)
            var unichar = String(ch).utf16.first ?? 0
            if CTFontGetGlyphsForCharacters(candidate, &unichar, &glyph, 1), glyph != 0 {
                return candidate
            }
        }

        // System fallback (may find LastResort or other system font)
        let resolved = CTFontCreateForString(primaryFont, str, range)
        // Verify the resolved font actually has the glyph
        var glyph = CGGlyph(0)
        var unichar = String(ch).utf16.first ?? 0
        if CTFontGetGlyphsForCharacters(resolved, &unichar, &glyph, 1), glyph != 0 {
            return resolved
        }

        return nil // No font has this glyph — render as space
    }

    // MARK: - Nerd Font detection

    /// Scan installed fonts for Nerd Font families.
    private func detectNerdFonts() {
        let fm = NSFontManager.shared
        let families = fm.availableFontFamilies

        let nerdKeywords = ["Nerd Font", "NerdFont", "Nerd"]
        for family in families {
            for keyword in nerdKeywords {
                if family.contains(keyword) {
                    let attrs: [String: Any] = [kCTFontFamilyNameAttribute as String: family]
                    let desc = CTFontDescriptorCreateWithAttributes(attrs as CFDictionary)
                    nerdFontDescriptors.append(desc)
                    break
                }
            }
        }
    }

    /// Invalidate cache (call on font change).
    func invalidate() {
        cache.removeAll()
        detectNerdFonts()
    }
}
