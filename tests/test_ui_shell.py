import unittest

from pyservx import ui_shell


class TestUiShell(unittest.TestCase):
    def test_shell_contains_title_and_body(self):
        html = ui_shell.shell("My Title", "<p>hello</p>")
        self.assertIn("My Title", html)
        self.assertIn("<p>hello</p>", html)

    def test_shell_contains_glass_tokens_and_theme(self):
        html = ui_shell.shell("T", "<p></p>")
        self.assertIn("--glass-bg", html)
        self.assertIn('data-theme="dark"', html)
        self.assertIn("backdrop-filter", html)

    def test_shell_includes_extra_head(self):
        html = ui_shell.shell("T", "<p></p>",
                              extra_head='<meta name="x" content="y">')
        self.assertIn('<meta name="x" content="y">', html)

    def test_shell_includes_liquid_engine_and_fallback(self):
        html = ui_shell.shell("T", "<p></p>")
        self.assertIn("lgCanvas", html)
        self.assertIn("webgl2", html.lower())
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("auroraShift", html)          # css fallback layer
        self.assertIn("#version 300 es", html)      # glsl es 3.0 shader

    def test_theme_js_keeps_legacy_key(self):
        self.assertIn("pyservx-theme", ui_shell.THEME_JS)
        self.assertIn("light-theme", ui_shell.THEME_JS)

    def test_accent_themes_defined(self):
        self.assertIn('data-accent="violet"', ui_shell.GLASS_CSS)
        for aid in ("teal", "sunset", "emerald", "rose"):
            self.assertIn(f'data-accent="{aid}"', ui_shell.GLASS_CSS)
        self.assertIn("pyservx-accent", ui_shell.THEME_JS)
        self.assertIn("lgPaletteBtn", ui_shell.THEME_JS)

    def test_backdrop_elegance_layers(self):
        self.assertIn("lg-vignette", ui_shell.GLASS_BODY_OPEN)
        self.assertIn("lg-grain", ui_shell.GLASS_BODY_OPEN)


if __name__ == "__main__":
    unittest.main()
