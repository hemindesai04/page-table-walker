# ptw-sim User Guide

This guide focuses on the simulation aspects of the Page Table Walker, specifically how to create scenarios and understand the simulation engine's behavior.

## Creating Scenarios

Scenarios are JSON files that describe the state of the system before a translation begins.

### 1. Architecture Configuration
Define the core parameters of the translation system.
```json
"architecture": {
    "va_bits": 48,
    "pa_bits": 52,
    "ipa_bits": 48
}
```
*(Note: The global `granule_size_kb` in `architecture` is supported for legacy but it's recommended to configure `TG0` and `TG1` in the system registers directly for dynamic multi-granule support.)*

### 2. Register State
Configure the control registers that govern the translation process.
- **TTBR0_EL1/TTBR1_EL1**: Base addresses for Stage 1 tables.
- **VTTBR_EL2**: Base address for Stage 2 tables.
- **TCR_EL1**: Translation Control Register (`T0SZ`, `T1SZ`, `TG0`, `TG1`).
- **VTCR_EL2**: Virtualization Translation Control Register (`T0SZ`, `SL0`, `TG0`).

**Dynamic Granule Sizes**
You can configure independent granule sizes (4, 16, or 64 KB) for Stage 1 (via `TCR_EL1.TG0` or `TG1` depending on the VA) and Stage 2 (via `VTCR_EL2.TG0`). 
The simulator natively supports mixing sizes, meaning Stage 1 might operate out of 16KB translations while Stage 2 transparently applies 64KB mappings. Translating Page Offsets and index calculations correctly scale matching the stage's corresponding granule config mapping.

### 3. Translation Tables
Define the contents of memory at specific physical addresses.
```json
"translation_tables": {
    "stage1": {
        "0x1000": { "value": "0x0000000000002003", "comment": "L0 points to L1 at 0x2000" }
    },
    "stage2": {
        "0x5000": { "value": "0x0000000000006003", "comment": "S2 translation for S1 table access" }
    }
}
```

## Understanding Simulation Output

### Terminal Summary
When running `ptw-sim`, the terminal output shows:
1. **Address Breakdown**: How the VA is sliced into indices (L0, L1, etc.).
2. **Walk Steps**: Each memory access, its type (S1 or S2), and the descriptor found.
3. **Final Result**: Success (with PA) or Failure (with Fault details).

### JSON Trace
The JSON trace is designed for machine consumption (the visualizer). It preserves every bit of information extracted during the walk, including intermediate physical addresses (IPAs) and the context of Stage 2 lookups triggered by Stage 1 table fetches.

## Examples
- `examples/scenario_simple_success.json`: Basic 1-stage success.
- `examples/scenario_s2_success.json`: Full 2-stage walk.
- `examples/scenario_fault.json`: Demonstrates a Translation Fault at Level 2.

## Troubleshooting
- **Missing Tables**: If the simulator hits an address not defined in `translation_tables`, it assumes it's unmapped and can cause a fault depending on the context.
- **Alignment**: Ensure table base addresses are aligned to their size as per ARM specifications.
