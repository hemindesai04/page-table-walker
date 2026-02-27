"""
Scenario Generator for ptw-sim.

Automatically computes all Stage 1 and Stage 2 translation table entries
for a given VA → PA mapping, and outputs a complete scenario JSON file.

Usage:
    ptw-gen --va 0x12345678 --pa 0x87654000
    ptw-gen --va 0xABC --pa 0x200ABC --fault translation --fault-stage 1 --fault-level 2
    ptw-gen --va 0xABC --pa 0x200ABC --fault permission -o examples/perm_fault.json

The generator handles the tedious part of scenario crafting:
  1. Assigns IPA addresses for S1 tables
  2. Assigns PA addresses for S2 tables and S1 table backing
  3. Computes all descriptor values with correct bit encoding
  4. Builds the full S2 chain for every IPA that needs translation
  5. Optionally injects faults by invalidating descriptors or setting RO permissions
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Descriptor encoding helpers (4KB granule, 64-bit descriptors)
# ---------------------------------------------------------------------------

AF_BIT = 1 << 10          # Access Flag (bit 10)
AP_RW_ALL = 0b01 << 6     # AP=01: RW at EL1/EL0
AP_RO_ALL = 0b11 << 6     # AP=11: RO at EL1/EL0

# Index bit positions per level for each granule size
_INDEX_SHIFTS = {
    4:  {0: 39, 1: 30, 2: 21, 3: 12},
    16: {0: 47, 1: 36, 2: 25, 3: 14},
    64: {1: 42, 2: 29, 3: 16},
}
_INDEX_MASKS = {4: 0x1FF, 16: 0x7FF, 64: 0x1FFF}
_OFFSET_MASKS = {4: 0xFFF, 16: 0x3FFF, 64: 0xFFFF}


def _idx(addr: int, level: int, granule_kb: int = 4) -> int:
    """Extract the table index for a given level from an address."""
    if level not in _INDEX_SHIFTS[granule_kb]:
        return 0
    return (addr >> _INDEX_SHIFTS[granule_kb][level]) & _INDEX_MASKS[granule_kb]


def _table_desc(next_table_addr: int) -> int:
    """Table descriptor: bits[47:12] (or up to 51) = address, bits[1:0] = 0b11."""
    return (next_table_addr & 0x000F_FFFF_FFFF_F000) | 0x3


def _page_desc(output_addr: int, ap: int = AP_RW_ALL) -> int:
    """L3 page descriptor: output address + AF + AP + valid+page bits."""
    return (output_addr & 0x000F_FFFF_FFFF_F000) | AF_BIT | ap | 0x3


# ---------------------------------------------------------------------------
# Scenario Generator
# ---------------------------------------------------------------------------

class ScenarioGenerator:
    """
    Generates a complete ptw-sim scenario JSON from a high-level mapping spec.

    Address layout (PA space):
        0x0008_0000 region — S2 table hierarchy (VTTBR and sub-tables)
        0x0004_0000 region — Physical backing for S1 tables
        user-specified      — Target PA for the final mapping

    IPA space:
        0x0001_0000 region — S1 table IPAs (chosen by the generator)
        0x0010_0000         — Final output IPA from Stage 1
    """

    def __init__(
        self,
        va: int,
        pa: int,
        granule_kb: int = 4,
        s2_granule_kb: Optional[int] = None,
        va_bits: int = 48,
        pa_bits: int = 52,
        ipa_bits: int = 48,
        access_type: str = "READ",
        privilege: str = "EL0",
        permissions: str = "RW",
        fault_type: Optional[str] = None,
        fault_stage: int = 1,
        fault_level: int = 2,
        scenario_name: Optional[str] = None,
    ):
        self.va = va
        self.pa = pa
        self.granule_kb = granule_kb
        self.granule_size = granule_kb * 1024
        self.s2_granule_kb = s2_granule_kb if s2_granule_kb is not None else granule_kb
        self.s2_granule_size = self.s2_granule_kb * 1024
        self.va_bits = va_bits
        self.pa_bits = pa_bits
        self.ipa_bits = ipa_bits
        self.access_type = access_type
        self.privilege = privilege
        self.permissions = permissions
        self.fault_type = fault_type
        self.fault_stage = fault_stage
        self.fault_level = fault_level
        self.scenario_name = scenario_name or self._auto_name()

        # Will be populated during generate()
        self.s1_table_ipas: Dict[int, int] = {}   # level → IPA
        self.s1_table_pas: Dict[int, int] = {}    # level → backing PA
        self.final_ipa = 0
        self.ttbr0 = 0
        self.vttbr = 0x0008_0000
        self.s1_entries: Dict[int, Tuple[int, str]] = {}  # PA → (value, comment)
        self.s2_entries: Dict[int, Tuple[int, str]] = {}  # PA → (value, comment)

    def _auto_name(self) -> str:
        parts = [f"gen_va_{self.va:x}_pa_{self.pa:x}"]
        if self.fault_type:
            parts.append(f"{self.fault_type}_s{self.fault_stage}_l{self.fault_level}")
        return "_".join(parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> dict:
        """Generate the complete scenario dictionary."""
        self._assign_addresses()
        self._build_s1_chain()
        self._build_s2_chains()
        if self.fault_type:
            self._inject_fault()
        return self._to_dict()

    # ------------------------------------------------------------------
    # Address assignment
    # ------------------------------------------------------------------

    def _assign_addresses(self):
        # Stagger IPAs by max granule size so Stage 2 pages don't overlap
        gs = max(self.granule_size, self.s2_granule_size)
        for level in range(4):
            self.s1_table_ipas[level] = 0x0001_0000 + level * gs
            self.s1_table_pas[level]  = 0x0004_0000 + level * gs
        self.final_ipa = 0x0010_0000
        self.ttbr0 = self.s1_table_ipas[0]

    # ------------------------------------------------------------------
    # Stage 1 chain
    # ------------------------------------------------------------------

    def _build_s1_chain(self):
        g = self.granule_kb
        ap = AP_RW_ALL if self.permissions == "RW" else AP_RO_ALL

        # L0 → L1 → L2: table descriptors
        for level in range(3):
            idx = _idx(self.va, level, g)
            desc_pa = self.s1_table_pas[level] + idx * 8
            next_ipa = self.s1_table_ipas[level + 1]
            self.s1_entries[desc_pa] = (
                _table_desc(next_ipa),
                f"S1 L{level}[{idx:#x}] → L{level+1} table at IPA {next_ipa:#x}",
            )

        # L3: page descriptor
        idx = _idx(self.va, 3, g)
        desc_pa = self.s1_table_pas[3] + idx * 8
        self.s1_entries[desc_pa] = (
            _page_desc(self.final_ipa, ap),
            f"S1 L3[{idx:#x}] → Page at IPA {self.final_ipa:#x}"
            f", AP={'RW' if self.permissions == 'RW' else 'RO'}",
        )

    # ------------------------------------------------------------------
    # Stage 2 chains (for every IPA that needs translation)
    # ------------------------------------------------------------------

    def _build_s2_chains(self):
        g, gs = self.s2_granule_kb, self.s2_granule_size
        target_page_pa = self.pa & ~(gs - 1)

        # All IPAs we must provide S2 mappings for
        ipa_map: List[Tuple[int, int, str]] = [
            (self.s1_table_ipas[l], self.s1_table_pas[l], f"S1 L{l} table")
            for l in range(4)
        ]
        ipa_map.append((self.final_ipa, target_page_pa, "final IPA"))

        # Track allocated sub-tables to share common paths
        l1_tables: Dict[int, int] = {}              # l0_idx → PA
        l2_tables: Dict[Tuple[int,int], int] = {}   # (l0,l1) → PA
        l3_tables: Dict[Tuple[int,int,int], int] = {}
        next_pa = self.vttbr + gs  # first free PA after L0 table

        for ipa, backing_pa, label in ipa_map:
            i0 = _idx(ipa, 0, g)
            i1 = _idx(ipa, 1, g)
            i2 = _idx(ipa, 2, g)
            i3 = _idx(ipa, 3, g)

            # L0 → L1
            if i0 not in l1_tables:
                l1_tables[i0] = next_pa; next_pa += gs
                self.s2_entries[self.vttbr + i0 * 8] = (
                    _table_desc(l1_tables[i0]),
                    f"S2 L0[{i0:#x}] → L1 table at PA {l1_tables[i0]:#x}",
                )
            # L1 → L2
            k2 = (i0, i1)
            if k2 not in l2_tables:
                l2_tables[k2] = next_pa; next_pa += gs
                self.s2_entries[l1_tables[i0] + i1 * 8] = (
                    _table_desc(l2_tables[k2]),
                    f"S2 L1[{i1:#x}] → L2 table at PA {l2_tables[k2]:#x}",
                )
            # L2 → L3
            k3 = (i0, i1, i2)
            if k3 not in l3_tables:
                l3_tables[k3] = next_pa; next_pa += gs
                self.s2_entries[l2_tables[k2] + i2 * 8] = (
                    _table_desc(l3_tables[k3]),
                    f"S2 L2[{i2:#x}] → L3 table at PA {l3_tables[k3]:#x}",
                )
            # L3 page entry
            self.s2_entries[l3_tables[k3] + i3 * 8] = (
                _page_desc(backing_pa),
                f"S2 L3[{i3:#x}] → PA {backing_pa:#x} for IPA {ipa:#x} ({label})",
            )

        # Save table maps for fault injection
        self._s2_l1 = l1_tables
        self._s2_l2 = l2_tables
        self._s2_l3 = l3_tables

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------

    def _inject_fault(self):
        if self.fault_type == "translation":
            self._inject_translation_fault()
        elif self.fault_type == "permission":
            self._inject_permission_fault()
        elif self.fault_type == "address_size":
            self._inject_address_size_fault()
        elif self.fault_type == "access_flag":
            self._inject_access_flag_fault()

    def _inject_translation_fault(self):
        """Invalidate a descriptor at the specified stage/level."""
        stage, level = self.fault_stage, self.fault_level

        if stage == 1:
            g = self.granule_kb
            idx = _idx(self.va, level, g)
            pa = self.s1_table_pas[level] + idx * 8
            if pa in self.s1_entries:
                old = self.s1_entries[pa][1]
                self.s1_entries[pa] = (0x0, f"FAULT INJECTED (was: {old})")
        else:
            g = self.s2_granule_kb
            # Invalidate the S2 descriptor at the given level for the
            # TTBR0 IPA translation (the first S2 walk the hardware does).
            ipa = self.ttbr0
            i0, i1, i2, i3 = [_idx(ipa, l, g) for l in range(4)]
            target_pa = None
            if level == 0:
                target_pa = self.vttbr + i0 * 8
            elif level == 1 and i0 in self._s2_l1:
                target_pa = self._s2_l1[i0] + i1 * 8
            elif level == 2 and (i0, i1) in self._s2_l2:
                target_pa = self._s2_l2[(i0, i1)] + i2 * 8
            elif level == 3 and (i0, i1, i2) in self._s2_l3:
                target_pa = self._s2_l3[(i0, i1, i2)] + i3 * 8
            if target_pa and target_pa in self.s2_entries:
                old = self.s2_entries[target_pa][1]
                self.s2_entries[target_pa] = (0x0, f"FAULT INJECTED (was: {old})")

    def _inject_permission_fault(self):
        """Set final S1 page descriptor to RO and force WRITE access."""
        idx = _idx(self.va, 3, self.granule_kb)
        pa = self.s1_table_pas[3] + idx * 8
        if pa in self.s1_entries:
            self.s1_entries[pa] = (
                _page_desc(self.final_ipa, AP_RO_ALL),
                f"S1 L3[{idx:#x}] → Page at IPA {self.final_ipa:#x}, AP=RO "
                f"(PERMISSION FAULT: write attempted)",
            )
        self.access_type = "WRITE"

    def _inject_address_size_fault(self):
        """Set an output address that exceeds the configured IPA bits to fault at Stage 1."""
        idx = _idx(self.va, 3, self.granule_kb)
        pa = self.s1_table_pas[3] + idx * 8
        if pa in self.s1_entries:
            # Set a bit just outside the configured IPA size (e.g. bit 48 if ipa_bits=48), bounded to 51
            fault_bit = min(self.ipa_bits, 51)
            bad_ipa = self.final_ipa | (1 << fault_bit)
            self.s1_entries[pa] = (
                _page_desc(bad_ipa, AP_RW_ALL),
                f"S1 L3[{idx:#x}] → Page at IPA {bad_ipa:#x} "
                f"(ADDRESS SIZE FAULT: requires {fault_bit + 1} bits > {self.ipa_bits})",
            )

    def _inject_access_flag_fault(self):
        """Clear the Access Flag (AF) bit in the final page descriptor."""
        idx = _idx(self.va, 3, self.granule_kb)
        pa = self.s1_table_pas[3] + idx * 8
        if pa in self.s1_entries:
            val = _page_desc(self.final_ipa, AP_RW_ALL) & ~AF_BIT
            self.s1_entries[pa] = (
                val,
                f"S1 L3[{idx:#x}] → Page at IPA {self.final_ipa:#x}, AF=0 "
                f"(ACCESS FLAG FAULT: AF bit clear)",
            )

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------

    def _to_dict(self) -> dict:
        def _hex(v: int) -> str:
            return f"0x{v:016X}"

        stage1 = {
            _hex(pa): {"value": _hex(val), "comment": cmt}
            for pa, (val, cmt) in sorted(self.s1_entries.items())
        }
        stage2 = {
            _hex(pa): {"value": _hex(val), "comment": cmt}
            for pa, (val, cmt) in sorted(self.s2_entries.items())
        }

        desc_parts = [f"VA {self.va:#x} → PA {self.pa:#x}"]
        if self.fault_type == "translation":
            desc_parts.append(
                f"translation fault at S{self.fault_stage} L{self.fault_level}"
            )
        elif self.fault_type == "permission":
            desc_parts.append("permission fault (RO page + WRITE access)")
        elif self.fault_type == "address_size":
            desc_parts.append(f"address size fault (> {self.ipa_bits} bits)")
        elif self.fault_type == "access_flag":
            desc_parts.append("access flag fault (AF=0)")

        return {
            "scenario_name": self.scenario_name,
            "description": ", ".join(desc_parts),
            "architecture": {
                "granule_size_kb": self.granule_kb,
                "va_bits": self.va_bits,
                "pa_bits": self.pa_bits,
                "ipa_bits": self.ipa_bits,
            },
            "registers": {
                "TTBR0_EL1": _hex(self.ttbr0),
                "TTBR1_EL1": _hex(0x0000_0000_8000_0000),
                "VTTBR_EL2": _hex(self.vttbr),
                "TCR_EL1":  {"T0SZ": 64 - self.va_bits, "T1SZ": 64 - self.va_bits, "TG0": self.granule_kb, "TG1": self.granule_kb},
                "VTCR_EL2": {"T0SZ": 64 - self.ipa_bits, "SL0": 0, "TG0": self.s2_granule_kb},
            },
            "memory_access": {
                "virtual_address": _hex(self.va),
                "access_type": self.access_type,
                "privilege_level": self.privilege,
            },
            "translation_tables": {"stage1": stage1, "stage2": stage2},
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_hex(value: str) -> int:
    """Parse a hex string, accepting with or without 0x prefix."""
    return int(value, 16) if value.startswith("0x") or value.startswith("0X") else int(value, 0)


def main() -> int:
    """CLI entry point for ptw-gen."""
    p = argparse.ArgumentParser(
        prog="ptw-gen",
        description="Generate ptw-sim scenario JSON from a high-level VA → PA mapping.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --va 0xABC --pa 0x200ABC
  %(prog)s --va 0x12345678 --pa 0x87654678 -o examples/my_scenario.json
  %(prog)s --va 0xABC --pa 0x200ABC --fault translation --fault-stage 1 --fault-level 2
  %(prog)s --va 0xABC --pa 0x200ABC --fault permission
        """,
    )

    p.add_argument("--va", required=True, help="Virtual address (hex)")
    p.add_argument("--pa", required=True, help="Target physical address (hex)")
    p.add_argument("--name", help="Scenario name (auto-generated if omitted)")
    p.add_argument("--granule", type=int, default=4, choices=[4, 16, 64],
                   help="Granule size in KB (default: 4)")
    p.add_argument("--s2-granule", type=int, choices=[4, 16, 64],
                   help="Stage 2 Granule size in KB (defaults to Stage 1 granule)")
    p.add_argument("--va-bits", type=int, default=48, help="VA bits (default: 48)")
    p.add_argument("--access", default="READ", choices=["READ", "WRITE", "EXECUTE"])
    p.add_argument("--privilege", default="EL0", choices=["EL0", "EL1"])
    p.add_argument("--permissions", default="RW", choices=["RW", "RO"])
    p.add_argument("--fault", default=None, choices=["translation", "permission", "address_size", "access_flag"],
                   help="Inject a fault into the scenario")
    p.add_argument("--fault-stage", type=int, default=1, choices=[1, 2],
                   help="Stage for translation fault (default: 1)")
    p.add_argument("--fault-level", type=int, default=2, choices=[0, 1, 2, 3],
                   help="Level for translation fault (default: 2)")
    p.add_argument("-o", "--output", type=Path, help="Output JSON file path")

    args = p.parse_args()

    gen = ScenarioGenerator(
        va=_parse_hex(args.va),
        pa=_parse_hex(args.pa),
        granule_kb=args.granule,
        s2_granule_kb=args.s2_granule,
        va_bits=args.va_bits,
        access_type=args.access,
        privilege=args.privilege,
        permissions=args.permissions,
        fault_type=args.fault,
        fault_stage=args.fault_stage,
        fault_level=args.fault_level,
        scenario_name=args.name,
    )

    scenario = gen.generate()
    output_json = json.dumps(scenario, indent=4)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n")
        print(f"Scenario written to: {args.output}")
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
