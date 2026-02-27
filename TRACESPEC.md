# PTW Trace Format Specification (v1.0)

This document defines the formal contract for the Page Table Walk (PTW) trace format. Any tool that generates output following this specification can be visualized using the `ptw-viz` tool.

## Format Overview

The trace is a JSON object that captures the chronological events of an ARM v9 2-stage page table walk. It includes input parameters, configuration snapshots, a list of walk events, and the final result (success or fault).

## JSON Schema

The formal specification is available as a JSON Schema:
[trace_schema.json](ptw-sim/src/ptw_sim/io/trace_schema.json)

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format_version` | String | Yes | Must be `"1.0"`. |
| `generator` | String | No | Name of the tool that generated the trace. |
| `scenario_name` | String | No | Identifier for the simulation scenario. |
| `timestamp` | String | No | ISO 8601 timestamp. |
| `input` | Object | Yes | Parameters of the access being translated. |
| `configuration` | Object | No | Architecture and Register settings. |
| `result` | Object | Yes | Final outcome (PA, IPA, status). |
| `walk_trace` | Object | Yes | List of events and register snapshots. |
| `fault` | Object | No | Details if a translation fault occurred. |
| `final_permissions` | Object | No | Combined S1/S2 permissions. |

## Walk Events (`walk_trace.events`)

Each event in the `events` array represents a single memory access or key step in the translation.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Integer | Unique sequential ID starting from 1. |
| `event_type` | String | `"T"` (Translation Table Read) or `"M"` (Memory Access). |
| `stage` | Integer | `1` or `2`. |
| `level` | Integer | `0` to `3`. |
| `purpose` | String | Human-readable explanation (e.g., "S1 L0 lookup"). |
| `address` | String | Hex address of the descriptor being read. |
| `descriptor_value` | String | Raw 64/128-bit hex value found at `address`. |
| `result` | String | Interpretation: `"TABLE"`, `"PAGE"`, `"BLOCK"`, `"INVALID"`. |
| `output` | String | Hex address of the next table or the final output. |

## Address Representation

All addresses and descriptor values MUST be represented as hexadecimal strings with the `0x` prefix (e.g., `"0x0000000012345678"`).

## Usage for Third-Party Tools

To make your custom simulator compatible with `ptw-viz`:

1.  Export your results in the format described above.
2.  Ensure `format_version` is set to `"1.0"`.
3.  Save the JSON to a file (e.g., `my_trace.json`).
4.  Run the visualizer:
    ```bash
    ptw-viz my_trace.json
    ```

## Validation

You can validate your generated traces against the schema using standard JSON Schema validation tools (e.g., `jsonschema` in Python).
