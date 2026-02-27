"""Tests for dynamic granule size support in translation walks."""

import pytest
from ptw_sim.core.faults import AccessType
from ptw_sim.core.walker import PageTableWalker
from ptw_sim.models.address import VirtualAddress
from ptw_sim.models.registers import RegisterState
from ptw_sim.io.parser import parse_scenario, build_register_state, build_translation_tables, get_virtual_address

import json
from pathlib import Path


def _create_temp_scenario(tmp_path: Path, tcr_tg0: int, vtcr_tg0: int) -> Path:
    """Create a temporary scenario with specific TG0 settings."""
    scenario = {
        "scenario_name": f"test_s1_tg{tcr_tg0}_s2_tg{vtcr_tg0}",
        "architecture": {
            "granule_size_kb": tcr_tg0,
            "va_bits": 48,
            "pa_bits": 52,
            "ipa_bits": 48
        },
        "registers": {
            "TTBR0_EL1": "0x0000000000010000",
            "TTBR1_EL1": "0x0000000080000000",
            "VTTBR_EL2": "0x0000000000080000",
            "TCR_EL1": {
                "T0SZ": 16,
                "T1SZ": 16,
                "TG0": tcr_tg0,
                "TG1": tcr_tg0
            },
            "VTCR_EL2": {
                "T0SZ": 16,
                "SL0": 0 if vtcr_tg0 == 4 else 1,
                "TG0": vtcr_tg0
            }
        },
        "memory_access": {
            "virtual_address": "0x0",
            "access_type": "READ",
            "privilege_level": "EL0"
        },
        "translation_tables": {
            "stage1": {},
            "stage2": {}
        }
    }
    
    # Simple direct mapping tables to prevent bounds faults
    # Stage 1 mapping 0x1000 to IPA 0x2000
    if tcr_tg0 == 4:
        # 4 levels mapping 0x1ABC
        scenario["translation_tables"]["stage1"] = {
            "0x0000000000040000": "0x0000000000011003", # L0
            "0x0000000000041000": "0x0000000000012003", # L1
            "0x0000000000042000": "0x0000000000013003", # L2
            "0x0000000000043010": "0x0000000000002443"  # L3 -> IPA 0x2000 (Index 1)
        }
    elif tcr_tg0 == 16:
        # TTBR0_EL1 is set to 0x10000 in config.
        scenario["registers"]["TTBR0_EL1"] = "0x10000"
        scenario["memory_access"]["virtual_address"] = "0x0"
        
        scenario["translation_tables"]["stage1"] = {
            "0x40000": "0x20003", # L0 (at PA 0x40000) -> L1 at IPA 0x20000
            "0x60000": "0x30003", # L1 (at PA 0x60000) -> L2 at IPA 0x30000
            "0x50000": "0x40003", # L2 (at PA 0x50000) -> L3 at IPA 0x40000
            "0x70000": "0x00443"  # L3 (at PA 0x70000) -> outputs final IPA 0x0
        }

    if vtcr_tg0 == 64:
        # VTTBR is 0x80000 -> points to L1.
        scenario["registers"]["VTTBR_EL2"] = "0x80000"
        scenario["translation_tables"]["stage2"] = {
            "0x80000": "0x81003", # L1[0] -> L2 table at PA 0x81000
            "0x81000": "0x82003", # L2[0] -> L3 table at PA 0x82000

            # L3 table at PA 0x82000
            "0x82008": "0x40443", # IPA 0x10000 (Index 1) -> PA 0x40000 (L0 table)
            "0x82010": "0x60443", # IPA 0x20000 (Index 2) -> PA 0x60000 (L1 table)
            "0x82018": "0x50443", # IPA 0x30000 (Index 3) -> PA 0x50000 (L2 table)
            "0x82020": "0x70443", # IPA 0x40000 (Index 4) -> PA 0x70000 (L3 table)
            "0x82000": "0x00443"  # IPA 0x0 (Final Translation) -> PA 0x0
        }

    filepath = tmp_path / "scenario.json"
    filepath.write_text(json.dumps(scenario))
    return filepath


def test_different_granule_sizes(tmp_path):
    """Test that VA and IPA offsets correctly reflect different Stage 1 and Stage 2 granules."""
    # S1 uses 16KB, S2 uses 64KB
    filepath = _create_temp_scenario(tmp_path, 16, 64)
    config = parse_scenario(filepath)
    
    register_state = build_register_state(config)
    s1_tables, s2_tables = build_translation_tables(config)
    
    walker = PageTableWalker(
        register_state=register_state,
        s1_tables=s1_tables,
        s2_tables=s2_tables
    )
    
    # Verify the configured granule sizes made it into the register state
    assert register_state.tcr_el1.tg0.value == 16 * 1024
    assert register_state.vtcr_el2.tg0.value == 64 * 1024
    
    # Virtual address uses S1 granule (16KB)
    va = get_virtual_address(config)
    assert va.granule_kb == 16
    assert va.page_offset == 0x000  # Updated the VA to 0
    assert va._config.offset_bits == 14
    
    # Perform translation walk
    result = walker.walk(va, AccessType.READ, is_el0=True)

    if not result.status.name == "SUCCESS":
        print(f"FAILED WALK: {result.status.name}")
        if result.fault:
            print(f"Fault details: {result.fault}")
        print(f"Walk events:")
        for evt in result.events:
            print(evt)
        pytest.fail(f"Walk failed: {result.status.name}")

    # 0x0 is just the offset, so IPA=0x0, final PA should reflect this.
    
    # Extracted IPA offset should use the **Stage 2 granule size (64KB, 16 bit offset)**
    assert result.ipa.granule_kb == 64
    assert result.ipa._config.offset_bits == 16
    assert result.ipa.page_offset == 0x0
    
    # Same with the PA
    assert result.output_pa.granule_kb == 64
    assert result.output_pa._config.offset_bits == 16
    assert result.output_pa.page_offset == 0x0
