# QR Code Size Optimization Design

## Overview

This design optimizes the QR code display size in PyServeX by reducing the `box_size` parameter from 10 to 2-3 pixels, achieving approximately 25% of the current display size. The optimization maintains scanning reliability while significantly reducing terminal screen space usage.

## Architecture

The QR code generation occurs in the `run()` function within `pyservx/server.py`. The current implementation uses the `qrcode` library with these parameters:
- `version=1` (automatic sizing)
- `error_correction=ERROR_CORRECT_L` (lowest error correction for smaller size)
- `box_size=10` (current size - target for reduction)
- `border=4` (border width)

### Current Flow
1. Server startup triggers IP address detection
2. For each IP address, a QR code is generated with current parameters
3. QR code is printed to terminal via `qr.print_tty()`

## Components and Interfaces

### Modified Components

#### QRCode Configuration
- **Location**: `pyservx/server.py`, lines 117-123
- **Change**: Reduce `box_size` from 10 to 2 or 3
- **Rationale**: 25% size reduction (10 → 2.5, rounded to 2 or 3 for integer value)

#### Border Optimization (Optional)
- **Location**: Same configuration block
- **Change**: Consider reducing `border` from 4 to 2-3
- **Rationale**: Proportional border reduction maintains visual balance

### Unchanged Components
- IP address detection logic
- QR code data encoding (URL format)
- Error handling for TTY detection
- Command-line argument processing (`--no-qr` flag)

## Data Models

### QR Code Parameters
```python
# Current configuration
qr = qrcode.QRCode(
    version=1,                                    # Keep unchanged
    error_correction=qrcode.constants.ERROR_CORRECT_L,  # Keep unchanged
    box_size=10,                                 # Change to 2 or 3
    border=4,                                    # Optionally reduce to 2-3
)
```

### Size Calculation
- Current approximate size: 10px per module × ~21 modules = ~210px width
- Target size: 2-3px per module × ~21 modules = ~42-63px width
- Reduction ratio: 2px = 20% (better than target), 3px = 30% (close to target)

## Error Handling

### Existing Error Handling (Preserved)
- TTY detection with OSError catch for non-terminal environments
- Graceful fallback when QR code printing fails
- Network interface detection error handling

### New Considerations
- No additional error handling required
- QR code library handles invalid parameter values internally
- Scanning reliability maintained with ERROR_CORRECT_L

## Testing Strategy

### Manual Testing
1. **Visual Verification**: Compare QR code sizes before and after optimization
2. **Scanning Tests**: Verify QR codes remain scannable with mobile devices
3. **Terminal Compatibility**: Test across different terminal applications and sizes
4. **Network Access**: Confirm scanned URLs provide correct server access

### Functional Testing
1. **Parameter Validation**: Ensure box_size values 2-3 work correctly
2. **Cross-platform Testing**: Verify behavior on Windows, macOS, Linux terminals
3. **Mobile Device Testing**: Test scanning with various smartphone cameras
4. **Edge Cases**: Test with different network configurations and IP addresses

### Regression Testing
1. **Existing Functionality**: Verify all current features remain operational
2. **Command-line Options**: Ensure `--no-qr` flag continues working
3. **Error Scenarios**: Confirm error handling remains intact
4. **Multi-IP Scenarios**: Test QR generation for multiple network interfaces

## Implementation Approach

### Phase 1: Core Optimization
- Modify `box_size` parameter from 10 to 3 (30% of original, close to 25% target)
- Test basic functionality and scanning reliability

### Phase 2: Fine-tuning (Optional)
- Experiment with `box_size=2` if scanning remains reliable
- Adjust `border` parameter if needed for visual balance
- Optimize for specific terminal environments if required

### Phase 3: Validation
- Comprehensive testing across devices and platforms
- Performance verification (minimal impact expected)
- Documentation updates if needed

## Design Decisions

### Box Size Selection
- **Decision**: Use `box_size=3` initially, with option to reduce to 2
- **Rationale**: Balances size reduction with scanning reliability
- **Alternative**: Could use 2 for maximum reduction, but may impact scanning

### Border Preservation
- **Decision**: Keep `border=4` initially
- **Rationale**: Maintains scanning reliability and visual clarity
- **Future**: Could reduce to 2-3 if testing shows no scanning issues

### Error Correction Level
- **Decision**: Maintain `ERROR_CORRECT_L`
- **Rationale**: Already optimized for smallest size, changing would increase QR code complexity