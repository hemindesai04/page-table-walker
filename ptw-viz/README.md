# ARM v9 MMU Visualizer (`ptw-viz`)

A rich visualization frontend for the Page Table Walker project. it transforms the raw JSON traces produced by `ptw-sim` into human-readable tables, trees, and interactive HTML reports.

## Features

- **Terminal Tables**: Color-coded, high-contrast tables using `rich`.
- **Hierarchical Tree View**: Visualizes the walk as a tree, showing the nested relationship between Stage 1 and Stage 2 translations.
- **Static HTML Reports**: Standalone HTML files for documentation and sharing.
- **Interactive Animated Visualizer**: Advanced browser-based frontend with step-by-step playback, binary register inspection, and recursive table navigation.
- **Trace Validation**: Automatically checks trace format versions for compatibility.

## Installation

```bash
cd ptw-viz
pip install -e .
```

## Usage

```bash
# Render trace in terminal (default)
ptw-viz results/trace.json

# Hierarchical tree view
ptw-viz results/trace.json --tree

# Generate a static HTML report
ptw-viz results/trace.json --format html --output results/

# Generate an interactive visualization
ptw-viz results/trace.json --interactive
```

## Visualization Modes

### Terminal (Table/Tree)
The terminal view is best for quick debugging. The **Tree View** (`--tree`) is particularly powerful for 2-stage translations, as it explicitly shows which Stage 2 lookups were required to resolve a Stage 1 descriptor.

### Interactive HTML
The interactive mode (`--interactive`) creates a `ptw_visualizer.html` template and a data JSON file. Open the template in any modern browser to:
- **Play/Pause** the walk animation.
- **Inspect Registers** in binary format.
- **Toggle Views** between a chronological timeline and a recursive table structure.

For more details on using the visualizer features, see [HOWTO.md](HOWTO.md).
