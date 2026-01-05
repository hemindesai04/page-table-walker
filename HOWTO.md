# Page Table Walker User Guide (HOWTO)
 
This guide explains how to use the Page Table Walker (formerly ptw-viz) for simulation and visualization.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running Simulations](#running-simulations)
3. [Creating Scenarios](#creating-scenarios)
4. [Understanding Output](#understanding-output)
5. [Input Format Reference](#input-format-reference)
6. [Common Use Cases](#common-use-cases)

---

## Quick Start

### Prerequisites

- Python 3.11 or later
- UV package manager (`/opt/homebrew/bin/uv`)

### Installation

```bash
cd /path/to/ptw-viz
/opt/homebrew/bin/uv sync
```

### Run Your First Simulation

```bash
# Terminal visualization
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json

# HTML visualization (opens in browser)
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json --format html --output results/
open results/scenario_simple_success.html
```

---

## Running Simulations

### Command Line Usage

```bash
ptw-viz <scenario.json> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `-f, --format` | Output format: `terminal`, `html`, `both`, `json`, `interactive` |
| `-o, --output` | Output directory for results (default: `results/`) |
| `-q, --quiet` | Suppress terminal output |
| `--tree` | Show tree view instead of table (terminal only) |

### Examples

```bash
# Terminal output (default)
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json

# HTML output
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json -f html -o results/

# Both terminal and HTML
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json -f both -o results/

# JSON output (for programmatic use)
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json -f json -o results/

# Interactive animated visualization
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json -f interactive -o results/

# Tree view (shows hierarchical walk structure)
/opt/homebrew/bin/uv run python -m ptw_viz examples/scenario_simple_success.json --tree
```

### Interactive Visualization

The `-f interactive` option generates:
1. A **reusable template** (`ptw_visualizer.html`) - open this *once*.
2. A **JSON data file** (`*_data.json`) containing the simulation results.

### Features
- **Dynamic File Loading**: Switch between different scenarios instantly using the **"📂 Load Another File"** button without reloading the page.
- **Dual Visualization Modes**:
    - **Timeline View**: Step-by-step animation with detailed context panels and flow diagrams.
    - **Recursive Table View**: Hierarchical table explicitly showing how Stage 2 translations enabling Stage 1 levels (e.g., "S2 for S1 L0").
- **Deep Inspection**:
    - **Binary Register View**: Full 64-bit binary breakdown of registers like `TTBRn_EL1` to debug bit fields.
    - **Calculated Fields**: Tables populate derived values like Index and Table Base Addresses automatically.
    - **Address Logic**: Formulas showing exactly how the Physical Address is calculated at each step.
- **Playback Controls**: Play, Pause, Step Next/Prev, and adjustable Speed.

### How to use
1. Run `ptw-viz <scenario.json> -f interactive` to generate the data.
2. Open `results/ptw_visualizer.html` in your browser.
3. Click **"Choose JSON File"** to load the generated `*_data.json`.
4. To view a different scenario:
    - Run the simulator for the new scenario: `ptw-viz another.json -f interactive`
    - In the open browser tab, click **"📂 Load Another File"** and select the new JSON file.
5. Toggle between **Timeline** and **Table** modes using the buttons in the control bar.

---

## Creating Scenarios

### Basic Structure

Create a JSON file with this structure:

```json
{
    "scenario_name": "my_scenario",
    "description": "Description of what this scenario tests",
    
    "architecture": {
        "granule_size_kb": 4,
        "va_bits": 48,
        "pa_bits": 56,
        "ipa_bits": 48
    },
    
    "registers": {
        "TTBR0_EL1": "0x0000000000001000",
        "VTTBR_EL2": "0x0000000000002000",
        "TCR_EL1": { "T0SZ": 16 },
        "VTCR_EL2": { "T0SZ": 16, "SL0": 0 }
    },
    
    "memory_access": {
        "virtual_address": "0x0000000012345678",
        "access_type": "READ",
        "privilege_level": "EL0"
    },
    
    "translation_tables": {
        "stage1": { ... },
        "stage2": { ... }
    }
}
```

### Defining Translation Tables

Translation tables map physical addresses to descriptor values:

```json
"translation_tables": {
    "stage1": {
        "0x11000": {"value": "0x0000000000003003", "comment": "L0 -> L1 table"},
        "0x13000": {"value": "0x0000000000004003", "comment": "L1 -> L2 table"},
        "0x14000": {"value": "0x0000000000005003", "comment": "L2 -> L3 table"},
        "0x15000": {"value": "0x0000000000100443", "comment": "L3 -> Page"}
    },
    "stage2": {
        "0x2000": {"value": "0x0000000000010003", "comment": "S2 L0 table"},
        ...
    }
}
```

### Descriptor Value Encoding

For **Table Descriptors** (bits[1:0] = 0b11):
```
bits[47:12] = Next table address
bits[1:0]   = 0b11
```

For **Page Descriptors** (bits[1:0] = 0b11 at L3):
```
bits[47:12] = Output page address
bits[10]    = AF (Access Flag, set to 1)
bits[7:6]   = AP (Access Permissions)
bits[1:0]   = 0b11
```

For **Block Descriptors** (bits[1:0] = 0b01 at L1/L2):
```
bits[47:30] = Output address (L1 1GB block)
bits[47:21] = Output address (L2 2MB block)
bits[10]    = AF (Access Flag, set to 1)
bits[7:6]   = AP (Access Permissions)
bits[1:0]   = 0b01
```

Common descriptor values:
- `0x...003` = Table descriptor (valid, points to next table)
- `0x...443` = Page descriptor (valid, AF=1, AP=01 RW for both EL0/EL1)
- `0x...441` = Block descriptor (valid, AF=1, AP=01 RW)
- `0x...4C3` = Page descriptor (valid, AF=1, AP=11 RO for both)
- `0x...000` = Invalid descriptor (causes translation fault)

---

## Understanding Output

### Terminal Output

```
╔═══════════════════════════════════════════════════════╗
║ ARM v9 Page Table Walk Visualization                  ║
║ Scenario: scenario_simple_success                     ║
╚═══════════════════════════════════════════════════════╝

                Address Breakdown                 
╭─────────────────┬────────────────────┬─────────╮
│ Component       │ Value              │ Bits    │
├─────────────────┼────────────────────┼─────────┤
│ Virtual Address │ 0x0000000000000ABC │ [47:0]  │
│   L0 Index      │ 0x000              │ [47:39] │
│   L1 Index      │ 0x000              │ [38:30] │
│   L2 Index      │ 0x000              │ [29:21] │
│   L3 Index      │ 0x000              │ [20:12] │
│   Page Offset   │ 0xABC              │ [11:0]  │
│ Intermediate PA │ 0x0000000000100ABC │ S1 out  │
│ Physical Address│ 0x0000000000200ABC │ Final   │
╰─────────────────┴────────────────────┴─────────╯
```

- **L0-L3 Index**: Extracted from VA bits, used to index into tables
- **Page Offset**: Preserved through translation (not translated)
- **IPA**: Output of Stage 1 translation
- **PA**: Final physical address

### Walk Events

Each event represents a memory read during translation:

| Column | Description |
|--------|-------------|
| # | Sequential event number |
| Type | T = Translation read |
| Stage | S1 = Stage 1, S2 = Stage 2 |
| Level | L0, L1, L2, L3 |
| Purpose | Why this read is being done |
| Result | TABLE, PAGE, or INVALID |
| Output | Next address or final address |

### Fault Output

When a fault occurs:
```
╭─────────────────── Fault Details ────────────────────╮
│ Fault Type: TRANSLATION_FAULT                        │
│ Stage: 1  Level: 2                                   │
│ Address: 0x0000000012345678                          │
│ Message: Invalid descriptor at Stage 1 Level 2       │
│ FAR_EL1: 0x0000000012345678                          │
╰──────────────────────────────────────────────────────╯
```

---

## Input Format Reference

### Architecture Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `granule_size_kb` | int | 4 | Page size: 4, 16, or 64 KB (affects bit slicing) |
| `va_bits` | int | 48 | Virtual address bits |
| `pa_bits` | int | 56 | Physical address bits |
| `ipa_bits` | int | 48 | IPA bits |

**Granule Size Effects**:
- **4KB**: 9-bit indices, 512 entries/table, L1=1GB blocks, L2=2MB blocks
- **16KB**: 11-bit indices, 2048 entries/table, L2=32MB blocks
- **64KB**: 13-bit indices, 8192 entries/table, starts at L1, L2=512MB blocks

### Registers Section

| Register | Description |
|----------|-------------|
| `TTBR0_EL1` | Stage 1 table base for lower VA range (hex string) |
| `TTBR1_EL1` | Stage 1 table base for upper VA range (hex string) |
| `VTTBR_EL2` | Stage 2 table base (hex string) |
| `TCR_EL1.T0SZ` | Size offset (VA bits = 64 - T0SZ) |
| `VTCR_EL2.SL0` | Stage 2 starting level (0, 1, or 2) |

### Memory Access Section

| Field | Values | Description |
|-------|--------|-------------|
| `virtual_address` | hex string | Address to translate |
| `access_type` | READ, WRITE, EXECUTE | Type of access |
| `privilege_level` | EL0, EL1 | Exception level |

---

## Common Use Cases

### Testing Successful Translation

Use `scenario_simple_success.json` as a template. Ensure all descriptor chains are valid.

### Simulating Translation Fault

Set a descriptor to `0x0000000000000000` (invalid):
```json
"0x14000": {"value": "0x0000000000000000", "comment": "INVALID - causes fault"}
```

### Simulating Permission Fault

Use AP=0b11 (read-only) and attempt WRITE access:
```json
"memory_access": {
    "virtual_address": "0x...",
    "access_type": "WRITE",
    "privilege_level": "EL0"
}
```
With page descriptor having AP=11:
```json
"0x15000": {"value": "0x00000000001004C3", "comment": "Page, AP=11 (RO)"}
```

### Using Block Mappings

Block descriptors can reduce the number of memory accesses by terminating the walk early. See `scenario_e_block_mapping.json` for a complete example.

For a 2MB block at L2:
1. Use level 2 for the descriptor location.
2. Set bits[1:0] = `0b01`.
3. The output address bits [20:0] will be taken directly from the VA.

### Calculating Descriptor Addresses

For VA `0x0000000012345678` with 4KB granule:
```
L0 index = (0x12345678 >> 39) & 0x1FF = 0x000
L1 index = (0x12345678 >> 30) & 0x1FF = 0x000
L2 index = (0x12345678 >> 21) & 0x1FF = 0x091
L3 index = (0x12345678 >> 12) & 0x1FF = 0x145
```

Descriptor address = table_base + (index × 8)

---

## Troubleshooting

### "Translation fault at Stage 2 Level 1"

The Stage 2 tables don't have entries for the IPA you're trying to translate. Ensure your S2 tables have valid entries for:
- The TTBR0_EL1 base address range
- All S1 table addresses
- The final IPA output address

### No output generated

Check that your scenario JSON is valid:
```bash
/opt/homebrew/bin/uv run python -c "import json; json.load(open('my_scenario.json'))"
```

### "Configuration error"

Verify all required fields are present and have valid values. See the Input Format Reference section.

---

## Getting Help

- Check the example scenarios in `examples/` directory
- Read the developer documentation in `README.md`
- Examine the source code comments in `src/ptw_viz/`
