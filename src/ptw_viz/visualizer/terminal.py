"""
Terminal-based visualizer using Rich library.

This module provides colorful, structured terminal output for
page table walk results. It uses the Rich library for:
- Colored text and panels
- Tree structures for walk hierarchy
- Tables for register values and event lists
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich import box

from ptw_viz.visualizer.base import BaseVisualizer
from ptw_viz.simulator.walker import WalkResult, WalkStatus, WalkEvent
from ptw_viz.io.parser import ScenarioConfig


class TerminalVisualizer(BaseVisualizer):
    """
    Rich terminal visualizer for page table walks.

    Produces colorful, structured output including:
    - Walk summary with status
    - Address breakdown (VA → IPA → PA)
    - Event timeline with stage/level info
    - Register snapshots
    - Fault details (if any)
    """

    def __init__(
        self,
        config: Optional[ScenarioConfig] = None,
        console: Optional[Console] = None
    ):
        """
        Initialize the terminal visualizer.

        Args:
            config: Scenario configuration.
            console: Rich Console instance (creates new if None).
        """
        super().__init__(config)
        self.console = console or Console()

    def visualize(self, result: WalkResult) -> None:
        """
        Display the walk result in the terminal.

        Args:
            result: The walk result to visualize.
        """
        # Header
        self._print_header(result)

        # Address breakdown
        self._print_address_breakdown(result)

        # Walk status
        self._print_status(result)

        # Event timeline
        self._print_events(result)

        # Register snapshots
        self._print_registers(result)

        # Fault details (if any)
        if result.fault:
            self._print_fault(result)

        # Permissions (if successful)
        if result.final_permissions:
            self._print_permissions(result)

    def save(self, result: WalkResult, output_path: Path) -> None:
        """
        Save terminal output to a file.

        Args:
            result: The walk result.
            output_path: Path to save output (as text).
        """
        # Create a file console
        file_console = Console(file=open(output_path, "w"), force_terminal=True)
        old_console = self.console
        self.console = file_console

        try:
            self.visualize(result)
        finally:
            self.console = old_console
            file_console.file.close()

    def _print_header(self, result: WalkResult) -> None:
        """Print the header panel."""
        scenario_name = self.get_scenario_name()
        description = self.get_description()

        header_text = f"[bold cyan]ARM v9 Page Table Walk Visualization[/]\n"
        header_text += f"[dim]Scenario: {scenario_name}[/]"
        if description:
            header_text += f"\n[dim]{description}[/]"

        self.console.print(Panel(header_text, box=box.DOUBLE))

    def _print_address_breakdown(self, result: WalkResult) -> None:
        """Print the address breakdown panel."""
        va = result.input_va

        # Create address breakdown table
        table = Table(title="Address Breakdown", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="yellow")
        table.add_column("Bits", style="dim")

        table.add_row("Virtual Address", va.to_hex(), "[47:0]")
        table.add_row("  L0 Index", f"0x{va.l0_index:03X}", "[47:39]")
        table.add_row("  L1 Index", f"0x{va.l1_index:03X}", "[38:30]")
        table.add_row("  L2 Index", f"0x{va.l2_index:03X}", "[29:21]")
        table.add_row("  L3 Index", f"0x{va.l3_index:03X}", "[20:12]")
        table.add_row("  Page Offset", f"0x{va.page_offset:03X}", "[11:0]")

        if result.ipa:
            table.add_row("", "", "")
            table.add_row("Intermediate PA (IPA)", result.ipa.to_hex(), "S1 output")

        if result.output_pa:
            table.add_row("Physical Address (PA)", result.output_pa.to_hex(), "Final")

        self.console.print(table)

    def _print_status(self, result: WalkResult) -> None:
        """Print the walk status."""
        if result.status == WalkStatus.SUCCESS:
            status_text = "[bold green]✓ TRANSLATION SUCCESSFUL[/]"
        else:
            status_text = f"[bold red]✗ TRANSLATION FAILED: {result.status.name}[/]"

        self.console.print(Panel(status_text, title="Result", box=box.ROUNDED))

    def _print_events(self, result: WalkResult) -> None:
        """Print the event timeline."""
        table = Table(
            title=f"Walk Events ({result.total_memory_accesses} memory accesses)",
            box=box.ROUNDED
        )

        table.add_column("#", style="dim", width=4)
        table.add_column("Type", style="bold", width=4)
        table.add_column("Stage", width=6)
        table.add_column("Level", width=6)
        table.add_column("Purpose", style="cyan", width=35)
        table.add_column("Result", style="yellow", width=10)
        table.add_column("Output Address", style="green", width=20)

        for event in result.events:
            # Color coding by stage
            if event.stage == 1:
                stage_style = "[blue]S1[/]"
            else:
                stage_style = "[magenta]S2[/]"

            # Color coding by result
            if event.result == "INVALID":
                result_style = f"[red]{event.result}[/]"
            elif event.result == "TABLE":
                result_style = f"[cyan]{event.result}[/]"
            elif event.result == "BLOCK":
                result_style = f"[bold yellow]{event.result}[/]"
            else:
                result_style = f"[green]{event.result}[/]"

            table.add_row(
                str(event.event_id),
                "T",
                stage_style,
                f"L{event.level}",
                event.purpose,
                result_style,
                f"0x{event.output:012X}"
            )

        self.console.print(table)

    def _print_registers(self, result: WalkResult) -> None:
        """Print register snapshots."""
        if not result.register_snapshots:
            return

        table = Table(title="Register Snapshots", box=box.ROUNDED)
        table.add_column("Point", style="cyan")
        table.add_column("VA", style="yellow")
        table.add_column("IPA", style="magenta")
        table.add_column("PA", style="green")

        for snapshot in result.register_snapshots:
            table.add_row(
                snapshot.get("point", ""),
                snapshot.get("VA", "-"),
                snapshot.get("IPA", "-") or "-",
                snapshot.get("PA", "-") or "-"
            )

        self.console.print(table)

    def _print_fault(self, result: WalkResult) -> None:
        """Print fault details."""
        fault = result.fault

        fault_text = f"[bold red]Fault Type:[/] {fault.fault_type.name}\n"
        fault_text += f"[bold red]Stage:[/] {fault.stage}  "
        fault_text += f"[bold red]Level:[/] {fault.level}\n"
        fault_text += f"[bold red]Address:[/] 0x{fault.address:016X}\n"
        fault_text += f"[bold red]Message:[/] {fault.message}"

        if fault.far_el1:
            fault_text += f"\n[bold red]FAR_EL1:[/] 0x{fault.far_el1:016X}"
        if fault.far_el2:
            fault_text += f"\n[bold red]FAR_EL2:[/] 0x{fault.far_el2:016X}"

        self.console.print(Panel(
            fault_text,
            title="[red]Fault Details[/]",
            border_style="red",
            box=box.ROUNDED
        ))

    def _print_permissions(self, result: WalkResult) -> None:
        """Print final permissions."""
        perms = result.final_permissions

        table = Table(title="Final Permissions", box=box.ROUNDED)
        table.add_column("Level", style="cyan")
        table.add_column("Read", style="green")
        table.add_column("Write", style="yellow")
        table.add_column("Execute", style="magenta")

        def _yn(val: bool) -> str:
            return "[green]Yes[/]" if val else "[red]No[/]"

        table.add_row(
            "EL0 (User)",
            _yn(perms.read_el0),
            _yn(perms.write_el0),
            _yn(perms.execute_el0)
        )
        table.add_row(
            "EL1 (Kernel)",
            _yn(perms.read_el1),
            _yn(perms.write_el1),
            _yn(perms.execute_el1)
        )

        self.console.print(table)

    def print_walk_tree(self, result: WalkResult) -> None:
        """
        Print an alternative tree view of the walk.

        This shows the hierarchical nature of the walk with
        S2 events nested under their triggering S1 events.
        """
        tree = Tree(f"[bold]Walk: {result.input_va.to_hex()}[/]")

        if result.s1_result:
            s1_branch = tree.add("[blue]Stage 1 (VA → IPA)[/]")

            for s1_event in result.s1_result.events:
                level_text = f"L{s1_event.level}: {s1_event.descriptor_type.name}"
                s1_node = s1_branch.add(f"[cyan]{level_text}[/]")

                # Add S2 events for this table translation
                if s1_event.s2_events:
                    s2_branch = s1_node.add("[magenta]S2 Translation[/]")
                    for s2_event in s1_event.s2_events:
                        s2_branch.add(
                            f"L{s2_event.level}: {s2_event.descriptor_type.name}"
                        )

        if result.s2_final_result and result.s2_final_result.events:
            s2_final = tree.add("[magenta]Final Stage 2 (IPA → PA)[/]")
            for s2_event in result.s2_final_result.events:
                s2_final.add(f"L{s2_event.level}: {s2_event.descriptor_type.name}")

        # Result
        if result.status == WalkStatus.SUCCESS:
            tree.add(f"[green]✓ PA: {result.output_pa.to_hex()}[/]")
        else:
            tree.add(f"[red]✗ {result.status.name}[/]")

        self.console.print(tree)
