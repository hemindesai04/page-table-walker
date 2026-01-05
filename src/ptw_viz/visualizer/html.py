"""
HTML-based visualizer using Jinja2 templates.

This module generates interactive HTML visualizations for page table
walks. The HTML output includes:
- Styled boxes for addresses and results
- Color-coded event timeline
- Collapsible sections for details
- Register value displays
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime

from jinja2 import Template

from ptw_viz.visualizer.base import BaseVisualizer
from ptw_viz.simulator.walker import WalkResult, WalkStatus
from ptw_viz.io.parser import ScenarioConfig


# HTML template for the visualization
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PTW Visualization: {{ scenario_name }}</title>
    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-tertiary: #0f3460;
            --accent-blue: #4da8da;
            --accent-green: #00d26a;
            --accent-red: #ff6b6b;
            --accent-yellow: #ffd93d;
            --accent-magenta: #c792ea;
            --text-primary: #e8e8e8;
            --text-secondary: #a0a0a0;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: var(--bg-secondary);
            border-radius: 16px;
            border: 1px solid var(--bg-tertiary);
        }

        .header h1 {
            font-size: 2.5rem;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-magenta));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .header .scenario-name {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }

        .status-badge {
            display: inline-block;
            padding: 0.5rem 1.5rem;
            border-radius: 25px;
            font-weight: bold;
            font-size: 1.2rem;
            margin-top: 1rem;
        }

        .status-success {
            background: rgba(0, 210, 106, 0.2);
            border: 2px solid var(--accent-green);
            color: var(--accent-green);
        }

        .status-fault {
            background: rgba(255, 107, 107, 0.2);
            border: 2px solid var(--accent-red);
            color: var(--accent-red);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid var(--bg-tertiary);
        }

        .card h2 {
            color: var(--accent-blue);
            font-size: 1.3rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--bg-tertiary);
        }

        .address-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .address-label {
            color: var(--text-secondary);
        }

        .address-value {
            font-family: 'Fira Code', monospace;
            color: var(--accent-yellow);
        }

        .events-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }

        .events-table th {
            background: var(--bg-tertiary);
            padding: 0.75rem;
            text-align: left;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .events-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--bg-tertiary);
            font-family: 'Fira Code', monospace;
            font-size: 0.85rem;
        }

        .events-table tr:hover {
            background: rgba(77, 168, 218, 0.1);
        }

        .stage-1 { color: var(--accent-blue); }
        .stage-2 { color: var(--accent-magenta); }
        .result-table { color: var(--accent-blue); }
        .result-page { color: var(--accent-green); }
        .result-block { color: var(--accent-yellow); font-weight: bold; }
        .result-invalid { color: var(--accent-red); }

        .register-chip {
            display: inline-block;
            background: var(--bg-tertiary);
            padding: 0.25rem 0.75rem;
            border-radius: 15px;
            margin: 0.25rem;
            font-family: 'Fira Code', monospace;
            font-size: 0.8rem;
        }

        .fault-card {
            background: rgba(255, 107, 107, 0.1);
            border: 1px solid var(--accent-red);
        }

        .fault-card h2 {
            color: var(--accent-red);
        }

        .permissions-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.5rem;
            margin-top: 1rem;
        }

        .perm-cell {
            text-align: center;
            padding: 0.5rem;
            border-radius: 8px;
            font-size: 0.85rem;
        }

        .perm-header {
            background: var(--bg-tertiary);
            font-weight: bold;
        }

        .perm-yes {
            background: rgba(0, 210, 106, 0.2);
            color: var(--accent-green);
        }

        .perm-no {
            background: rgba(255, 107, 107, 0.2);
            color: var(--accent-red);
        }

        .summary-stat {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            padding: 1.5rem;
            background: var(--bg-tertiary);
            border-radius: 10px;
            margin: 0.5rem;
        }

        .summary-stat .value {
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--accent-blue);
        }

        .summary-stat .label {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        .timestamp {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 2rem;
        }

        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .header h1 {
                font-size: 1.8rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>ARM v9 Page Table Walk</h1>
            <p class="scenario-name">{{ scenario_name }}{% if description %} - {{ description }}{% endif %}</p>
            <div class="status-badge {{ 'status-success' if status == 'SUCCESS' else 'status-fault' }}">
                {% if status == 'SUCCESS' %}✓ Translation Successful{% else %}✗ {{ status }}{% endif %}
            </div>
        </header>

        <div class="grid">
            <!-- Address Breakdown -->
            <div class="card">
                <h2>📍 Address Breakdown</h2>
                <div class="address-row">
                    <span class="address-label">Virtual Address</span>
                    <span class="address-value">{{ va }}</span>
                </div>
                <div class="address-row">
                    <span class="address-label">L0 Index [47:39]</span>
                    <span class="address-value">{{ l0_index }}</span>
                </div>
                <div class="address-row">
                    <span class="address-label">L1 Index [38:30]</span>
                    <span class="address-value">{{ l1_index }}</span>
                </div>
                <div class="address-row">
                    <span class="address-label">L2 Index [29:21]</span>
                    <span class="address-value">{{ l2_index }}</span>
                </div>
                <div class="address-row">
                    <span class="address-label">L3 Index [20:12]</span>
                    <span class="address-value">{{ l3_index }}</span>
                </div>
                <div class="address-row">
                    <span class="address-label">Page Offset [11:0]</span>
                    <span class="address-value">{{ page_offset }}</span>
                </div>
                {% if ipa %}
                <div class="address-row" style="margin-top: 1rem; border-top: 2px solid var(--bg-tertiary); padding-top: 1rem;">
                    <span class="address-label">Intermediate PA</span>
                    <span class="address-value" style="color: var(--accent-magenta);">{{ ipa }}</span>
                </div>
                {% endif %}
                {% if pa %}
                <div class="address-row">
                    <span class="address-label">Physical Address</span>
                    <span class="address-value" style="color: var(--accent-green);">{{ pa }}</span>
                </div>
                {% endif %}
            </div>

            <!-- Summary Stats -->
            <div class="card">
                <h2>📊 Summary</h2>
                <div style="display: flex; flex-wrap: wrap; justify-content: center;">
                    <div class="summary-stat">
                        <span class="value">{{ total_accesses }}</span>
                        <span class="label">Memory Accesses</span>
                    </div>
                    <div class="summary-stat">
                        <span class="value">{{ s1_events }}</span>
                        <span class="label">S1 Events</span>
                    </div>
                    <div class="summary-stat">
                        <span class="value">{{ s2_events }}</span>
                        <span class="label">S2 Events</span>
                    </div>
                </div>
            </div>
        </div>

        {% if permissions %}
        <div class="card" style="margin-bottom: 2rem;">
            <h2>🔒 Final Permissions</h2>
            <div class="permissions-grid">
                <div class="perm-cell perm-header"></div>
                <div class="perm-cell perm-header">Read</div>
                <div class="perm-cell perm-header">Write</div>
                <div class="perm-cell perm-header">Execute</div>

                <div class="perm-cell perm-header">EL0 (User)</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.read_el0 else 'perm-no' }}">{{ 'Yes' if permissions.read_el0 else 'No' }}</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.write_el0 else 'perm-no' }}">{{ 'Yes' if permissions.write_el0 else 'No' }}</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.execute_el0 else 'perm-no' }}">{{ 'Yes' if permissions.execute_el0 else 'No' }}</div>

                <div class="perm-cell perm-header">EL1 (Kernel)</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.read_el1 else 'perm-no' }}">{{ 'Yes' if permissions.read_el1 else 'No' }}</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.write_el1 else 'perm-no' }}">{{ 'Yes' if permissions.write_el1 else 'No' }}</div>
                <div class="perm-cell {{ 'perm-yes' if permissions.execute_el1 else 'perm-no' }}">{{ 'Yes' if permissions.execute_el1 else 'No' }}</div>
            </div>
        </div>
        {% endif %}

        {% if fault %}
        <div class="card fault-card" style="margin-bottom: 2rem;">
            <h2>⚠️ Fault Details</h2>
            <div class="address-row">
                <span class="address-label">Fault Type</span>
                <span class="address-value">{{ fault.fault_type }}</span>
            </div>
            <div class="address-row">
                <span class="address-label">Stage / Level</span>
                <span class="address-value">S{{ fault.stage }} L{{ fault.level }}</span>
            </div>
            <div class="address-row">
                <span class="address-label">Faulting Address</span>
                <span class="address-value">{{ fault.address }}</span>
            </div>
            <div class="address-row">
                <span class="address-label">Message</span>
                <span class="address-value" style="color: var(--accent-red);">{{ fault.message }}</span>
            </div>
            {% if fault.far_el1 %}
            <div class="address-row">
                <span class="address-label">FAR_EL1</span>
                <span class="address-value">{{ fault.far_el1 }}</span>
            </div>
            {% endif %}
        </div>
        {% endif %}

        <!-- Events Table -->
        <div class="card">
            <h2>📋 Translation Events</h2>
            <table class="events-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Type</th>
                        <th>Stage</th>
                        <th>Level</th>
                        <th>Purpose</th>
                        <th>Result</th>
                        <th>Output Address</th>
                    </tr>
                </thead>
                <tbody>
                    {% for event in events %}
                    <tr>
                        <td>{{ event.event_id }}</td>
                        <td>{{ event.event_type }}</td>
                        <td class="{{ 'stage-1' if event.stage == 1 else 'stage-2' }}">S{{ event.stage }}</td>
                        <td>L{{ event.level }}</td>
                        <td>{{ event.purpose }}</td>
                        <td class="result-{{ event.result|lower }}">{{ event.result }}</td>
                        <td>{{ event.output }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <p class="timestamp">Generated: {{ timestamp }}</p>
    </div>
</body>
</html>
"""


class HTMLVisualizer(BaseVisualizer):
    """
    HTML visualizer for page table walks.

    Generates a standalone HTML file with styled visualization
    of the page table walk, suitable for viewing in a browser.
    """

    def __init__(self, config: Optional[ScenarioConfig] = None):
        """
        Initialize the HTML visualizer.

        Args:
            config: Scenario configuration.
        """
        super().__init__(config)
        self.template = Template(HTML_TEMPLATE)

    def visualize(self, result: WalkResult) -> None:
        """
        Generate and print HTML to stdout.

        For HTML, this is less useful than save(), but provides
        the same interface as TerminalVisualizer.
        """
        html = self._render(result)
        print(html)

    def save(self, result: WalkResult, output_path: Path) -> None:
        """
        Save HTML visualization to a file.

        Args:
            result: The walk result.
            output_path: Path to save HTML file.
        """
        html = self._render(result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _render(self, result: WalkResult) -> str:
        """Render the HTML from template."""
        va = result.input_va

        # Count events by stage
        s1_events = sum(1 for e in result.events if e.stage == 1)
        s2_events = sum(1 for e in result.events if e.stage == 2)

        # Prepare permissions dict
        permissions = None
        if result.final_permissions:
            permissions = {
                "read_el0": result.final_permissions.read_el0,
                "write_el0": result.final_permissions.write_el0,
                "execute_el0": result.final_permissions.execute_el0,
                "read_el1": result.final_permissions.read_el1,
                "write_el1": result.final_permissions.write_el1,
                "execute_el1": result.final_permissions.execute_el1,
            }

        # Prepare fault dict
        fault = None
        if result.fault:
            fault = {
                "fault_type": result.fault.fault_type.name,
                "stage": result.fault.stage,
                "level": result.fault.level,
                "address": f"0x{result.fault.address:016X}",
                "message": result.fault.message,
                "far_el1": f"0x{result.fault.far_el1:016X}" if result.fault.far_el1 else None,
            }

        # Prepare events list
        events = []
        for e in result.events:
            events.append({
                "event_id": e.event_id,
                "event_type": e.event_type,
                "stage": e.stage,
                "level": e.level,
                "purpose": e.purpose,
                "result": e.result,
                "output": f"0x{e.output:012X}",
            })

        context = {
            "scenario_name": self.get_scenario_name(),
            "description": self.get_description(),
            "status": result.status.name,
            "va": va.to_hex(),
            "l0_index": f"0x{va.l0_index:03X}",
            "l1_index": f"0x{va.l1_index:03X}",
            "l2_index": f"0x{va.l2_index:03X}",
            "l3_index": f"0x{va.l3_index:03X}",
            "page_offset": f"0x{va.page_offset:03X}",
            "ipa": result.ipa.to_hex() if result.ipa else None,
            "pa": result.output_pa.to_hex() if result.output_pa else None,
            "total_accesses": result.total_memory_accesses,
            "s1_events": s1_events,
            "s2_events": s2_events,
            "permissions": permissions,
            "fault": fault,
            "events": events,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return self.template.render(**context)

    def render_to_string(self, result: WalkResult) -> str:
        """
        Render HTML to string without saving.

        Args:
            result: The walk result.

        Returns:
            HTML string.
        """
        return self._render(result)

    def export_json(self, result: WalkResult, output_path: Path) -> None:
        """
        Export walk result as JSON for interactive visualization.

        Args:
            result: The walk result.
            output_path: Path to save JSON file.
        """
        import json

        va = result.input_va

        # Prepare events with detailed address info
        events = []
        for e in result.events:
            events.append({
                "event_id": e.event_id,
                "event_type": e.event_type,
                "stage": e.stage,
                "level": e.level,
                "purpose": e.purpose,
                "result": e.result,
                "address": f"0x{e.address:016X}",
                "descriptor_value": f"0x{e.descriptor_value:016X}",
                "output": f"0x{e.output:016X}",
            })

        # Prepare permissions
        permissions = None
        if result.final_permissions:
            permissions = {
                "read_el0": result.final_permissions.read_el0,
                "write_el0": result.final_permissions.write_el0,
                "execute_el0": result.final_permissions.execute_el0,
                "read_el1": result.final_permissions.read_el1,
                "write_el1": result.final_permissions.write_el1,
                "execute_el1": result.final_permissions.execute_el1,
            }

        # Prepare fault
        fault = None
        if result.fault:
            fault = {
                "fault_type": result.fault.fault_type.name,
                "stage": result.fault.stage,
                "level": result.fault.level,
                "address": f"0x{result.fault.address:016X}",
                "message": result.fault.message,
            }

        data = {
            "scenario_name": self.get_scenario_name(),
            "description": self.get_description(),
            "status": result.status.name,
            "source_file": str(self.config.source_file) if self.config and hasattr(self.config, 'source_file') else None,
            "input_va": va.to_hex(),
            "ipa": result.ipa.to_hex() if result.ipa else None,
            "output_pa": result.output_pa.to_hex() if result.output_pa else None,
            "total_memory_accesses": result.total_memory_accesses,
            "granule_kb": getattr(va, 'granule_kb', 4),
            "va_bits": getattr(va, 'va_bits', 48),
            "l0_index": va.l0_index,
            "l1_index": va.l1_index,
            "l2_index": va.l2_index,
            "l3_index": va.l3_index,
            "page_offset": va.page_offset,
            "events": events,
            "permissions": permissions,
            "fault": fault,
            "register_snapshots": result.register_snapshots,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def ensure_template_exists(output_dir: Path) -> Path:
        """
        Ensure the reusable HTML template exists in the output directory.
        
        Only copies the template if it doesn't already exist.
        
        Args:
            output_dir: Directory where template should be placed.
            
        Returns:
            Path to the template file.
        """
        import shutil
        from pathlib import Path
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        template_dest = output_dir / "ptw_visualizer.html"
        
        # Only copy if doesn't exist
        if not template_dest.exists():
            template_src = Path(__file__).parent / "templates" / "interactive.html"
            if template_src.exists():
                shutil.copy(template_src, template_dest)
            else:
                # Create minimal fallback
                with open(template_dest, "w", encoding="utf-8") as f:
                    f.write('''<!DOCTYPE html>
<html><head><title>PTW Visualizer</title></head>
<body>
<p>Template not found. Place interactive.html in templates/ directory.</p>
</body></html>''')
        
        return template_dest

    def save_interactive(self, result: WalkResult, output_dir: Path) -> tuple[Path, Path]:
        """
        Save JSON data and ensure template exists.
        
        This method now:
        - Only generates JSON data file for this scenario
        - Ensures the reusable template exists (copied once)
        
        Args:
            result: The walk result.
            output_dir: Directory to save files.
            
        Returns:
            Tuple of (template_path, json_path).
        """
        from pathlib import Path
        
        output_dir = Path(output_dir)
        
        # Ensure template exists (only copied once)
        template_path = self.ensure_template_exists(output_dir)
        
        # Export JSON data only
        scenario_name = self.get_scenario_name() or "walk_result"
        json_path = output_dir / f"{scenario_name}_data.json"
        self.export_json(result, json_path)
        
        return template_path, json_path

