"""
Command-line interface for ptw-viz.

Usage:
    ptw-viz <trace.json> [--format terminal|html|both]
    ptw-viz --help

Examples:
    # Render trace in terminal
    ptw-viz results/scenario_a_success_trace.json

    # Generate HTML visualization
    ptw-viz results/scenario_a_success_trace.json --format html

    # Both terminal and HTML
    ptw-viz results/scenario_a_success_trace.json --format both
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ptw_viz.trace_loader import load_trace
from ptw_viz.terminal import TerminalVisualizer
from ptw_viz.html import HTMLVisualizer


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Visualize ARM v9 Page Table Walk traces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s results/scenario_a_success_trace.json
  %(prog)s results/scenario_a_success_trace.json --format html --output results/
  %(prog)s results/scenario_a_success_trace.json --format both --tree
        """
    )

    parser.add_argument(
        "trace",
        type=Path,
        help="Path to trace JSON file (produced by ptw-sim)"
    )

    parser.add_argument(
        "-f", "--format",
        choices=["terminal", "html", "both"],
        default="terminal",
        help="Output format (default: terminal)"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("results"),
        help="Output directory for HTML files (default: results/)"
    )

    parser.add_argument(
        "-t", "--tree",
        action="store_true",
        help="Show tree view instead of table view (terminal only)"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Generate interactive HTML (with JSON data + template)"
    )

    args = parser.parse_args()

    # Check trace file exists
    if not args.trace.exists():
        print(f"Error: Trace file not found: {args.trace}", file=sys.stderr)
        return 1

    try:
        # Load trace
        trace = load_trace(args.trace)

        # Terminal output
        if args.format in ("terminal", "both"):
            tv = TerminalVisualizer()
            if args.tree:
                tv.print_walk_tree(trace)
            else:
                tv.visualize(trace)

        # HTML output
        if args.format in ("html", "both"):
            hv = HTMLVisualizer()

            if args.interactive:
                template_path, json_path = hv.save_interactive(trace, args.output)
                print(f"\nInteractive visualization:")
                print(f"  Template: {template_path}")
                print(f"  Data:     {json_path}")
            else:
                html_path = args.output / f"{trace.scenario_name}_visualization.html"
                hv.save(trace, html_path)
                print(f"\nHTML saved to: {html_path}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Format error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
