# GlassThemeSystem Documentation

## Overview

The `GlassThemeSystem` is a Python class that implements Apple iOS glass morphism design principles for PyServeX v3.0.1. It provides a comprehensive system for applying glass effects, managing color palettes, and generating CSS for glass components while maintaining the black and green color scheme.

## Features

- **Glass Morphism Effects**: Apply backdrop blur, shadows, and transparency
- **Configurable Parameters**: Adjust blur strength (0-20), opacity (0.0-1.0), border radius (0-24px)
- **Color Palette Management**: Maintain black and green color scheme with glass adaptations
- **CSS Generation**: Generate complete CSS for glass components
- **Component Support**: Panel, button, input, and table components
- **Screen Density Adaptation**: Calculate appropriate blur radius for different screen densities
- **WCAG 2.1 AA Compliance**: Maintains accessibility standards

## Installation

The GlassThemeSystem is included in the PyServeX package:

```python
from pyservx import GlassThemeSystem, ThemeConfig, ColorPalette
```

## Quick Start

### Basic Usage

```python
from pyservx import GlassThemeSystem

# Create a default glass theme system
theme = GlassThemeSystem()

# Apply glass effect to a panel
panel_styles = theme.apply_glass_effect("panel")

# Generate CSS variables
css_vars = theme.generate_css_variables()

# Generate complete CSS for components
panel_css = theme.generate_glass_panel_css()
button_css = theme.generate_glass_button_css()
input_css = theme.generate_glass_input_css()
```

### Custom Configuration

```python
from pyservx import GlassThemeSystem, ThemeConfig

# Create custom configuration
config = ThemeConfig(
    blur_strength=15,
    shadow_intensity=0.4,
    border_radius=16,
    animation_duration=0.4
)

# Initialize theme with custom config
theme = GlassThemeSystem(config=config)
```

### Custom Color Palette

```python
from pyservx import GlassThemeSystem, ColorPalette

# Create custom color palette
palette = ColorPalette(
    accent_green="#00cc00",
    text_primary="#00cc00"
)

# Initialize theme with custom palette
theme = GlassThemeSystem(color_palette=palette)

# Or update existing theme
theme.update_color_palette(palette)
```

## API Reference

### ThemeConfig

Configuration dataclass for glass theme effects.

**Parameters:**
- `glass_effect_enabled` (bool): Enable/disable glass effects (default: True)
- `blur_strength` (int): Blur intensity in pixels, range 0-20 (default: 12)
- `shadow_intensity` (float): Shadow opacity, range 0.0-1.0 (default: 0.3)
- `border_radius` (int): Corner rounding in pixels, range 0-24 (default: 12)
- `animation_duration` (float): Transition duration in seconds (default: 0.3)

**Methods:**
- `validate() -> bool`: Validate configuration parameters

### ColorPalette

Color palette dataclass for glass theme with black and green scheme.

**Attributes:**
- `base_black` (str): Base black color (default: "#000000")
- `accent_green` (str): Accent green color (default: "#00ff00")
- `text_primary` (str): Primary text color
- `text_secondary` (str): Secondary text color
- `text_tertiary` (str): Tertiary text color
- `bg_glass_primary` (str): Primary glass background
- `bg_glass_secondary` (str): Secondary glass background
- `interactive_default` (str): Default interactive state color
- `interactive_hover` (str): Hover state color
- `border_default` (str): Default border color
- `shadow_green` (str): Green shadow color
- `shadow_black` (str): Black shadow color

**Methods:**
- `get_color(color_type: str) -> str`: Get color value by type

### GlassThemeSystem

Main class for managing glass theme application.

**Constructor:**
```python
GlassThemeSystem(
    config: Optional[ThemeConfig] = None,
    color_palette: Optional[ColorPalette] = None
)
```

**Methods:**

#### `apply_glass_effect(component_type: str = "panel") -> Dict[str, str]`

Apply glass effect to a UI component.

**Parameters:**
- `component_type` (str): Type of component ("panel", "button", "input", "table")

**Returns:**
- `Dict[str, str]`: CSS properties for glass effect

**Example:**
```python
styles = theme.apply_glass_effect("button")
# Returns: {
#     "backdrop-filter": "blur(12px) saturate(180%)",
#     "border-radius": "12px",
#     "background": "rgba(0, 255, 0, 0.1)",
#     ...
# }
```

#### `update_color_palette(new_palette: ColorPalette) -> GlassThemeSystem`

Update the color palette.

**Parameters:**
- `new_palette` (ColorPalette): New color palette configuration

**Returns:**
- `GlassThemeSystem`: Self for method chaining

#### `calculate_blur_radius(screen_density: float = 1.0) -> int`

Calculate appropriate blur radius based on screen density.

**Parameters:**
- `screen_density` (float): Screen pixel density (1.0 = standard, 2.0 = retina)

**Returns:**
- `int`: Calculated blur radius in pixels (capped at 20px)

**Example:**
```python
standard_blur = theme.calculate_blur_radius(1.0)  # 12px
retina_blur = theme.calculate_blur_radius(2.0)    # 20px (capped)
```

#### `generate_shadow(position: Tuple[int, int], size: Tuple[int, int], intensity: Optional[float] = None) -> str`

Generate realistic shadow effects for depth perception.

**Parameters:**
- `position` (Tuple[int, int]): (x, y) position offset
- `size` (Tuple[int, int]): (width, height) of the component
- `intensity` (Optional[float]): Shadow intensity (uses config if None)

**Returns:**
- `str`: CSS box-shadow value

**Example:**
```python
shadow = theme.generate_shadow((0, 0), (100, 100))
# Returns: "0 8px 32px 0 rgba(0, 255, 0, 0.099), ..."
```

#### `generate_css_variables() -> str`

Generate CSS custom properties for the theme.

**Returns:**
- `str`: CSS :root block with custom properties

#### `generate_glass_panel_css() -> str`

Generate complete CSS for glass panel component.

**Returns:**
- `str`: CSS rules for glass panel

#### `generate_glass_button_css() -> str`

Generate complete CSS for glass button component with states.

**Returns:**
- `str`: CSS rules for glass button (default, hover, active, focus)

#### `generate_glass_input_css() -> str`

Generate complete CSS for glass input component with states.

**Returns:**
- `str`: CSS rules for glass input (default, placeholder, focus)

## Component Types

### Panel Component

Large container elements with strong glass effect.

**CSS Classes:** `.glass-panel`

**Features:**
- 70% opacity background
- 20px backdrop blur
- Multi-layer shadows
- Gradient overlay

### Button Component

Interactive button elements with hover/active states.

**CSS Classes:** `.glass-button`, `.glass-button:hover`, `.glass-button:active`, `.glass-button:focus`

**Features:**
- 10% green tint background
- Smooth transitions
- Hover elevation effect
- Focus ring indicator

### Input Component

Form input elements with focus states.

**CSS Classes:** `.glass-input`, `.glass-input:focus`, `.glass-input::placeholder`

**Features:**
- 50% opacity background
- Inset shadow
- Focus glow effect
- Placeholder styling

### Table Component

Data table elements with row hover effects.

**CSS Classes:** `.glass-table`, `.glass-table thead`, `.glass-table tbody tr:hover`

**Features:**
- 60% opacity background
- Header styling
- Row hover effects
- Border styling

## Examples

### Example 1: Basic Panel

```python
from pyservx import GlassThemeSystem

theme = GlassThemeSystem()
panel_css = theme.generate_glass_panel_css()

# Use in HTML:
# <div class="glass-panel">Content here</div>
```

### Example 2: Custom Button

```python
from pyservx import GlassThemeSystem, ThemeConfig

config = ThemeConfig(
    blur_strength=15,
    border_radius=16
)
theme = GlassThemeSystem(config=config)
button_css = theme.generate_glass_button_css()

# Use in HTML:
# <button class="glass-button">Click Me</button>
```

### Example 3: Complete Theme

```python
from pyservx import GlassThemeSystem

theme = GlassThemeSystem()

# Generate complete CSS file
css = theme.generate_css_variables()
css += theme.generate_glass_panel_css()
css += theme.generate_glass_button_css()
css += theme.generate_glass_input_css()

# Save to file
with open("glass_theme.css", "w") as f:
    f.write(css)
```

### Example 4: Screen Density Adaptation

```python
from pyservx import GlassThemeSystem

theme = GlassThemeSystem()

# Calculate blur for different screens
standard = theme.calculate_blur_radius(1.0)  # 12px
retina = theme.calculate_blur_radius(2.0)    # 20px
high_dpi = theme.calculate_blur_radius(3.0)  # 20px (capped)
```

## Browser Compatibility

The GlassThemeSystem generates CSS with fallbacks for browsers that don't support `backdrop-filter`:

```css
@supports not (backdrop-filter: blur(20px)) {
  .glass-panel {
    background: rgba(0, 0, 0, 0.85);
  }
}
```

**Supported Browsers:**
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+
- Mobile Safari 13+

## Accessibility

The GlassThemeSystem maintains WCAG 2.1 AA compliance:

- **Primary Text**: 15.3:1 contrast ratio (AAA)
- **Secondary Text**: 10.7:1 contrast ratio (AAA)
- **Tertiary Text**: 7.65:1 contrast ratio (AA)
- **Interactive Elements**: 4.8:1 contrast ratio (AA)

High contrast mode is automatically supported:

```css
@media (prefers-contrast: high) {
  :root {
    --bg-glass-primary: rgba(0, 0, 0, 0.95);
    --border-default: rgba(0, 255, 0, 0.5);
  }
}
```

## Performance Considerations

The GlassThemeSystem includes performance optimizations:

1. **Hardware Acceleration**: Uses `transform: translateZ(0)` for GPU acceleration
2. **Blur Capping**: Maximum blur radius of 20px to prevent performance issues
3. **Responsive Optimization**: Reduced blur on mobile devices
4. **Will-change Property**: Applied to animated properties

## Testing

Run the test suite:

```bash
python -m pytest tests/test_glass_theme_system.py -v
```

Run the demo:

```bash
python -m examples.glass_theme_demo
```

## Validation

The `ThemeConfig.validate()` method ensures all parameters are within valid ranges:

- `blur_strength`: 0-20 pixels
- `shadow_intensity`: 0.0-1.0
- `border_radius`: 0-24 pixels
- `animation_duration`: > 0 seconds

Invalid configurations will raise a `ValueError` during initialization.

## Best Practices

1. **Use Default Configuration**: Start with defaults and adjust as needed
2. **Test Across Browsers**: Verify glass effects work in target browsers
3. **Consider Performance**: Limit blur intensity on mobile devices
4. **Maintain Contrast**: Ensure text remains readable with glass effects
5. **Use CSS Variables**: Leverage generated CSS variables for consistency

## Troubleshooting

### Glass effects not visible

- Check browser support for `backdrop-filter`
- Verify CSS is properly loaded
- Ensure elements have content behind them for blur effect

### Performance issues

- Reduce `blur_strength` value
- Limit number of glass elements on page
- Use mobile-optimized blur on smaller screens

### Contrast issues

- Increase background opacity
- Use higher contrast text colors
- Test with accessibility tools

## License

Part of PyServeX v3.0.1 - See main project license.

## Contributing

Contributions are welcome! Please follow the project's contribution guidelines.

## Support

For issues and questions, please use the project's issue tracker.
