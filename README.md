# Page Table Walker
 
Page Table Walker with simulation and visualization of each and every step of a 2-stage page table walk in ARM v9 architecture with FEAT_D128 extension support.

***DISCLAIMER:*** *This tool was "vibe-coded" into existence. While the development process was 90% vibes, the logic is 100% pedantic, providing a granular, step-by-step breakdown of ARM v9 translation that even a hardware manual would find "TMI".*

## Overview

This tool simulates the complete address translation process in ARM v9 virtualized systems:

```
Virtual Address (VA) → [Stage 1] → Intermediate PA (IPA) → [Stage 2] → Physical Address (PA)
```

### Key Features

- **Full 2-Stage Translation**: Simulates the complete VA → IPA → PA translation
- **Recursive Walk Support**: Correctly handles Stage 2 translations for Stage 1 table addresses
- **24 Memory Accesses**: Models the maximum worst-case scenario with no TLB hits
- **Fault Simulation**: Translation faults, permission faults, address size faults
- **Enhanced Visualization**:
  - **Timeline View**: Step-by-step animation of the walk
  - **Recursive Table View**: Hierarchical display of nested translation sequences
  - **Terminal Output**: Rich-based detailed text output
- **Interactive Workflow**: Load different JSON scenarios dynamically into a single reusable HTML viewer
- **Event Tracking**: Complete trace of all translation table reads

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         ptw_viz                                │
├────────────────────────────────────────────────────────────────┤
│  main.py            CLI entry point                            │
├────────────────────────────────────────────────────────────────┤
│  models/                                                       │
│  ├── address.py     VA, IPA, PA address models with slicing    │
│  ├── descriptor.py  Table/Page descriptors, AP bits parsing    │
│  └── registers.py   TTBR, TCR, VTCR register models            │
├────────────────────────────────────────────────────────────────┤
│  simulator/                                                    │
│  ├── walker.py      PageTableWalker facade (main orchestrator) │
│  ├── stage1.py      Stage 1 walker (VA → IPA)                  │
│  ├── stage2.py      Stage 2 walker (IPA → PA)                  │
│  └── faults.py      Fault types and permission checking        │
├────────────────────────────────────────────────────────────────┤
│  io/                                                           │
│  ├── parser.py      JSON input parsing with validation         │
│  └── formatter.py   JSON output formatting                     │
├────────────────────────────────────────────────────────────────┤
│  visualizer/                                                   │
│  ├── base.py        Abstract visualizer interface              │
│  ├── terminal.py    Rich-based terminal visualization          │
│  └── html.py        Jinja2-based HTML visualization            │
└────────────────────────────────────────────────────────────────┘
```

## Design Patterns

| Pattern | Application |
|---------|-------------|
| **Facade** | `PageTableWalker` provides simple interface to complex walk logic |
| **Strategy** | `BaseVisualizer` with `TerminalVisualizer`/`HTMLVisualizer` implementations |
| **Factory** | `create_descriptor()` creates appropriate descriptor type from raw value |
| **Builder** | `WalkEvent` construction during walk execution |

## Installation (Development)

```bash
# Clone repository
cd ptw-viz

# Install with UV
/opt/homebrew/bin/uv sync

# Install development dependencies
/opt/homebrew/bin/uv sync --extra dev
```

## Project Structure

```
ptw-viz/
├── pyproject.toml           # UV/pip project configuration
├── README.md                 # This file (developer docs)
├── HOWTO.md                  # User guide
├── src/
│   └── ptw_viz/
│       ├── __init__.py
│       ├── __main__.py       # Module entry point
│       ├── main.py           # CLI implementation
│       ├── models/           # Data models
│       ├── simulator/        # Core simulation
│       ├── io/               # Input/output handling
│       └── visualizer/       # Visualization components
├── examples/                 # Example scenario files
│   ├── scenario_simple_success.json
│   ├── scenario_a_success.json
│   ├── scenario_b_translation_fault.json
│   ├── scenario_c_permission_fault.json
│   ├── scenario_d_s2_fault.json
│   └── scenario_e_block_mapping.json
├── results/                  # Output directory
└── tests/                    # Unit tests
```

## Key Concepts

### Address Slicing by Granule Size

The simulator supports 4KB, 16KB, and 64KB granules:

**4KB Granule (default)**:
```
[47:39] L0 (9 bits) → [38:30] L1 (9 bits) → [29:21] L2 (9 bits) → [20:12] L3 (9 bits) → [11:0] 12-bit offset
```

**16KB Granule**:
```
[47] L0 (1 bit) → [46:36] L1 (11 bits) → [35:25] L2 (11 bits) → [24:14] L3 (11 bits) → [13:0] 14-bit offset
```

**64KB Granule** (starts at L1):
```
[47:42] L1 (6 bits) → [41:29] L2 (13 bits) → [28:16] L3 (13 bits) → [15:0] 16-bit offset
```

### 2-Stage Walk Memory Accesses

```
Maximum 24 memory accesses (no TLB hits):

Stage 1 Walk (VA → IPA):
  - 4 S1 table reads (L0, L1, L2, L3)
  - Each S1 table is at an IPA, requiring S2 translation
  - 4 S1 reads × 4 S2 reads each = 16 S2 reads for tables
  - Total: 4 S1 + 16 S2 = 20 reads

Final IPA → PA translation:
  - 4 more S2 reads to translate the final IPA

Grand Total: 20 + 4 = 24 memory accesses
```

### Descriptor Types

| Type | bits[1:0] | Levels | Description |
|------|-----------|--------|-------------|
| Invalid | `0b*0` | Any | Causes Translation Fault |
| Table | `0b11` | L0-L2 | Points to next-level table |
| Block | `0b01` | L1-L2 | Maps 1GB (L1) or 2MB (L2) block |
| Page | `0b11` | L3 | Maps 4KB page |

### Access Permissions (AP[7:6])

| AP | EL1 | EL0 |
|----|-----|-----|
| 0b00 | RW | None |
| 0b01 | RW | RW |
| 0b10 | RO | None |
| 0b11 | RO | RO |

## Extending the Simulator

### Adding TLB Simulation

1. Create a `TLB` class with LRU or FIFO replacement
2. Check TLB before each translation table read
3. Track TLB hits/misses in the walk result

## Testing

```bash
# Run tests
/opt/homebrew/bin/uv run pytest tests/ -v

# Run with coverage
/opt/homebrew/bin/uv run pytest tests/ --cov=ptw_viz
```

## References

- [ARM Architecture Reference Manual (ARM DDI 0487)](https://developer.arm.com/documentation/ddi0487/latest)
- [ARM Cortex-A Series Programmer's Guide](https://developer.arm.com/documentation/den0024/latest)
- [FEAT_D128 - 128-bit page table descriptors](https://developer.arm.com/documentation/102378/0100)

## License

GPLv3 License
