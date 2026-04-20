#!/usr/bin/env python3
"""
Unit tests for GlassThemeSystem class.
"""

import unittest
from pyservx.glass_theme_system import (
    GlassThemeSystem,
    ThemeConfig,
    ColorPalette,
)


class TestThemeConfig(unittest.TestCase):
    """Test ThemeConfig validation and functionality."""
    
    def test_default_config_is_valid(self):
        """Test that default configuration is valid."""
        config = ThemeConfig()
        self.assertTrue(config.validate())
    
    def test_blur_strength_validation(self):
        """Test blur strength must be between 0 and 20."""
        # Valid values
        config = ThemeConfig(blur_strength=0)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(blur_strength=20)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(blur_strength=10)
        self.assertTrue(config.validate())
        
        # Invalid values
        config = ThemeConfig(blur_strength=-1)
        self.assertFalse(config.validate())
        
        config = ThemeConfig(blur_strength=21)
        self.assertFalse(config.validate())
    
    def test_shadow_intensity_validation(self):
        """Test shadow intensity must be between 0.0 and 1.0."""
        # Valid values
        config = ThemeConfig(shadow_intensity=0.0)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(shadow_intensity=1.0)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(shadow_intensity=0.5)
        self.assertTrue(config.validate())
        
        # Invalid values
        config = ThemeConfig(shadow_intensity=-0.1)
        self.assertFalse(config.validate())
        
        config = ThemeConfig(shadow_intensity=1.1)
        self.assertFalse(config.validate())
    
    def test_border_radius_validation(self):
        """Test border radius must be between 0 and 24."""
        # Valid values
        config = ThemeConfig(border_radius=0)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(border_radius=24)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(border_radius=12)
        self.assertTrue(config.validate())
        
        # Invalid values
        config = ThemeConfig(border_radius=-1)
        self.assertFalse(config.validate())
        
        config = ThemeConfig(border_radius=25)
        self.assertFalse(config.validate())
    
    def test_animation_duration_validation(self):
        """Test animation duration must be positive."""
        # Valid values
        config = ThemeConfig(animation_duration=0.1)
        self.assertTrue(config.validate())
        
        config = ThemeConfig(animation_duration=1.0)
        self.assertTrue(config.validate())
        
        # Invalid values
        config = ThemeConfig(animation_duration=0)
        self.assertFalse(config.validate())
        
        config = ThemeConfig(animation_duration=-0.1)
        self.assertFalse(config.validate())


class TestColorPalette(unittest.TestCase):
    """Test ColorPalette functionality."""
    
    def test_default_palette_has_black_and_green(self):
        """Test that default palette uses black and green colors."""
        palette = ColorPalette()
        self.assertEqual(palette.base_black, "#000000")
        self.assertEqual(palette.accent_green, "#00ff00")
    
    def test_get_color_returns_correct_values(self):
        """Test get_color method returns correct color values."""
        palette = ColorPalette()
        
        self.assertEqual(palette.get_color("base_black"), "#000000")
        self.assertEqual(palette.get_color("accent_green"), "#00ff00")
        self.assertEqual(palette.get_color("text_primary"), "#00ff00")
        self.assertEqual(palette.get_color("bg_glass_primary"), "rgba(0, 0, 0, 0.7)")
    
    def test_get_color_returns_default_for_unknown_type(self):
        """Test get_color returns base_black for unknown color types."""
        palette = ColorPalette()
        self.assertEqual(palette.get_color("unknown_color"), "#000000")


class TestGlassThemeSystem(unittest.TestCase):
    """Test GlassThemeSystem functionality."""
    
    def test_initialization_with_defaults(self):
        """Test GlassThemeSystem initializes with default config and palette."""
        theme = GlassThemeSystem()
        self.assertIsNotNone(theme.config)
        self.assertIsNotNone(theme.color_palette)
        self.assertTrue(theme.config.validate())
    
    def test_initialization_with_custom_config(self):
        """Test GlassThemeSystem initializes with custom configuration."""
        config = ThemeConfig(blur_strength=15, border_radius=16)
        theme = GlassThemeSystem(config=config)
        self.assertEqual(theme.config.blur_strength, 15)
        self.assertEqual(theme.config.border_radius, 16)
    
    def test_initialization_rejects_invalid_config(self):
        """Test GlassThemeSystem raises error for invalid configuration."""
        config = ThemeConfig(blur_strength=25)  # Invalid: > 20
        with self.assertRaises(ValueError):
            GlassThemeSystem(config=config)
    
    def test_apply_glass_effect_panel(self):
        """Test applying glass effect to panel component."""
        theme = GlassThemeSystem()
        styles = theme.apply_glass_effect("panel")
        
        self.assertIn("backdrop-filter", styles)
        self.assertIn("blur", styles["backdrop-filter"])
        self.assertIn("border-radius", styles)
        self.assertIn("background", styles)
        self.assertIn("border", styles)
        self.assertIn("box-shadow", styles)
    
    def test_apply_glass_effect_button(self):
        """Test applying glass effect to button component."""
        theme = GlassThemeSystem()
        styles = theme.apply_glass_effect("button")
        
        self.assertIn("backdrop-filter", styles)
        self.assertIn("background", styles)
        self.assertIn("border", styles)
        self.assertIn("color", styles)
        self.assertEqual(styles["color"], theme.color_palette.text_primary)
    
    def test_apply_glass_effect_input(self):
        """Test applying glass effect to input component."""
        theme = GlassThemeSystem()
        styles = theme.apply_glass_effect("input")
        
        self.assertIn("backdrop-filter", styles)
        self.assertIn("background", styles)
        self.assertIn("box-shadow", styles)
        self.assertIn("inset", styles["box-shadow"])
    
    def test_apply_glass_effect_table(self):
        """Test applying glass effect to table component."""
        theme = GlassThemeSystem()
        styles = theme.apply_glass_effect("table")
        
        self.assertIn("backdrop-filter", styles)
        self.assertIn("background", styles)
        self.assertIn("border", styles)
    
    def test_update_color_palette(self):
        """Test updating color palette."""
        theme = GlassThemeSystem()
        new_palette = ColorPalette(accent_green="#00cc00")
        
        result = theme.update_color_palette(new_palette)
        
        self.assertEqual(theme.color_palette.accent_green, "#00cc00")
        self.assertIs(result, theme)  # Method chaining
    
    def test_calculate_blur_radius_standard_density(self):
        """Test blur radius calculation for standard screen density."""
        config = ThemeConfig(blur_strength=12)
        theme = GlassThemeSystem(config=config)
        
        blur = theme.calculate_blur_radius(1.0)
        self.assertEqual(blur, 12)
    
    def test_calculate_blur_radius_retina_density(self):
        """Test blur radius calculation for retina screen density."""
        config = ThemeConfig(blur_strength=12)
        theme = GlassThemeSystem(config=config)
        
        blur = theme.calculate_blur_radius(2.0)
        self.assertEqual(blur, 20)  # Capped at 20
    
    def test_calculate_blur_radius_caps_at_20(self):
        """Test blur radius is capped at 20px."""
        config = ThemeConfig(blur_strength=15)
        theme = GlassThemeSystem(config=config)
        
        blur = theme.calculate_blur_radius(3.0)
        self.assertEqual(blur, 20)
    
    def test_generate_shadow(self):
        """Test shadow generation."""
        theme = GlassThemeSystem()
        shadow = theme.generate_shadow((0, 0), (100, 100))
        
        self.assertIsInstance(shadow, str)
        self.assertIn("rgba", shadow)
        self.assertIn("inset", shadow)
    
    def test_generate_shadow_with_custom_intensity(self):
        """Test shadow generation with custom intensity."""
        theme = GlassThemeSystem()
        shadow = theme.generate_shadow((0, 0), (100, 100), intensity=0.5)
        
        self.assertIsInstance(shadow, str)
        self.assertIn("0.5", shadow)
    
    def test_generate_css_variables(self):
        """Test CSS variables generation."""
        theme = GlassThemeSystem()
        css = theme.generate_css_variables()
        
        self.assertIn(":root", css)
        self.assertIn("--color-black", css)
        self.assertIn("--color-green", css)
        self.assertIn("--text-primary", css)
        self.assertIn("--bg-glass-primary", css)
        self.assertIn("--border-default", css)
        self.assertIn("--blur-strength", css)
    
    def test_generate_glass_panel_css(self):
        """Test glass panel CSS generation."""
        theme = GlassThemeSystem()
        css = theme.generate_glass_panel_css()
        
        self.assertIn(".glass-panel", css)
        self.assertIn("backdrop-filter", css)
        self.assertIn("border-radius", css)
        self.assertIn("::before", css)
        self.assertIn("linear-gradient", css)
    
    def test_generate_glass_button_css(self):
        """Test glass button CSS generation."""
        theme = GlassThemeSystem()
        css = theme.generate_glass_button_css()
        
        self.assertIn(".glass-button", css)
        self.assertIn(":hover", css)
        self.assertIn(":active", css)
        self.assertIn(":focus", css)
        self.assertIn("cursor: pointer", css)
    
    def test_generate_glass_input_css(self):
        """Test glass input CSS generation."""
        theme = GlassThemeSystem()
        css = theme.generate_glass_input_css()
        
        self.assertIn(".glass-input", css)
        self.assertIn("::placeholder", css)
        self.assertIn(":focus", css)
        self.assertIn("outline: none", css)
    
    def test_blur_strength_affects_backdrop_filter(self):
        """Test that blur strength configuration affects backdrop-filter."""
        config = ThemeConfig(blur_strength=8)
        theme = GlassThemeSystem(config=config)
        styles = theme.apply_glass_effect("panel")
        
        self.assertIn("blur(8px)", styles["backdrop-filter"])
    
    def test_border_radius_affects_styles(self):
        """Test that border radius configuration affects styles."""
        config = ThemeConfig(border_radius=16)
        theme = GlassThemeSystem(config=config)
        styles = theme.apply_glass_effect("panel")
        
        self.assertEqual(styles["border-radius"], "16px")
    
    def test_animation_duration_affects_transition(self):
        """Test that animation duration affects transition property."""
        config = ThemeConfig(animation_duration=0.5)
        theme = GlassThemeSystem(config=config)
        styles = theme.apply_glass_effect("panel")
        
        self.assertIn("0.5s", styles["transition"])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_zero_blur_strength(self):
        """Test glass effect with zero blur strength."""
        config = ThemeConfig(blur_strength=0)
        theme = GlassThemeSystem(config=config)
        styles = theme.apply_glass_effect("panel")
        
        self.assertIn("blur(0px)", styles["backdrop-filter"])
    
    def test_maximum_blur_strength(self):
        """Test glass effect with maximum blur strength."""
        config = ThemeConfig(blur_strength=20)
        theme = GlassThemeSystem(config=config)
        styles = theme.apply_glass_effect("panel")
        
        self.assertIn("blur(20px)", styles["backdrop-filter"])
    
    def test_zero_shadow_intensity(self):
        """Test shadow generation with zero intensity."""
        config = ThemeConfig(shadow_intensity=0.0)
        theme = GlassThemeSystem(config=config)
        shadow = theme.generate_shadow((0, 0), (100, 100))
        
        self.assertIn("0.0", shadow)
    
    def test_maximum_shadow_intensity(self):
        """Test shadow generation with maximum intensity."""
        config = ThemeConfig(shadow_intensity=1.0)
        theme = GlassThemeSystem(config=config)
        shadow = theme.generate_shadow((0, 0), (100, 100))
        
        self.assertIn("1.0", shadow)


if __name__ == "__main__":
    unittest.main()
