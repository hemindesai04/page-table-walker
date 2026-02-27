"""
Terminal-based visualizer using Rich library.

This module provides colorful, structured terminal output for
page table walk traces. It uses the Rich library for:
- Colored text and panels
- Tree structures for walk hierarchy
- Tables for register values and event lists

This visualizer operates on TraceData (from trace_loader) and has
NO dependency on the simulator package.
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

from ptw_viz.trace_loader import TraceData, TraceEvent


class TerminalVisualizer:
    """
    Rich terminal visualizer for page table walk traces.

    Produces colorful, structured output including:
    - Walk summary with status
    - Address breakdown (VA → IPA → PA)
    - Event timeline with stage/level info
    - Register snapshots
    - Fault details (if any)
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the terminal visualizer.

        Args:
            console: Rich Console instance (creates new if None).
        """
        self.console = console or Console()

    def visualize(self, trace: TraceData) -> None:
        """
        Display the walk trace in the terminal.

        Args:
            trace: The trace data to visualize.
        """
        # Header
        self._print_header(trace)

        # Address breakdown
        self._print_address_breakdown(trace)

        # Walk status
        self._print_status(trace)

        # Event timeline
        self._print_events(trace)

        # Register snapshots
        self._print_registers(trace)

        # Fault details (if any)
        if trace.fault:
            self._print_fault(trace)

        # Permissions (if successful)
        if trace.final_permissions:
            self._print_permissions(trace)

    def save(self, trace: TraceData, output_path: Path) -> None:
        """
        Save terminal output to a file.

        Args:
            trace: The trace data.
            output_path: Path to save output (as text).
        """
        file_console = Console(file=open(output_path, "w"), force_terminal=True)
        old_console = self.console
        self.console = file_console

        try:
            self.visualize(trace)
        finally:
            self.console = old_console
            file_console.file.close()

    def _print_header(self, trace: TraceData) -> None:
        """Print the header panel."""
        header_text = f"[bold cyan]ARM v9 Page Table Walk Visualization[/]\n"
        header_text += f"[dim]Scenario: {trace.scenario_name}[/]"
        if trace.description:
            header_text += f"\n[dim]{trace.description}[/]"

        self.console.print(Panel(header_text, box=box.DOUBLE))

    def _print_address_breakdown(self, trace: TraceData) -> None:
        """Print the address breakdown panel."""
        table = Table(title="Address Breakdown", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="yellow")
        table.add_column("Bits", style="dim")

        table.add_row("Virtual Address", trace.virtual_address, "[47:0]")
        table.add_row("  L0 Index", trace.va_l0_index, "[47:39]")
        table.add_row("  L1 Index", trace.va_l1_index, "[38:30]")
        table.add_row("  L2 Index", trace.va_l2_index, "[29:21]")
        table.add_row("  L3 Index", trace.va_l3_index, "[20:12]")
        table.add_row("  Page Offset", trace.va_page_offset, "[11:0]")

        if trace.ipa:
            table.add_row("", "", "")
            table.add_row("Intermediate PA (IPA)", trace.ipa, "S1 output")

        if trace.final_pa:
            table.add_row("Physical Address (PA)", trace.final_pa, "Final")

        self.console.print(table)

    def _print_status(self, trace: TraceData) -> None:
        """Print the walk status."""
        if trace.is_success:
            status_text = "[bold green]✓ TRANSLATION SUCCESSFUL[/]"
        else:
            status_text = f"[bold red]✗ TRANSLATION FAILED: {trace.status}[/]"

        self.console.print(Panel(status_text, title="Result", box=box.ROUNDED))

    def _print_events(self, trace: TraceData) -> None:
        """Print the event timeline."""
        table = Table(
            title=f"Walk Events ({trace.total_memory_accesses} memory accesses)",
            box=box.ROUNDED
        )

        table.add_column("#", style="dim", width=4)
        table.add_column("Type", style="bold", width=4)
        table.add_column("Stage", width=6)
        table.add_column("Level", width=6)
        table.add_column("Purpose", style="cyan", width=35)
        table.add_column("Result", style="yellow", width=10)
        table.add_column("Output Address", style="green", width=20)

        for event in trace.events:
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
                event.output
            )

        self.console.print(table)

    def _print_registers(self, trace: TraceData) -> None:
        """Print register snapshots."""
        if not trace.register_snapshots:
            return

        table = Table(title="Register Snapshots", box=box.ROUNDED)
        table.add_column("Point", style="cyan")
        table.add_column("VA", style="yellow")
        table.add_column("IPA", style="magenta")
        table.add_column("PA", style="green")

        for snapshot in trace.register_snapshots:
            table.add_row(
                snapshot.get("point", ""),
                snapshot.get("VA", "-"),
                snapshot.get("IPA", "-") or "-",
                snapshot.get("PA", "-") or "-"
            )

        self.console.print(table)

    def _print_fault(self, trace: TraceData) -> None:
        """Print fault details."""
        fault = trace.fault

        fault_text = f"[bold red]Fault Type:[/] {fault.get('fault_type', 'UNKNOWN')}\n"
        fault_text += f"[bold red]Stage:[/] {fault.get('stage', '?')}  "
        fault_text += f"[bold red]Level:[/] {fault.get('level', '?')}\n"
        fault_text += f"[bold red]Address:[/] {fault.get('address', '?')}\n"
        fault_text += f"[bold red]Message:[/] {fault.get('message', '')}"

        if fault.get("FAR_EL1"):
            fault_text += f"\n[bold red]FAR_EL1:[/] {fault['FAR_EL1']}"
        if fault.get("FAR_EL2"):
            fault_text += f"\n[bold red]FAR_EL2:[/] {fault['FAR_EL2']}"

        self.console.print(Panel(
            fault_text,
            title="[red]Fault Details[/]",
            border_style="red",
            box=box.ROUNDED
        ))

    def _print_permissions(self, trace: TraceData) -> None:
        """Print final permissions."""
        perms = trace.final_permissions

        table = Table(title="Final Permissions", box=box.ROUNDED)
        table.add_column("Level", style="cyan")
        table.add_column("Read", style="green")
        table.add_column("Write", style="yellow")
        table.add_column("Execute", style="magenta")

        def _yn(val: bool) -> str:
            return "[green]Yes[/]" if val else "[red]No[/]"

        table.add_row(
            "EL0 (User)",
            _yn(perms.get("read_el0", False)),
            _yn(perms.get("write_el0", False)),
            _yn(perms.get("execute_el0", False))
        )
        table.add_row(
            "EL1 (Kernel)",
            _yn(perms.get("read_el1", False)),
            _yn(perms.get("write_el1", False)),
            _yn(perms.get("execute_el1", False))
        )

        self.console.print(table)

    def print_walk_tree(self, trace: TraceData) -> None:
        """
        Print an alternative tree view of the walk.

        Groups S2 events under their corresponding S1 events.
        """
        tree = Tree(f"[bold]Walk: {trace.virtual_address}[/]")

        s1_branch = tree.add("[blue]Stage 1 (VA → IPA)[/]")

        # Group events: S2 events before an S1 event belong to that S1 event
        pending_s2: list[TraceEvent] = []
        for event in trace.events:
            if event.stage == 2 and "Final S2" not in event.purpose:
                pending_s2.append(event)
            elif event.stage == 1:
                level_text = f"L{event.level}: {event.result}"
                s1_node = s1_branch.add(f"[cyan]{level_text}[/]")
                if pending_s2:
                    s2_branch = s1_node.add("[magenta]S2 Translation[/]")
                    for s2_event in pending_s2:
                        s2_branch.add(f"L{s2_event.level}: {s2_event.result}")
                    pending_s2 = []

        # Final S2 events
        final_s2 = [e for e in trace.events if "Final S2" in e.purpose]
        if final_s2:
            s2_final = tree.add("[magenta]Final Stage 2 (IPA → PA)[/]")
            for s2_event in final_s2:
                s2_final.add(f"L{s2_event.level}: {s2_event.result}")

        # Result
        if trace.is_success:
            tree.add(f"[green]✓ PA: {trace.final_pa}[/]")
        else:
            tree.add(f"[red]✗ {trace.status}[/]")

        self.console.print(tree)
