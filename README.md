# ARM v9 Page Table Walker (`ptw`)

This is the workspace root for the ARM v9 MMU simulator project. The project is split into two independent but complementary packages:

- **[ptw-sim](ptw-sim/)** — The simulation engine (`ptw-sim`)
- **[ptw-viz](ptw-viz/)** — The visualization frontend (`ptw-viz`)

## Project Structure

```text
.
├── ptw-sim/             # Simulation logic & scenario processing
├── ptw-viz/             # Terminal and HTML visualization tools
├── examples/            # Shared scenario JSON templates
├── results/             # Default output directory for traces and HTML
└── HOWTO.md             # Comprehensive user guide
```

## Installation

We recommend using [uv](https://github.com/astral-sh/uv) for fast and reliable dependency management.

```bash
# Install both packages in development mode
pip install -e ptw-sim/
pip install -e ptw-viz/
```

Or using `uv`:
```bash
uv sync
```

## Quick Start

The typical workflow involves generating a trace with the simulator and then viewing it with the visualizer.

### 1. Run a Simulation
Produces a trace JSON file containing all walk events.
```bash
ptw-sim examples/scenario_a_success.json --output results/
```

### 2. Visualize the Trace
Render the simulation results in your terminal:
```bash
ptw-viz results/scenario_a_success_trace.json
```

### 3. Generate Interactive HTML
Create a rich, animated visualization for browser viewing:
```bash
ptw-viz results/scenario_a_success_trace.json --format html --output results/
```

## Documentation

- **[HOWTO.md](HOWTO.md)**: Detailed guide on creating scenarios, configuring architecture parameters, and using the interactive tools.
- **[TRACESPEC.md](TRACESPEC.md)**: Formal JSON specification for the walk trace format (v1.0).
- **[ptw-sim/README.md](ptw-sim/README.md)**: Details on the simulation engine and trace format.
- **[ptw-viz/README.md](ptw-viz/README.md)**: Details on visualization modes and terminal options.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.
