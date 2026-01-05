"""
Input parser for scenario configuration files.

This module parses JSON configuration files that define:
- Architecture parameters (granule size, VA/PA bits)
- Register state (TTBR, TCR values)
- Translation tables for simulation
- Memory access to perform

INPUT FORMAT DOCUMENTATION:
===========================

The input JSON file has the following structure:

{
    "scenario_name": "string",     // Identifier for this scenario
    "description": "string",       // Human-readable description

    "architecture": {              // ARM architecture configuration
        "granule_size_kb": 4,      // Translation granule: 4, 16, or 64 KB
        "va_bits": 48,             // Virtual address size (typically 48)
        "pa_bits": 56,             // Physical address size (up to 56 with D128)
        "ipa_bits": 48,            // Intermediate physical address size
        "feat_d128_enabled": true  // Enable 128-bit descriptor support
    },

    "registers": {                 // System register values
        "TTBR0_EL1": "0x...",      // Stage 1 table base (lower VA range)
        "TTBR1_EL1": "0x...",      // Stage 1 table base (upper VA range)
        "VTTBR_EL2": "0x...",      // Stage 2 table base
        "TCR_EL1": {               // Translation control register
            "T0SZ": 16,            // Size offset for TTBR0 (VA bits = 64 - T0SZ)
            "T1SZ": 16             // Size offset for TTBR1
        },
        "VTCR_EL2": {              // Virtualization translation control
            "T0SZ": 16,            // Size offset for IPA space
            "SL0": 0               // Starting level for S2 walk
        }
    },

    "memory_access": {             // The access to simulate
        "virtual_address": "0x...",// VA to translate
        "access_type": "READ",     // READ, WRITE, or EXECUTE
        "privilege_level": "EL0"   // EL0 (user) or EL1 (kernel)
    },

    "translation_tables": {        // Pre-populated table data
        "stage1": {                // Stage 1 tables (at PA addresses)
            "0x...": {             // PA of descriptor
                "value": "0x...",  // Descriptor value
                "type": "table",   // table, page, or invalid
                "comment": "..."   // Optional description
            }
        },
        "stage2": {                // Stage 2 tables (at PA addresses)
            "0x...": {             // PA of descriptor
                "value": "0x...",
                "type": "page"
            }
        }
    }
}

FIELD EXPLANATIONS:
===================

granule_size_kb:
    The page size used for translation. 4KB is most common.
    Affects how VA bits are sliced into table indices.

T0SZ / T1SZ:
    Size offset values. The number of VA bits = 64 - TxSZ.
    T0SZ=16 means 48-bit VA for lower address range.
    T0SZ=25 means 39-bit VA (3-level walk starting at L1).

SL0 (Starting Level):
    Which level to start the Stage 2 walk at.
    0 = start at L0 (4 levels), 1 = start at L1 (3 levels), etc.

access_type:
    READ  - Load instruction (LDR)
    WRITE - Store instruction (STR)
    EXECUTE - Instruction fetch

privilege_level:
    EL0 - User/unprivileged mode
    EL1 - Kernel/privileged mode
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from ptw_viz.models.address import VirtualAddress
from ptw_viz.models.registers import (
    RegisterState,
    TTBR,
    TCR,
    VTCR,
    GranuleSize,
    PhysicalAddressSize,
)
from ptw_viz.simulator.faults import AccessType


class ArchitectureConfig(BaseModel):
    """Architecture configuration from input file."""

    granule_size_kb: int = Field(default=4, description="Granule size in KB")
    va_bits: int = Field(default=48, description="Virtual address bits")
    pa_bits: int = Field(default=56, description="Physical address bits")
    ipa_bits: int = Field(default=48, description="IPA bits")
    feat_d128_enabled: bool = Field(default=True, description="FEAT_D128 enabled")

    @field_validator("granule_size_kb")
    @classmethod
    def validate_granule(cls, v: int) -> int:
        """Validate granule size is valid."""
        if v not in (4, 16, 64):
            raise ValueError(f"Invalid granule size: {v}KB. Must be 4, 16, or 64.")
        return v


class TCRConfig(BaseModel):
    """TCR_EL1 configuration."""

    T0SZ: int = Field(default=16, ge=0, le=39)
    T1SZ: int = Field(default=16, ge=0, le=39)


class VTCRConfig(BaseModel):
    """VTCR_EL2 configuration."""

    T0SZ: int = Field(default=16, ge=0, le=39)
    SL0: int = Field(default=0, ge=0, le=2)


class RegisterConfig(BaseModel):
    """Register configuration from input file."""

    TTBR0_EL1: str = Field(default="0x0000000040000000")
    TTBR1_EL1: str = Field(default="0x0000000080000000")
    VTTBR_EL2: str = Field(default="0x0000000100000000")
    TCR_EL1: TCRConfig = Field(default_factory=TCRConfig)
    VTCR_EL2: VTCRConfig = Field(default_factory=VTCRConfig)


class MemoryAccessConfig(BaseModel):
    """Memory access configuration."""

    virtual_address: str = Field(description="VA to translate in hex")
    access_type: str = Field(default="READ", description="READ/WRITE/EXECUTE")
    privilege_level: str = Field(default="EL0", description="EL0/EL1")

    @field_validator("access_type")
    @classmethod
    def validate_access_type(cls, v: str) -> str:
        """Validate access type."""
        v = v.upper()
        if v not in ("READ", "WRITE", "EXECUTE"):
            raise ValueError(f"Invalid access type: {v}")
        return v

    @field_validator("privilege_level")
    @classmethod
    def validate_privilege(cls, v: str) -> str:
        """Validate privilege level."""
        v = v.upper()
        if v not in ("EL0", "EL1"):
            raise ValueError(f"Invalid privilege level: {v}")
        return v


class ScenarioConfig(BaseModel):
    """Complete scenario configuration."""

    scenario_name: str = Field(default="unnamed")
    description: str = Field(default="")
    architecture: ArchitectureConfig = Field(default_factory=ArchitectureConfig)
    registers: RegisterConfig = Field(default_factory=RegisterConfig)
    memory_access: MemoryAccessConfig
    translation_tables: Dict[str, Any] = Field(default_factory=dict)
    source_file: Optional[str] = Field(default=None, description="Path to source JSON file")


def parse_hex(value: str) -> int:
    """Parse a hex string to integer."""
    if isinstance(value, int):
        return value
    value = value.strip()
    if value.startswith("0x") or value.startswith("0X"):
        return int(value, 16)
    return int(value)


def parse_scenario(file_path: str | Path) -> ScenarioConfig:
    """
    Parse a scenario configuration file.

    Args:
        file_path: Path to JSON configuration file.

    Returns:
        Parsed ScenarioConfig object.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If configuration is invalid.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path, "r") as f:
        data = json.load(f)

    config = ScenarioConfig.model_validate(data)
    config.source_file = str(path)
    return config


def build_register_state(config: ScenarioConfig) -> RegisterState:
    """
    Build RegisterState from configuration.

    Args:
        config: Parsed scenario configuration.

    Returns:
        RegisterState object.
    """
    return RegisterState(
        ttbr0_el1=TTBR(
            value=parse_hex(config.registers.TTBR0_EL1),
            name="TTBR0_EL1"
        ),
        ttbr1_el1=TTBR(
            value=parse_hex(config.registers.TTBR1_EL1),
            name="TTBR1_EL1"
        ),
        vttbr_el2=TTBR(
            value=parse_hex(config.registers.VTTBR_EL2),
            name="VTTBR_EL2"
        ),
        tcr_el1=TCR(
            t0sz=config.registers.TCR_EL1.T0SZ,
            t1sz=config.registers.TCR_EL1.T1SZ,
        ),
        vtcr_el2=VTCR(
            t0sz=config.registers.VTCR_EL2.T0SZ,
            sl0=config.registers.VTCR_EL2.SL0,
        )
    )


def build_translation_tables(
    config: ScenarioConfig
) -> tuple[Dict[int, int], Dict[int, int]]:
    """
    Build translation table dictionaries from configuration.

    The configuration maps addresses to descriptor info. We extract
    the actual descriptor values into PA → value dictionaries.

    Args:
        config: Parsed scenario configuration.

    Returns:
        Tuple of (stage1_tables, stage2_tables).
    """
    s1_tables: Dict[int, int] = {}
    s2_tables: Dict[int, int] = {}

    tables = config.translation_tables

    # Parse Stage 1 tables
    if "stage1" in tables:
        for addr, desc_info in tables["stage1"].items():
            pa = parse_hex(addr)
            if isinstance(desc_info, dict):
                value = parse_hex(desc_info.get("value", "0"))
            else:
                value = parse_hex(desc_info)
            s1_tables[pa] = value

    # Parse Stage 2 tables
    if "stage2" in tables:
        for addr, desc_info in tables["stage2"].items():
            pa = parse_hex(addr)
            if isinstance(desc_info, dict):
                value = parse_hex(desc_info.get("value", "0"))
            else:
                value = parse_hex(desc_info)
            s2_tables[pa] = value

    return s1_tables, s2_tables


def get_access_type(config: ScenarioConfig) -> AccessType:
    """Get AccessType enum from configuration."""
    access_str = config.memory_access.access_type.upper()
    return AccessType[access_str]


def get_virtual_address(config: ScenarioConfig) -> VirtualAddress:
    """Get VirtualAddress from configuration."""
    va_value = parse_hex(config.memory_access.virtual_address)
    va_bits = config.architecture.va_bits
    granule_kb = config.architecture.granule_size_kb
    return VirtualAddress(value=va_value, va_bits=va_bits, granule_kb=granule_kb)


def is_el0_access(config: ScenarioConfig) -> bool:
    """Check if access is from EL0."""
    return config.memory_access.privilege_level.upper() == "EL0"
