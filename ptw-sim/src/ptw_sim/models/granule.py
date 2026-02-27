"""
Granule size configuration for ARM v9 page table walks.

This module defines the configuration for different translation granule sizes:
- 4KB granule (most common, 9-bit indices per level)
- 16KB granule (11-bit indices per level)
- 64KB granule (13-bit indices per level)

GRANULE SIZE COMPARISON:
========================

| Granule | Page Size | Index Bits | Entries/Table | Offset Bits |
|---------|-----------|------------|---------------|-------------|
| 4KB     | 4KB       | 9          | 512           | 12          |
| 16KB    | 16KB      | 11         | 2048          | 14          |
| 64KB    | 64KB      | 13         | 8192          | 16          |

VA BIT SLICING (48-bit VA):
===========================

4KB Granule:
    [47:39] L0 (9 bits) → [38:30] L1 (9 bits) → [29:21] L2 (9 bits) → [20:12] L3 (9 bits) → [11:0] offset

16KB Granule:
    [47] L0 (1 bit) → [46:36] L1 (11 bits) → [35:25] L2 (11 bits) → [24:14] L3 (11 bits) → [13:0] offset

64KB Granule:
    [47:42] L1 (6 bits) → [41:29] L2 (13 bits) → [28:16] L3 (13 bits) → [15:0] offset
    (Note: 64KB skips L0 for 48-bit VA)

BLOCK SIZES PER GRANULE:
========================

| Granule | L1 Block | L2 Block | L3 Page |
|---------|----------|----------|---------|
| 4KB     | 1GB      | 2MB      | 4KB     |
| 16KB    | N/A      | 32MB     | 16KB    |
| 64KB    | N/A      | 512MB    | 64KB    |
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class GranuleType(Enum):
    """Translation granule types."""
    
    GRANULE_4KB = 4
    GRANULE_16KB = 16
    GRANULE_64KB = 64


@dataclass(frozen=True)
class GranuleConfig:
    """
    Configuration for a specific granule size.
    
    Attributes:
        granule_type: The granule type enum.
        page_size: Page size in bytes.
        offset_bits: Number of bits for page offset.
        index_bits: Number of bits per table index.
        entries_per_table: Number of entries in each translation table.
        level_shifts: Tuple of bit positions for each level's index start.
        block_offsets: Dict mapping level to block offset mask.
        min_level: Minimum (first) level for this granule with 48-bit VA.
    """
    
    granule_type: GranuleType
    page_size: int
    offset_bits: int
    index_bits: int
    entries_per_table: int
    level_shifts: Tuple[int, int, int, int]  # L0, L1, L2, L3 start bits
    block_offsets: Dict[int, int]  # Level -> offset mask for blocks
    min_level: int  # Starting level for 48-bit VA


# Pre-defined configurations for each granule size
GRANULE_4KB_CONFIG = GranuleConfig(
    granule_type=GranuleType.GRANULE_4KB,
    page_size=4096,
    offset_bits=12,
    index_bits=9,
    entries_per_table=512,
    level_shifts=(39, 30, 21, 12),  # L0 at [47:39], L1 at [38:30], etc.
    block_offsets={
        1: 0x3FFFFFFF,  # 1GB block: bits [29:0]
        2: 0x1FFFFF,    # 2MB block: bits [20:0]
    },
    min_level=0
)

GRANULE_16KB_CONFIG = GranuleConfig(
    granule_type=GranuleType.GRANULE_16KB,
    page_size=16384,
    offset_bits=14,
    index_bits=11,
    entries_per_table=2048,
    level_shifts=(47, 36, 25, 14),  # L0 at [47], L1 at [46:36], etc.
    block_offsets={
        2: 0x1FFFFFF,  # 32MB block: bits [24:0]
    },
    min_level=0
)

GRANULE_64KB_CONFIG = GranuleConfig(
    granule_type=GranuleType.GRANULE_64KB,
    page_size=65536,
    offset_bits=16,
    index_bits=13,
    entries_per_table=8192,
    level_shifts=(0, 42, 29, 16),  # No L0, L1 at [47:42], L2 at [41:29], L3 at [28:16]
    block_offsets={
        2: 0x1FFFFFFF,  # 512MB block: bits [28:0]
    },
    min_level=1  # 64KB starts at L1 for 48-bit VA
)


def get_granule_config(granule_kb: int) -> GranuleConfig:
    """
    Get the granule configuration for a given size.
    
    Args:
        granule_kb: Granule size in KB (4, 16, or 64).
        
    Returns:
        GranuleConfig for the specified size.
        
    Raises:
        ValueError: If granule size is not supported.
    """
    if granule_kb == 4:
        return GRANULE_4KB_CONFIG
    elif granule_kb == 16:
        return GRANULE_16KB_CONFIG
    elif granule_kb == 64:
        return GRANULE_64KB_CONFIG
    else:
        raise ValueError(f"Unsupported granule size: {granule_kb}KB. Must be 4, 16, or 64.")


def get_index_mask(index_bits: int) -> int:
    """Get the mask for extracting an index of the given bit width."""
    return (1 << index_bits) - 1


def get_offset_mask(offset_bits: int) -> int:
    """Get the mask for extracting the page offset."""
    return (1 << offset_bits) - 1


def calculate_index(address: int, level: int, config: GranuleConfig) -> int:
    """
    Calculate the table index for an address at a given level.
    
    Args:
        address: The address value.
        level: Translation table level (0-3).
        config: Granule configuration.
        
    Returns:
        The index value for this level.
    """
    if level < config.min_level or level > 3:
        return 0
    
    shift = config.level_shifts[level]
    mask = get_index_mask(config.index_bits)
    
    # Special case for 16KB L0 which only has 1 bit
    if config.granule_type == GranuleType.GRANULE_16KB and level == 0:
        return (address >> shift) & 0x1
    
    return (address >> shift) & mask


def calculate_page_offset(address: int, config: GranuleConfig) -> int:
    """Calculate the page offset for an address."""
    return address & get_offset_mask(config.offset_bits)


def calculate_block_offset(address: int, level: int, config: GranuleConfig) -> int:
    """
    Calculate the block offset for an address at a given level.
    
    Args:
        address: The address value.
        level: The level where the block descriptor was found.
        config: Granule configuration.
        
    Returns:
        The block offset to be ORed with the output address.
    """
    if level in config.block_offsets:
        return address & config.block_offsets[level]
    # Fall back to page offset if no block at this level
    return calculate_page_offset(address, config)
