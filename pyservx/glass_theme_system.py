#!/usr/bin/env python3
"""
Glass Theme System for PyServeX v3.0.1
Implements Apple iOS glass morphism design principles with black and green color palette.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class BorderRadiusConfig:
    """Border radius configuration for different component types."""
    small: int = 8   # buttons, inputs
    medium: int = 12  # panels
    large: int = 16   # cards, containers
    xl: int = 20      # modals, dialogs
    
    def get_radius(self, size: str) -> int:
        """
        Get border radius value by size.
        
        Args:
            size: Size identifier ("small", "medium", "large", "xl")
            
        Returns:
            int: Border radius in pixels
        """
        radius_map = {
            "small": self.small,
            "medium": self.medium,
            "large": self.large,
            "xl": self.xl,
        }
        return radius_map.get(size, self.medium)


@dataclass
class ThemeConfig:
    """Configuration for glass theme effects."""
    glass_effect_enabled: bool = True
    blur_strength: int = 12
    shadow_intensity: float = 0.3
    border_radius: int = 12
    animation_duration: float = 0.3
    border_radius_config: BorderRadiusConfig = None
    
    def __post_init__(self):
        """Initialize border radius config if not provided."""
        if self.border_radius_config is None:
            self.border_radius_config = BorderRadiusConfig()
    
    def validate(self) -> bool:
        """
        Validate theme configuration parameters.
        
        Returns:
            bool: True if all parameters are within valid ranges
        """
        if not (0 <= self.blur_strength <= 20):
            return False
        if not (0.0 <= self.shadow_intensity <= 1.0):
            return False
        if not (0 <= self.border_radius <= 24):
            return False
        if self.animation_duration <= 0:
            return False
        return True


@dataclass
class ColorPalette:
    """Color palette for glass theme with black and green scheme."""
    base_black: str = "#000000"
    accent_green: str = "#00ff00"
    
    # Text colors
    text_primary: str = "#00ff00"
    text_secondary: str = "rgba(0, 255, 0, 0.7)"
    text_tertiary: str = "rgba(0, 255, 0, 0.5)"
    text_disabled: str = "rgba(0, 255, 0, 0.3)"
    
    # Background colors with opacity levels
    bg_glass_primary: str = "rgba(0, 0, 0, 0.7)"
    bg_glass_secondary: str = "rgba(0, 0, 0, 0.6)"
    bg_glass_tertiary: str = "rgba(0, 0, 0, 0.5)"
    
    # Opacity levels for panels
    opacity_primary: float = 0.7
    opacity_secondary: float = 0.6
    opacity_tertiary: float = 0.5
    
    # Interactive colors with opacity levels
    interactive_default: str = "rgba(0, 255, 0, 0.1)"
    interactive_hover: str = "rgba(0, 255, 0, 0.2)"
    interactive_active: str = "rgba(0, 255, 0, 0.25)"
    interactive_focus: str = "rgba(0, 255, 0, 0.15)"
    
    # Interactive opacity levels
    opacity_interactive_default: float = 0.1
    opacity_interactive_hover: float = 0.2
    opacity_interactive_active: float = 0.25
    opacity_interactive_focus: float = 0.15
    
    # Border colors
    border_default: str = "rgba(0, 255, 0, 0.2)"
    border_hover: str = "rgba(0, 255, 0, 0.5)"
    border_active: str = "rgba(0, 255, 0, 0.6)"
    border_focus: str = "rgba(0, 255, 0, 0.5)"
    
    # Shadow colors
    shadow_green: str = "rgba(0, 255, 0, 0.15)"
    shadow_black: str = "rgba(0, 0, 0, 0.3)"
    shadow_glow: str = "rgba(0, 255, 0, 0.3)"
    
    def get_color(self, color_type: str) -> str:
        """
        Get color value by type.
        
        Args:
            color_type: Type of color to retrieve
            
        Returns:
            str: Color value in CSS format
        """
        color_map = {
            "base_black": self.base_black,
            "accent_green": self.accent_green,
            "text_primary": self.text_primary,
            "text_secondary": self.text_secondary,
            "text_tertiary": self.text_tertiary,
            "bg_glass_primary": self.bg_glass_primary,
            "bg_glass_secondary": self.bg_glass_secondary,
            "border_default": self.border_default,
            "shadow_green": self.shadow_green,
            "shadow_black": self.shadow_black,
        }
        return color_map.get(color_type, self.base_black)


class GlassThemeSystem:
    """
    Manages the application of Apple iOS glass morphism design principles.
    
    This class provides methods for applying glass effects, managing color palettes,
    and generating CSS for glass components.
    """
    
    def __init__(self, config: Optional[ThemeConfig] = None, 
                 color_palette: Optional[ColorPalette] = None):
        """
        Initialize the Glass Theme System.
        
        Args:
            config: Theme configuration (uses defaults if None)
            color_palette: Color palette (uses defaults if None)
        """
        self.config = config or ThemeConfig()
        self.color_palette = color_palette or ColorPalette()
        
        if not self.config.validate():
            raise ValueError("Invalid theme configuration parameters")
    
    def apply_glass_effect(self, component_type: str = "panel") -> Dict[str, str]:
        """
        Apply glass effect to a UI component.
        
        Args:
            component_type: Type of component ("panel", "button", "input", "table", "modal")
            
        Returns:
            Dict[str, str]: CSS properties for glass effect
        """
        # Determine border radius based on component type
        border_radius_map = {
            "button": self.config.border_radius_config.get_radius("small"),
            "input": self.config.border_radius_config.get_radius("small"),
            "panel": self.config.border_radius_config.get_radius("medium"),
            "table": self.config.border_radius_config.get_radius("medium"),
            "modal": self.config.border_radius_config.get_radius("xl"),
        }
        
        border_radius = border_radius_map.get(component_type, self.config.border_radius)
        
        base_styles = {
            "backdrop-filter": f"blur({self.config.blur_strength}px) saturate(180%)",
            "-webkit-backdrop-filter": f"blur({self.config.blur_strength}px) saturate(180%)",
            "border-radius": f"{border_radius}px",
            "transition": f"all {self.config.animation_duration}s cubic-bezier(0.4, 0, 0.2, 1)",
        }
        
        if component_type == "panel":
            base_styles.update({
                "background": self.color_palette.bg_glass_primary,
                "border": f"1px solid {self.color_palette.border_default}",
                "box-shadow": self.generate_shadow((0, 0), (100, 100)),
            })
        elif component_type == "button":
            base_styles.update({
                "background": self.color_palette.interactive_default,
                "border": f"1px solid {self.color_palette.border_default}",
                "box-shadow": self.generate_shadow((0, 0), (50, 40), intensity=0.15),
                "color": self.color_palette.text_primary,
            })
        elif component_type == "input":
            base_styles.update({
                "background": self.color_palette.bg_glass_tertiary,
                "border": f"1px solid {self.color_palette.border_default}",
                "box-shadow": f"inset 0 2px 4px {self.color_palette.shadow_black}",
                "color": self.color_palette.text_primary,
            })
        elif component_type == "table":
            base_styles.update({
                "background": self.color_palette.bg_glass_secondary,
                "border": f"1px solid {self.color_palette.border_default}",
            })
        elif component_type == "modal":
            base_styles.update({
                "background": self.color_palette.bg_glass_primary,
                "border": f"1px solid {self.color_palette.border_default}",
                "box-shadow": self.generate_shadow((0, 0), (200, 200), intensity=0.5),
            })
        
        return base_styles
    
    def update_color_palette(self, new_palette: ColorPalette) -> 'GlassThemeSystem':
        """
        Update the color palette.
        
        Args:
            new_palette: New color palette configuration
            
        Returns:
            GlassThemeSystem: Self for method chaining
        """
        self.color_palette = new_palette
        return self
    
    def calculate_blur_radius(self, screen_density: float = 1.0) -> int:
        """
        Calculate appropriate blur radius based on screen density.
        
        Args:
            screen_density: Screen pixel density (1.0 = standard, 2.0 = retina)
            
        Returns:
            int: Calculated blur radius in pixels
        """
        base_blur = self.config.blur_strength
        adjusted_blur = int(base_blur * screen_density)
        return min(adjusted_blur, 20)  # Cap at 20px
    
    def generate_shadow(self, position: Tuple[int, int], size: Tuple[int, int], 
                       intensity: Optional[float] = None) -> str:
        """
        Generate realistic shadow effects for depth perception.
        
        Args:
            position: (x, y) position offset
            size: (width, height) of the component
            intensity: Shadow intensity (uses config if None)
            
        Returns:
            str: CSS box-shadow value
        """
        shadow_intensity = intensity if intensity is not None else self.config.shadow_intensity
        
        # Multi-layer shadow system
        shadows = [
            f"0 8px 32px 0 rgba(0, 255, 0, {shadow_intensity * 0.33})",
            f"0 2px 8px 0 rgba(0, 0, 0, {shadow_intensity})",
            f"inset 0 1px 0 0 rgba(255, 255, 255, {shadow_intensity * 0.33})",
        ]
        
        return ", ".join(shadows)
    
    def generate_css_variables(self) -> str:
        """
        Generate CSS custom properties for the theme.
        
        Returns:
            str: CSS :root block with custom properties
        """
        css = ":root {\n"
        css += f"  /* Base Colors */\n"
        css += f"  --color-black: {self.color_palette.base_black};\n"
        css += f"  --color-green: {self.color_palette.accent_green};\n\n"
        
        css += f"  /* Text Colors */\n"
        css += f"  --text-primary: {self.color_palette.text_primary};\n"
        css += f"  --text-secondary: {self.color_palette.text_secondary};\n"
        css += f"  --text-tertiary: {self.color_palette.text_tertiary};\n"
        css += f"  --text-disabled: {self.color_palette.text_disabled};\n\n"
        
        css += f"  /* Background Colors */\n"
        css += f"  --bg-glass-primary: {self.color_palette.bg_glass_primary};\n"
        css += f"  --bg-glass-secondary: {self.color_palette.bg_glass_secondary};\n"
        css += f"  --bg-glass-tertiary: {self.color_palette.bg_glass_tertiary};\n\n"
        
        css += f"  /* Opacity Levels - Panels */\n"
        css += f"  --opacity-primary: {self.color_palette.opacity_primary};\n"
        css += f"  --opacity-secondary: {self.color_palette.opacity_secondary};\n"
        css += f"  --opacity-tertiary: {self.color_palette.opacity_tertiary};\n\n"
        
        css += f"  /* Interactive Colors */\n"
        css += f"  --interactive-default: {self.color_palette.interactive_default};\n"
        css += f"  --interactive-hover: {self.color_palette.interactive_hover};\n"
        css += f"  --interactive-active: {self.color_palette.interactive_active};\n"
        css += f"  --interactive-focus: {self.color_palette.interactive_focus};\n\n"
        
        css += f"  /* Opacity Levels - Interactive States */\n"
        css += f"  --opacity-interactive-default: {self.color_palette.opacity_interactive_default};\n"
        css += f"  --opacity-interactive-hover: {self.color_palette.opacity_interactive_hover};\n"
        css += f"  --opacity-interactive-active: {self.color_palette.opacity_interactive_active};\n"
        css += f"  --opacity-interactive-focus: {self.color_palette.opacity_interactive_focus};\n\n"
        
        css += f"  /* Border Colors */\n"
        css += f"  --border-default: {self.color_palette.border_default};\n"
        css += f"  --border-hover: {self.color_palette.border_hover};\n"
        css += f"  --border-active: {self.color_palette.border_active};\n"
        css += f"  --border-focus: {self.color_palette.border_focus};\n\n"
        
        css += f"  /* Shadow Colors */\n"
        css += f"  --shadow-green: {self.color_palette.shadow_green};\n"
        css += f"  --shadow-black: {self.color_palette.shadow_black};\n"
        css += f"  --shadow-glow: {self.color_palette.shadow_glow};\n\n"
        
        css += f"  /* Theme Configuration */\n"
        css += f"  --blur-strength: {self.config.blur_strength}px;\n"
        css += f"  --border-radius: {self.config.border_radius}px;\n"
        css += f"  --animation-duration: {self.config.animation_duration}s;\n\n"
        
        css += f"  /* Border Radius System */\n"
        css += f"  --border-radius-small: {self.config.border_radius_config.small}px;\n"
        css += f"  --border-radius-medium: {self.config.border_radius_config.medium}px;\n"
        css += f"  --border-radius-large: {self.config.border_radius_config.large}px;\n"
        css += f"  --border-radius-xl: {self.config.border_radius_config.xl}px;\n"
        css += "}\n"
        
        return css
    
    def generate_glass_panel_css(self) -> str:
        """
        Generate complete CSS for glass panel component.
        
        Returns:
            str: CSS rules for glass panel
        """
        styles = self.apply_glass_effect("panel")
        
        css = ".glass-panel {\n"
        for prop, value in styles.items():
            css += f"  {prop}: {value};\n"
        css += "}\n\n"
        
        # Add gradient overlay
        css += ".glass-panel::before {\n"
        css += "  content: '';\n"
        css += "  position: absolute;\n"
        css += "  inset: 0;\n"
        css += "  background: linear-gradient(135deg, rgba(0, 255, 0, 0.08) 0%, rgba(0, 255, 0, 0.02) 100%);\n"
        css += "  pointer-events: none;\n"
        css += "  border-radius: inherit;\n"
        css += "}\n"
        
        return css
    
    def generate_glass_button_css(self) -> str:
        """
        Generate complete CSS for glass button component.
        
        Returns:
            str: CSS rules for glass button with states
        """
        default_styles = self.apply_glass_effect("button")
        
        css = ".glass-button {\n"
        for prop, value in default_styles.items():
            css += f"  {prop}: {value};\n"
        css += "  cursor: pointer;\n"
        css += "}\n\n"
        
        # Hover state
        css += ".glass-button:hover {\n"
        css += f"  background: {self.color_palette.interactive_hover};\n"
        css += f"  border-color: {self.color_palette.border_hover};\n"
        css += f"  box-shadow: 0 6px 24px rgba(0, 255, 0, 0.25), 0 0 20px {self.color_palette.shadow_glow};\n"
        css += "  transform: translateY(-2px);\n"
        css += "}\n\n"
        
        # Active state
        css += ".glass-button:active {\n"
        css += f"  background: {self.color_palette.interactive_active};\n"
        css += f"  border-color: {self.color_palette.border_active};\n"
        css += f"  box-shadow: 0 2px 8px rgba(0, 255, 0, 0.2), inset 0 2px 4px {self.color_palette.shadow_black};\n"
        css += "  transform: translateY(0);\n"
        css += "}\n\n"
        
        # Focus state
        css += ".glass-button:focus {\n"
        css += f"  outline: none;\n"
        css += f"  box-shadow: 0 0 0 3px {self.color_palette.interactive_focus}, 0 0 20px rgba(0, 255, 0, 0.2);\n"
        css += "}\n"
        
        return css
    
    def generate_glass_input_css(self) -> str:
        """
        Generate complete CSS for glass input component.
        
        Returns:
            str: CSS rules for glass input with states
        """
        default_styles = self.apply_glass_effect("input")
        
        css = ".glass-input {\n"
        for prop, value in default_styles.items():
            css += f"  {prop}: {value};\n"
        css += "  padding: 0.5rem;\n"
        css += "}\n\n"
        
        # Placeholder
        css += ".glass-input::placeholder {\n"
        css += f"  color: {self.color_palette.text_tertiary};\n"
        css += "}\n\n"
        
        # Focus state
        css += ".glass-input:focus {\n"
        css += f"  background: {self.color_palette.bg_glass_secondary};\n"
        css += f"  border-color: {self.color_palette.border_focus};\n"
        css += f"  box-shadow: inset 0 2px 4px {self.color_palette.shadow_black}, "
        css += f"0 0 0 3px {self.color_palette.interactive_focus}, "
        css += f"0 0 20px rgba(0, 255, 0, 0.2);\n"
        css += "  outline: none;\n"
        css += "}\n"
        
        return css


# Default instance for easy import
default_glass_theme = GlassThemeSystem()
