"""
ARM v9 translation control register models.

This module defines the system registers used to configure and control
address translation in ARM v9 architecture.

TRANSLATION TABLE BASE REGISTERS (TTBR):
-----------------------------------------
TTBR0_EL1: Base register for lower VA range (user space)
TTBR1_EL1: Base register for upper VA range (kernel space)
VTTBR_EL2: Stage 2 base register (hypervisor controlled)

Each TTBR contains:
    [63:48] - ASID (Address Space IDentifier) for TLB tagging
    [47:1]  - BADDR (Base ADDRess) of the translation table
    [0]     - CnP (Common not Private) for shared TLB

TRANSLATION CONTROL REGISTER (TCR):
-----------------------------------
TCR_EL1 controls Stage 1 translation parameters:
    T0SZ: Size offset for TTBR0 region (bits addressable = 64 - T0SZ)
    T1SZ: Size offset for TTBR1 region
    TG0:  Granule size for TTBR0 (4KB/16KB/64KB)
    TG1:  Granule size for TTBR1
    IPS:  Physical address size

VIRTUALIZATION TRANSLATION CONTROL (VTCR_EL2):
----------------------------------------------
Controls Stage 2 translation:
    T0SZ: Size offset for IPA space
    SL0:  Starting level of Stage 2 walk
    PS:   Physical address size
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GranuleSize(Enum):
    """Translation granule (page) sizes."""

    GRANULE_4KB = 4096
    GRANULE_16KB = 16384
    GRANULE_64KB = 65536


class PhysicalAddressSize(Enum):
    """
    Encoded physical address size values (IPS/PS field).

    The IPS (Intermediate Physical address Size) or PS field encodes
    the maximum PA size the system supports.
    """

    PA_32_BITS = 0b000  # 4GB
    PA_36_BITS = 0b001  # 64GB
    PA_40_BITS = 0b010  # 1TB
    PA_42_BITS = 0b011  # 4TB
    PA_44_BITS = 0b100  # 16TB
    PA_48_BITS = 0b101  # 256TB
    PA_52_BITS = 0b110  # 4PB (FEAT_LPA)
    PA_56_BITS = 0b111  # 64PB (FEAT_D128)

    def to_bits(self) -> int:
        """Convert to actual number of address bits."""
        mapping = {
            0b000: 32, 0b001: 36, 0b010: 40, 0b011: 42,
            0b100: 44, 0b101: 48, 0b110: 52, 0b111: 56
        }
        return mapping.get(self.value, 48)


@dataclass
class TTBR:
    """
    Translation Table Base Register model.

    Represents TTBR0_EL1, TTBR1_EL1, or VTTBR_EL2.

    Attributes:
        value: Raw 64-bit register value.
        name: Register name (for display purposes).
    """

    value: int
    name: str = "TTBR"

    @property
    def asid(self) -> int:
        """
        Address Space IDentifier (bits [63:48]).

        The ASID is used by the TLB to distinguish between different
        process address spaces, avoiding TLB flushes on context switch.
        """
        return (self.value >> 48) & 0xFFFF

    @property
    def baddr(self) -> int:
        """
        Base address of translation table (bits [47:1]).

        This is the physical address of the level 0 translation table.
        The table must be aligned to its size.
        """
        # For Stage 1, this is a physical address
        # For Stage 2 (VTTBR), this is also a physical address
        return self.value & 0x0000FFFFFFFFFFFE

    @property
    def cnp(self) -> bool:
        """
        Common not Private bit (bit [0]).

        When set, this TTBR points to a translation table that is
        shared across multiple PEs (processors).
        """
        return bool(self.value & 1)

    def to_hex(self) -> str:
        """Return the register value as a hexadecimal string."""
        return f"0x{self.value:016X}"

    def __str__(self) -> str:
        return (
            f"{self.name}="
            f"{self.to_hex()} "
            f"(ASID={self.asid:#06x}, BADDR={self.baddr:#018x})"
        )


@dataclass
class TCR:
    """
    Translation Control Register (TCR_EL1).

    Controls Stage 1 translation parameters for EL0/EL1.

    Attributes:
        t0sz: Size offset for TTBR0 region.
              VA range = 2^(64-T0SZ), e.g., T0SZ=16 means 48-bit VA.
        t1sz: Size offset for TTBR1 region.
        tg0: Granule size for TTBR0 (0=4KB, 1=64KB, 2=16KB).
        tg1: Granule size for TTBR1 (1=16KB, 2=4KB, 3=64KB).
        ips: Intermediate (physical) address size.
    """

    t0sz: int = 16  # Default: 48-bit VA for lower range
    t1sz: int = 16  # Default: 48-bit VA for upper range
    tg0: GranuleSize = GranuleSize.GRANULE_4KB
    tg1: GranuleSize = GranuleSize.GRANULE_4KB
    ips: PhysicalAddressSize = PhysicalAddressSize.PA_48_BITS

    @property
    def va_bits_t0(self) -> int:
        """Number of VA bits for TTBR0 region."""
        return 64 - self.t0sz

    @property
    def va_bits_t1(self) -> int:
        """Number of VA bits for TTBR1 region."""
        return 64 - self.t1sz

    @property
    def pa_bits(self) -> int:
        """Number of PA bits supported."""
        return self.ips.to_bits()

    def starting_level(self, for_ttbr1: bool = False) -> int:
        """
        Determine the starting level of the translation table walk.

        The starting level depends on the VA size and granule size.
        For 48-bit VA with 4KB granule: starts at L0.
        For smaller VA ranges, may start at L1 or L2.

        Args:
            for_ttbr1: If True, calculate for TTBR1 region.

        Returns:
            Starting level (0, 1, or 2).
        """
        va_bits = self.va_bits_t1 if for_ttbr1 else self.va_bits_t0

        # For 4KB granule:
        # 48-bit VA: L0 covers bits [47:39] (9 bits), L1 [38:30], etc.
        # 39-bit VA: Skip L0, start at L1
        # 30-bit VA: Skip L0 and L1, start at L2
        if va_bits >= 40:
            return 0  # Full 4-level walk
        elif va_bits >= 31:
            return 1  # 3-level walk
        else:
            return 2  # 2-level walk

    def __str__(self) -> str:
        return (
            f"TCR_EL1(T0SZ={self.t0sz}, T1SZ={self.t1sz}, "
            f"TG0={self.tg0.name}, TG1={self.tg1.name}, "
            f"IPS={self.ips.name})"
        )


@dataclass
class VTCR:
    """
    Virtualization Translation Control Register (VTCR_EL2).

    Controls Stage 2 translation parameters.

    Attributes:
        t0sz: Size offset for IPA space.
              IPA range = 2^(64-T0SZ).
        sl0: Starting level of Stage 2 walk.
        ps: Physical address size.
    """

    t0sz: int = 16  # Default: 48-bit IPA
    sl0: int = 0    # Default: Start at Level 0
    ps: PhysicalAddressSize = PhysicalAddressSize.PA_48_BITS

    @property
    def ipa_bits(self) -> int:
        """Number of IPA bits."""
        return 64 - self.t0sz

    @property
    def pa_bits(self) -> int:
        """Number of PA bits supported."""
        return self.ps.to_bits()

    @property
    def starting_level(self) -> int:
        """Starting level of Stage 2 walk."""
        return self.sl0

    def __str__(self) -> str:
        return (
            f"VTCR_EL2(T0SZ={self.t0sz}, SL0={self.sl0}, "
            f"PS={self.ps.name})"
        )


@dataclass
class RegisterState:
    """
    Complete register state for a page table walk.

    This aggregates all relevant registers needed to perform
    2-stage address translation.
    """

    ttbr0_el1: TTBR
    ttbr1_el1: TTBR
    vttbr_el2: TTBR
    tcr_el1: TCR
    vtcr_el2: VTCR

    @classmethod
    def default(cls) -> "RegisterState":
        """Create a default register state for testing."""
        return cls(
            ttbr0_el1=TTBR(value=0x0000000040000000, name="TTBR0_EL1"),
            ttbr1_el1=TTBR(value=0x0000000080000000, name="TTBR1_EL1"),
            vttbr_el2=TTBR(value=0x0000000100000000, name="VTTBR_EL2"),
            tcr_el1=TCR(),
            vtcr_el2=VTCR()
        )

    def get_stage1_table_base(self, uses_ttbr1: bool) -> int:
        """Get the Stage 1 table base address from appropriate TTBR."""
        ttbr = self.ttbr1_el1 if uses_ttbr1 else self.ttbr0_el1
        return ttbr.baddr

    def get_stage2_table_base(self) -> int:
        """Get the Stage 2 table base address from VTTBR."""
        return self.vttbr_el2.baddr
