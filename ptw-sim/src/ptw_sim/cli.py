"""
Command-line interface for ptw-sim.

Usage:
    ptw-sim <scenario.json> [--output <dir>] [--format json|summary]
    ptw-sim --help

Examples:
    # Run a scenario and print summary to terminal
    ptw-sim examples/scenario_a_success.json

    # Run and save a trace JSON file for the visualizer
    ptw-sim examples/scenario_a_success.json --output results/ --format json

    # Print summary AND save trace JSON
    ptw-sim examples/scenario_a_success.json --output results/ --format both
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ptw_sim.models.address import VirtualAddress
from ptw_sim.models.registers import RegisterState
from ptw_sim.core.walker import PageTableWalker
from ptw_sim.core.faults import AccessType
from ptw_sim.io.parser import (
    parse_scenario,
    build_register_state,
    build_translation_tables,
    get_access_type,
    get_virtual_address,
    is_el0_access,
)
from ptw_sim.io.formatter import format_output, save_output, generate_summary


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
        description="ARM v9 Page Table Walk Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s examples/scenario_a_success.json
  %(prog)s examples/scenario_a_success.json --format json --output results/
  %(prog)s examples/scenario_a_success.json --format both --output results/
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
        help="Output directory for trace JSON files (default: results/)"
    )

    parser.add_argument(
        "-f", "--format",
        choices=["summary", "json", "both"],
        default="both",
        help="Output format: summary (terminal), json (trace file), or both (default: both)"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress terminal output"
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
        show_summary = args.format in ("summary", "both") and not args.quiet
        save_json = args.format in ("json", "both")

        # Terminal summary
        if show_summary:
            print(generate_summary(result))

        # Save trace JSON
        if save_json:
            json_path = args.output / f"{config.scenario_name}_trace.json"
            save_output(output, json_path)
            if not args.quiet:
                print(f"\nTrace saved to: {json_path}")
                print(f"Import this file with: ptw-viz {json_path}")

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
