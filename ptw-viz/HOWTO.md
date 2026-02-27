# ptw-viz User Guide

This guide covers the visualization tools available in the Page Table Walker project, explaining how to interpret the various outputs and use the interactive features.

## Terminal Visualization

### Table View (Default)
The standard table view lists "Walk Events" in chronological order. 
- **Type**: `T` (Translation) or `D` (Data/Final).
- **Stage/Level**: Identifies which part of the hierarchy is being walked.
- **Descriptor**: The raw 64-bit value found in memory.
- **Outcome**: Whether the descriptor points to a `TABLE`, a `PAGE`, or is `INVALID`.

### Tree View (`--tree`)
In a 2-stage translation, Stage 1 table addresses are themselves Intermediate Physical Addresses (IPAs) that must be translated by Stage 2. The Tree View visually nests these Stage 2 lookups under the Stage 1 level they enable, making the complex flow much easier to follow.

## Interactive HTML Features

When you run `ptw-viz --interactive`, a dashboard is generated that allows deep inspection.

### Timeline View
- **Playback Controls**: Step through the walk one memory access at a time.
- **Context Panels**: See the specific bits extracted from the VA/IPA for the current step.
- **Flow Diagram**: A dynamic diagram showing the path from VA to PA.

### Recursive Table View
This view organizes the translation as a nested hierarchy. You can expand a Stage 1 level to see the exactly which Stage 2 steps were performed to resolve that Stage 1 table's physical address.

### Binary Register Inspector
Click on any register name (like `TTBR0_EL1` or `TCR_EL1`) to see a full 64-bit binary breakdown with field labels, helping you verify bit-field configurations.

## Troubleshooting

### "No trace file found"
Ensure the path to the JSON file produced by `ptw-sim` is correct. By default, the simulator saves traces in the `results/` directory.

### "Browser doesn't load data"
The interactive visualizer uses a local JSON file. Some browsers (like Chrome) have security restrictions on loading local files via `file://`.
- **Solution 1**: Use the "📂 Load Another File" button in the visualizer to manually select the JSON data.
- **Solution 2**: Serve the directory using a local web server: `python -m http.server 8000`.

### "Missing colors in terminal"
The visualizer uses the `rich` library. Ensure your terminal supports TrueColor or 256-color modes.
