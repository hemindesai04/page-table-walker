"""
Command-line interface for PTW-Viz.

Usage:
    ptw-viz <scenario.json> [--output <dir>] [--format terminal|html|both|json]
    ptw-viz --help

Examples:
    # Run with terminal visualization
    ptw-viz examples/scenario_a_success.json

    # Save HTML output
    ptw-viz examples/scenario_a_success.json --output results/ --format html

    # Generate both terminal and HTML
    ptw-viz examples/scenario_a_success.json --format both
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ptw_viz.models.address import VirtualAddress
from ptw_viz.models.registers import RegisterState
from ptw_viz.simulator.walker import PageTableWalker
from ptw_viz.simulator.faults import AccessType
from ptw_viz.io.parser import (
    parse_scenario,
    build_register_state,
    build_translation_tables,
    get_access_type,
    get_virtual_address,
    is_el0_access,
)
from ptw_viz.io.formatter import format_output, save_output, generate_summary
from ptw_viz.visualizer.terminal import TerminalVisualizer
from ptw_viz.visualizer.html import HTMLVisualizer


def run_simulation(scenario_path: Path) -> tuple:
    """
    Run a simulation from a scenario file.

    Args:
        scenario_path: Path to the scenario JSON file.

    Returns:
        Tuple of (config, result).
    """
    # Parse configuration
    config = parse_scenario(scenario_path)

    # Build components
    register_state = build_register_state(config)
    s1_tables, s2_tables = build_translation_tables(config)
    va = get_virtual_address(config)
    access_type = get_access_type(config)
    is_el0 = is_el0_access(config)

    # Create walker and run
    walker = PageTableWalker(register_state, s1_tables, s2_tables)
    result = walker.walk(va, access_type, is_el0)

    return config, result


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ARM v9 Page Table Walk Simulator and Visualizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s examples/scenario_a_success.json
  %(prog)s examples/scenario_a_success.json --format html --output results/
  %(prog)s examples/scenario_a_success.json --format both
        """
    )

    parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario JSON file"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("results"),
        help="Output directory for results (default: results/)"
    )

    parser.add_argument(
        "-f", "--format",
        choices=["terminal", "html", "both", "json", "interactive"],
        default="terminal",
        help="Output format: terminal, html, both, json, or interactive (default: terminal)"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress terminal output (useful with --format json)"
    )

    parser.add_argument(
        "--tree",
        action="store_true",
        help="Show tree view instead of table (terminal only)"
    )

    args = parser.parse_args()

    # Check scenario file exists
    if not args.scenario.exists():
        print(f"Error: Scenario file not found: {args.scenario}", file=sys.stderr)
        return 1

    try:
        # Run simulation
        config, result = run_simulation(args.scenario)

        # Create output
        output = format_output(result, config)

        # Determine output actions
        show_terminal = args.format in ("terminal", "both") and not args.quiet
        save_html = args.format in ("html", "both")
        save_json = args.format == "json"

        # Terminal output
        if show_terminal:
            term_viz = TerminalVisualizer(config)
            if args.tree:
                term_viz.print_walk_tree(result)
            else:
                term_viz.visualize(result)

        # HTML output
        if save_html:
            html_viz = HTMLVisualizer(config)
            html_path = args.output / f"{config.scenario_name}.html"
            html_viz.save(result, html_path)
            if not args.quiet:
                print(f"\nHTML saved to: {html_path}")

        # Interactive output
        if args.format == "interactive":
            html_viz = HTMLVisualizer(config)
            template_path, json_path = html_viz.save_interactive(result, args.output)
            if not args.quiet:
                print(f"\nGenerated JSON data: {json_path}")
                print(f"Visualizer template: {template_path}")
                print(f"\nOpen {template_path} in a browser, then upload {json_path.name}")
                print("(The template is reusable - just upload different JSON files)")

        # JSON output
        if save_json:
            json_path = args.output / f"{config.scenario_name}.json"
            save_output(output, json_path)
            if not args.quiet:
                print(f"JSON saved to: {json_path}")

        # Always save JSON alongside HTML if using both
        if save_html:
            json_path = args.output / f"{config.scenario_name}.json"
            save_output(output, json_path)

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise  # Re-raise for debugging


if __name__ == "__main__":
    sys.exit(main())
