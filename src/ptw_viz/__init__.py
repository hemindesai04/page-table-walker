"""
ARM v9 Page Table Walk Simulator and Visualizer.

This package provides tools to simulate and visualize 2-stage page table walks
in ARM v9 architecture with FEAT_D128 extension support.

Modules:
    models: Data models for addresses, descriptors, and registers
    simulator: Core page table walk simulation logic
    io: Input/output handling (JSON parsing and formatting)
    visualizer: Terminal and HTML visualization
"""

__version__ = "0.1.0"
__author__ = "PTW-Viz Contributors"

from ptw_viz.simulator.walker import PageTableWalker
from ptw_viz.io.parser import parse_scenario
from ptw_viz.io.formatter import format_output

__all__ = [
    "PageTableWalker",
    "parse_scenario",
    "format_output",
]
