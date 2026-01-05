"""
ARM v9 translation table descriptor models.

This module defines the descriptor types used in ARM v9 translation tables:

DESCRIPTOR TYPES:
-----------------
1. Invalid Descriptor: bit[0] = 0
   - Any descriptor with bit[0] = 0 causes a Translation Fault

2. Table Descriptor: bits[1:0] = 0b11 (at L0-L2 only)
   - Points to the next-level translation table
   - Contains attributes that limit permissions for subsequent levels

3. Block Descriptor: bits[1:0] = 0b01 (at L1-L2 only)
   - Maps a large contiguous block (1GB at L1, 2MB at L2)
   - Contains output address and memory attributes
   - Maps 1GB (L1), 2MB (L2), or other large blocks

4. Page Descriptor: bits[1:0] = 0b11 (at L3 only)
   - Maps a single 4KB page
   - Contains output address and memory attributes

DESCRIPTOR FORMAT (64-bit):
---------------------------
For Table Descriptors:
    [63:59] - Ignored
    [58:51] - Ignored for hardware, available for software use
    [50]    - Ignored
    [47:12] - Next-level table address (bits [47:12])
    [11:2]  - Ignored
    [1:0]   - 0b11 (identifies table descriptor)

For Page/Block Descriptors:
    [63]    - Ignored for hardware
    [54:53] - Reserved (FEAT_D128 expands this for larger addresses)
    [52]    - Reserved
    [51:50] - Reserved, PBHA if implemented
    [49:48] - Reserved
    [47:12] - Output address (page-aligned)
    [11]    - nG (not Global) - TLB scope
    [10]    - AF (Access Flag) - must be 1 for valid access
    [9:8]   - SH (Shareability) - memory sharing domain
    [7:6]   - AP (Access Permissions) - read/write control
    [5]     - NS (Non-Secure) - security state
    [4:2]   - AttrIndx - index into MAIR register
    [1:0]   - 0b11 for page, 0b01 for block

ACCESS PERMISSIONS (AP[7:6]):
-----------------------------
Stage 1 permissions (with EL0/EL1 distinction):
    AP[7:6] = 0b00: Read/Write at EL1, no access at EL0
    AP[7:6] = 0b01: Read/Write at EL1 and EL0
    AP[7:6] = 0b10: Read-only at EL1, no access at EL0
    AP[7:6] = 0b11: Read-only at EL1 and EL0

Stage 2 permissions (S2AP):
    S2AP[1:0] = 0b00: No access
    S2AP[1:0] = 0b01: Read-only
    S2AP[1:0] = 0b10: Write-only
    S2AP[1:0] = 0b11: Read/Write
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DescriptorType(Enum):
    """Types of translation table descriptors."""

    INVALID = auto()  # bit[0] = 0, causes Translation Fault
    TABLE = auto()    # bits[1:0] = 0b11 at L0-L2, points to next table
    BLOCK = auto()    # bits[1:0] = 0b01 at L1-L2, maps large block
    PAGE = auto()     # bits[1:0] = 0b11 at L3, maps 4KB page


class Shareability(Enum):
    """Memory shareability domain (SH bits)."""

    NON_SHAREABLE = 0b00       # Not shared
    OUTER_SHAREABLE = 0b10    # Shared with outer domain (e.g., other clusters)
    INNER_SHAREABLE = 0b11    # Shared within inner domain (e.g., same cluster)


class MemoryType(Enum):
    """Memory type (derived from AttrIndx and MAIR)."""

    DEVICE_nGnRnE = auto()  # Device, non-Gathering, non-Reordering, no Early ack
    DEVICE_nGnRE = auto()   # Device, non-Gathering, non-Reordering, Early ack
    DEVICE_nGRE = auto()    # Device, non-Gathering, Reordering, Early ack
    DEVICE_GRE = auto()     # Device, Gathering, Reordering, Early ack
    NORMAL_NC = auto()      # Normal, Non-Cacheable
    NORMAL_WT = auto()      # Normal, Write-Through
    NORMAL_WB = auto()      # Normal, Write-Back (most common)


@dataclass
class AccessPermissions:
    """
    Access permissions for a memory region.

    These are derived from the AP bits in the descriptor and may be
    further restricted by table descriptor attributes (APTable).

    Attributes:
        read_el0: Read access permitted at EL0 (user mode).
        write_el0: Write access permitted at EL0.
        read_el1: Read access permitted at EL1 (kernel mode).
        write_el1: Write access permitted at EL1.
        execute_el0: Instruction fetch permitted at EL0 (from UXN bit).
        execute_el1: Instruction fetch permitted at EL1 (from PXN bit).
    """

    read_el0: bool = False
    write_el0: bool = False
    read_el1: bool = True
    write_el1: bool = True
    execute_el0: bool = True
    execute_el1: bool = True

    @classmethod
    def from_ap_bits(
        cls,
        ap: int,
        uxn: bool = False,
        pxn: bool = False
    ) -> "AccessPermissions":
        """
        Create permissions from AP[7:6] bits and UXN/PXN flags.

        Args:
            ap: 2-bit AP value (0b00 to 0b11).
            uxn: Unprivileged Execute Never flag.
            pxn: Privileged Execute Never flag.

        Returns:
            AccessPermissions instance.
        """
        if ap == 0b00:  # EL1: RW, EL0: none
            return cls(
                read_el0=False, write_el0=False,
                read_el1=True, write_el1=True,
                execute_el0=not uxn, execute_el1=not pxn
            )
        elif ap == 0b01:  # EL1: RW, EL0: RW
            return cls(
                read_el0=True, write_el0=True,
                read_el1=True, write_el1=True,
                execute_el0=not uxn, execute_el1=not pxn
            )
        elif ap == 0b10:  # EL1: RO, EL0: none
            return cls(
                read_el0=False, write_el0=False,
                read_el1=True, write_el1=False,
                execute_el0=not uxn, execute_el1=not pxn
            )
        else:  # 0b11: EL1: RO, EL0: RO
            return cls(
                read_el0=True, write_el0=False,
                read_el1=True, write_el1=False,
                execute_el0=not uxn, execute_el1=not pxn
            )


@dataclass
class Stage2Permissions:
    """
    Stage 2 access permissions (S2AP).

    Stage 2 permissions are simpler than Stage 1, with just read and write
    flags that apply to all exception levels.

    Attributes:
        read: Read access permitted.
        write: Write access permitted.
        execute: Execute access permitted (from XN bit).
    """

    read: bool = True
    write: bool = True
    execute: bool = True

    @classmethod
    def from_s2ap_bits(cls, s2ap: int, xn: bool = False) -> "Stage2Permissions":
        """
        Create permissions from S2AP[1:0] bits.

        Args:
            s2ap: 2-bit S2AP value.
            xn: Execute Never flag.

        Returns:
            Stage2Permissions instance.
        """
        return cls(
            read=(s2ap & 0b01) != 0 or s2ap == 0b11,
            write=(s2ap & 0b10) != 0,
            execute=not xn
        )


@dataclass
class MemoryAttributes:
    """
    Complete memory attributes from a descriptor.

    These attributes define how memory should behave for caching,
    ordering, and access permissions.
    """

    shareability: Shareability = Shareability.INNER_SHAREABLE
    memory_type: MemoryType = MemoryType.NORMAL_WB
    attr_index: int = 0  # Index into MAIR register
    access_flag: bool = True
    not_global: bool = False
    non_secure: bool = False


@dataclass
class Descriptor:
    """
    Base class for translation table descriptors.

    This represents a single entry in a translation table. The type
    is determined by the low bits of the value.

    Attributes:
        value: The raw 64-bit (or 128-bit for FEAT_D128) descriptor value.
        level: The translation table level (0-3).
        is_stage2: Whether this is a Stage 2 descriptor.
    """

    value: int
    level: int = 0
    is_stage2: bool = False

    @property
    def is_valid(self) -> bool:
        """Check if descriptor is valid (bit[0] = 1)."""
        return (self.value & 0x1) == 1

    @property
    def is_table(self) -> bool:
        """Check if this is a table descriptor (bits[1:0] = 0b11, L0-L2)."""
        return self.level < 3 and (self.value & 0x3) == 0b11

    @property
    def is_block(self) -> bool:
        """Check if this is a block descriptor (bits[1:0] = 0b01, L1-L2)."""
        return self.level in (1, 2) and (self.value & 0x3) == 0b01

    @property
    def is_page(self) -> bool:
        """Check if this is a page descriptor (bits[1:0] = 0b11, L3)."""
        return self.level == 3 and (self.value & 0x3) == 0b11

    @property
    def descriptor_type(self) -> DescriptorType:
        """Determine the descriptor type."""
        if not self.is_valid:
            return DescriptorType.INVALID
        if self.is_table:
            return DescriptorType.TABLE
        if self.is_block:
            return DescriptorType.BLOCK
        if self.is_page:
            return DescriptorType.PAGE
        return DescriptorType.INVALID

    def to_hex(self) -> str:
        """Return the descriptor value as a hexadecimal string."""
        return f"0x{self.value:016X}"


@dataclass
class TableDescriptor(Descriptor):
    """
    A table descriptor that points to the next-level translation table.

    Table descriptors can only appear at levels 0, 1, and 2. They contain
    the base address of the next-level table and optional permission
    restrictions.
    """

    @property
    def next_table_address(self) -> int:
        """
        Extract the next-level table base address.

        The address is in bits [47:12] for standard descriptors.
        For FEAT_D128, additional bits may be used.
        """
        # Mask to extract bits [47:12]
        return self.value & 0x0000FFFFFFFFF000

    @property
    def ns_table(self) -> bool:
        """Non-Secure table (NSTable bit at [63])."""
        return bool((self.value >> 63) & 1)

    @property
    def ap_table(self) -> int:
        """Access permissions limit for subsequent levels (APTable[62:61])."""
        return (self.value >> 61) & 0x3

    @property
    def uxn_table(self) -> bool:
        """UXN limit for subsequent levels."""
        return bool((self.value >> 60) & 1)

    @property
    def pxn_table(self) -> bool:
        """PXN limit for subsequent levels."""
        return bool((self.value >> 59) & 1)


@dataclass
class PageDescriptor(Descriptor):
    """
    A page descriptor that maps a 4KB page.

    Page descriptors only appear at level 3. They contain the physical
    address of the page and its memory attributes.
    """

    @property
    def output_address(self) -> int:
        """
        Extract the output physical address (page-aligned).

        The address is in bits [47:12] for standard descriptors.
        """
        return self.value & 0x0000FFFFFFFFF000

    @property
    def not_global(self) -> bool:
        """nG bit - if set, TLB entry is not global."""
        return bool((self.value >> 11) & 1)

    @property
    def access_flag(self) -> bool:
        """AF bit - must be 1 for valid access."""
        return bool((self.value >> 10) & 1)

    @property
    def shareability(self) -> Shareability:
        """SH[9:8] bits - memory shareability."""
        sh = (self.value >> 8) & 0x3
        return Shareability(sh)

    @property
    def ap(self) -> int:
        """AP[7:6] bits - access permissions."""
        return (self.value >> 6) & 0x3

    @property
    def non_secure(self) -> bool:
        """NS bit - non-secure memory."""
        return bool((self.value >> 5) & 1)

    @property
    def attr_index(self) -> int:
        """AttrIndx[4:2] - index into MAIR register."""
        return (self.value >> 2) & 0x7

    @property
    def uxn(self) -> bool:
        """UXN bit - Unprivileged Execute Never (bit 54)."""
        return bool((self.value >> 54) & 1)

    @property
    def pxn(self) -> bool:
        """PXN bit - Privileged Execute Never (bit 53)."""
        return bool((self.value >> 53) & 1)

    def get_permissions(self) -> AccessPermissions:
        """Get the access permissions for this page."""
        return AccessPermissions.from_ap_bits(self.ap, self.uxn, self.pxn)

    def get_attributes(self) -> MemoryAttributes:
        """Get complete memory attributes for this page."""
        return MemoryAttributes(
            shareability=self.shareability,
            attr_index=self.attr_index,
            access_flag=self.access_flag,
            not_global=self.not_global,
            non_secure=self.non_secure
        )


@dataclass
class BlockDescriptor(Descriptor):
    """
    A block descriptor that maps a large memory block (1GB or 2MB).

    Block descriptors appear at levels 1 (1GB) and 2 (2MB). They contain
    the output address and memory attributes.
    """

    @property
    def output_address(self) -> int:
        """
        Extract the output physical address (block-aligned).
        
        For L1: bits [47:30] are used.
        For L2: bits [47:21] are used.
        """
        if self.level == 1:
            # 1GB block - bits [29:0] must be ignored/zero
            return self.value & 0x0000FFFFC0000000
        elif self.level == 2:
            # 2MB block - bits [20:0] must be ignored/zero
            return self.value & 0x0000FFFFFFE00000
        return self.value & 0x0000FFFFFFFFF000

    @property
    def not_global(self) -> bool:
        """nG bit."""
        return bool((self.value >> 11) & 1)

    @property
    def access_flag(self) -> bool:
        """AF bit."""
        return bool((self.value >> 10) & 1)

    @property
    def shareability(self) -> Shareability:
        """SH[9:8] bits."""
        sh = (self.value >> 8) & 0x3
        return Shareability(sh)

    @property
    def ap(self) -> int:
        """AP[7:6] bits."""
        return (self.value >> 6) & 0x3

    @property
    def non_secure(self) -> bool:
        """NS bit."""
        return bool((self.value >> 5) & 1)

    @property
    def attr_index(self) -> int:
        """AttrIndx[4:2]."""
        return (self.value >> 2) & 0x7

    @property
    def uxn(self) -> bool:
        """UXN bit (bit 54)."""
        return bool((self.value >> 54) & 1)

    @property
    def pxn(self) -> bool:
        """PXN bit (bit 53)."""
        return bool((self.value >> 53) & 1)

    def get_permissions(self) -> AccessPermissions:
        """Get the access permissions for this block."""
        return AccessPermissions.from_ap_bits(self.ap, self.uxn, self.pxn)

    def get_attributes(self) -> MemoryAttributes:
        """Get complete memory attributes for this block."""
        return MemoryAttributes(
            shareability=self.shareability,
            attr_index=self.attr_index,
            access_flag=self.access_flag,
            not_global=self.not_global,
            non_secure=self.non_secure
        )


def create_descriptor(value: int, level: int, is_stage2: bool = False) -> Descriptor:
    """
    Factory function to create the appropriate descriptor type.

    This is a Factory pattern implementation that determines the correct
    descriptor class based on the value and level.

    Args:
        value: The raw descriptor value.
        level: Translation table level (0-3).
        is_stage2: Whether this is a Stage 2 descriptor.

    Returns:
        The appropriate Descriptor subclass instance.
    """
    base = Descriptor(value=value, level=level, is_stage2=is_stage2)

    if not base.is_valid:
        return base  # Invalid descriptor
    elif base.is_table:
        return TableDescriptor(value=value, level=level, is_stage2=is_stage2)
    elif base.is_page:
        return PageDescriptor(value=value, level=level, is_stage2=is_stage2)
    elif base.is_block:
        return BlockDescriptor(value=value, level=level, is_stage2=is_stage2)
    else:
        return base


def build_table_descriptor(next_table_address: int) -> int:
    """
    Build a table descriptor value from a next-level table address.

    This creates a valid table descriptor with bits[1:0] = 0b11.

    Args:
        next_table_address: Base address of next-level table (must be aligned).

    Returns:
        64-bit descriptor value.
    """
    # Ensure address is page-aligned
    aligned_addr = next_table_address & 0x0000FFFFFFFFF000
    # Set valid bit and table bits
    return aligned_addr | 0x3


def build_page_descriptor(
    output_address: int,
    ap: int = 0b01,
    uxn: bool = False,
    pxn: bool = False,
    af: bool = True,
    sh: Shareability = Shareability.INNER_SHAREABLE,
    attr_index: int = 0
) -> int:
    """
    Build a page descriptor value from components.

    Args:
        output_address: Physical address of the page (must be aligned).
        ap: Access permissions (0b00-0b11).
        uxn: Unprivileged Execute Never.
        pxn: Privileged Execute Never.
        af: Access Flag (should be True for valid access).
        sh: Shareability.
        attr_index: MAIR index (0-7).

    Returns:
        64-bit descriptor value.
    """
    aligned_addr = output_address & 0x0000FFFFFFFFF000
    value = aligned_addr
    value |= (1 if uxn else 0) << 54
    value |= (1 if pxn else 0) << 53
    value |= (1 if af else 0) << 10
    value |= sh.value << 8
    value |= (ap & 0x3) << 6
    value |= (attr_index & 0x7) << 2
    value |= 0x3  # Valid page descriptor
    return value
