# ARM v9 MMU Simulator (`ptw-sim`)

The simulation engine for the Page Table Walker project. It performs full 2-stage (VA → IPA → PA) address translations based on ARM v9 architecture specifications and produces detailed execution traces.

## Features

- **2-Stage Translation**: Full support for Stage 1 (VA to IPA) and Stage 2 (IPA to PA) lookups.
- **Granule Support**: Handles dynamic 4KB, 16KB, and 64KB granules independently configured per-stage (i.e. Stage 1 translating via 16KB tables over a 64KB Stage 2 virtualization space).
- **Modern Architecture**: Support for FEAT_D128 (128-bit descriptors) and large physical address spaces.
- **Fault Detection**: Accurately identifies Translation, Permission, and Address Size faults.
- **Trace Serialization**: Outputs a comprehensive JSON trace file (v1.0) for visualization tools.

## Installation

```bash
cd ptw-sim
pip install -e .
```

## Usage

```bash
# Basic simulation with terminal summary
ptw-sim examples/scenario_a_success.json

# Generate trace JSON for visualizer
ptw-sim examples/scenario_a_success.json --format json --output results/

# Generate both summary and trace
ptw-sim examples/scenario_a_success.json --format both
```

## Trace Format (v1.0)

The generated trace file includes:
- **Environment**: Architecture parameters and register states (`TTBR`, `TCR`, etc.).
- **Walk Events**: A chronological list of every memory access made during the walk.
- **Register Snapshots**: The state of relevant registers at the time of each event.
- **Final Result**: The translated address or detailed fault information.

For more details on creating simulation scenarios and interpreting results, see [HOWTO.md](HOWTO.md).
