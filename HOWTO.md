# Page Table Walker User Guide (HOWTO)

This guide explains how to use the Page Table Walker (ptw-walker) for simulation and visualization of ARM v9 2-stage translations.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running Simulations (`ptw-sim`)](#running-simulations)
3. [Interactive Visualization (`ptw-viz`)](#interactive-visualization)
4. [Creating Scenarios](#creating-scenarios)
5. [Input Format Reference](#input-format-reference)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Python 3.11 or later
- [uv](https://github.com/astral-sh/uv) (recommended)

### Installation
```bash
git clone <repository-url>
cd ptw
uv sync
```

### Your First Run
```bash
# 1. Simulate: generates results/scenario_simple_success_trace.json
ptw-sim examples/scenario_simple_success.json

# 2. Visualize: renders to terminal
ptw-viz results/scenario_simple_success_trace.json

# 3. HTML: opens in browser
ptw-viz results/scenario_simple_success_trace.json --format html
open results/scenario_simple_success_visualization.html
```

---

## Running Simulations

The `ptw-sim` package provides the `ptw-sim` tool.

### Usage
```bash
ptw-sim <scenario.json> [options]
```

### Key Options
| Option | Description |
|--------|-------------|
| `-f, --format` | `summary` (terminal), `json` (trace file), or `both` (default) |
| `-o, --output` | Output directory (default: `results/`) |
| `-q, --quiet`  | Suppress summary output |

---

## Interactive Visualization

The `ptw-viz` package provides the `ptw-viz` tool.

### Modes
- **Terminal**: Default view with color-coded tables.
- **Tree View**: Use `--tree` to see the hierarchical walk (especially useful for Stage 2 lookups).
- **HTML**: Use `--format html` for a standalone static report.
- **Interactive**: Use `--interactive` to generate a data JSON + Template for the advanced animated visualizer.

### Features
- **Timeline View**: Step-by-step animation of the walk.
- **Recursive Table View**: Shows Stage 2 translations nested within Stage 1 lookups.
- **Binary Register View**: Full bit-level breakdown of control registers.

---

## Creating Scenarios

Scenarios are defined in JSON format. A typical scenario includes architecture settings, register values, memory contents, and the target address.

### Basic Structure
```json
{
    "scenario_name": "my_test",
    "architecture": {
        "granule_size_kb": 4,
        "va_bits": 48
    },
    "registers": {
        "TTBR0_EL1": "0x1000",
        "TCR_EL1": { "T0SZ": 16 }
    },
    "memory_access": {
        "virtual_address": "0x12345678",
        "access_type": "READ"
    },
    "translation_tables": {
        "stage1": {
            "0x1000": {"value": "0x2003", "comment": "L0 -> L1"}
        }
    }
}
```

---

## Input Format Reference

### Architecture
- `granule_size_kb`: 4, 16, or 64.
- `va_bits`: Total virtual address bits (e.g., 48).
- `pa_bits`: Total physical address bits (e.g., 52).

### Descriptor Encoding
- `0x...3`: Table descriptor (points to next level).
- `0x...3`: Page descriptor (at L3).
- `0x...1`: Block descriptor (at L1 or L2).
- `0x...0`: Invalid descriptor (causes fault).

---

## Troubleshooting

### "Translation fault at Stage 2 Level 1"
Ensure your Stage 2 tables (`VTTBR_EL2`) contain entries for the IPAs used by Stage 1 tables. Every memory access in a 2-stage walk must be translated.

### "Incompatible trace version"
The visualizer requires traces produced by a compatible version of the simulator. Ensure both packages are up to date.

---

## Getting Help
- Explore `examples/` for complex scenarios (Stage 2, Faults, Block Mappings).
- See `ptw-sim/README.md` for engine details.
- See `ptw-viz/README.md` for visualization flags.
