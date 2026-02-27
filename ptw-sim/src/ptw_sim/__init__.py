"""
ARM v9 Page Table Walk Simulator.

This package simulates 2-stage page table walks in ARM v9 architecture
with FEAT_D128 extension support and outputs serialized walk traces.

Modules:
    models: Data models for addresses, descriptors, and registers
    core: Page table walk simulation engine
    io: Input parsing and trace output serialization
"""

__version__ = "0.1.0"
__author__ = "Hemin Desai"

from ptw_sim.core.walker import PageTableWalker
from ptw_sim.io.parser import parse_scenario
from ptw_sim.io.formatter import format_output

__all__ = [
    "PageTableWalker",
    "parse_scenario",
    "format_output",
]
