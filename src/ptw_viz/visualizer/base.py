"""
Base visualizer abstract class.

This module defines the interface for page table walk visualizers.
Both terminal and HTML visualizers implement this interface.

Design Pattern: Strategy
    Different visualization strategies can be swapped without
    changing the visualization caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ptw_viz.simulator.walker import WalkResult
from ptw_viz.io.parser import ScenarioConfig


class BaseVisualizer(ABC):
    """
    Abstract base class for walk visualizers.

    Subclasses implement specific visualization strategies
    (terminal, HTML, etc.).
    """

    def __init__(self, config: Optional[ScenarioConfig] = None):
        """
        Initialize the visualizer.

        Args:
            config: Optional scenario configuration for additional context.
        """
        self.config = config

    @abstractmethod
    def visualize(self, result: WalkResult) -> None:
        """
        Visualize a page table walk result.

        Args:
            result: The walk result to visualize.
        """
        pass

    @abstractmethod
    def save(self, result: WalkResult, output_path: Path) -> None:
        """
        Save visualization to a file.

        Args:
            result: The walk result to visualize.
            output_path: Path to save the visualization.
        """
        pass

    def get_scenario_name(self) -> str:
        """Get the scenario name from config."""
        if self.config:
            return self.config.scenario_name
        return "unnamed"

    def get_description(self) -> str:
        """Get the scenario description from config."""
        if self.config:
            return self.config.description
        return ""
