"""Data models for ARM v9 page table walk components."""

from ptw_viz.models.address import (
    VirtualAddress,
    IntermediatePhysicalAddress,
    PhysicalAddress,
)
from ptw_viz.models.descriptor import (
    DescriptorType,
    Descriptor,
    TableDescriptor,
    PageDescriptor,
    BlockDescriptor,
)
from ptw_viz.models.registers import (
    TTBR,
    TCR,
    VTCR,
)
from ptw_viz.models.granule import (
    GranuleType,
    GranuleConfig,
    get_granule_config,
    GRANULE_4KB_CONFIG,
    GRANULE_16KB_CONFIG,
    GRANULE_64KB_CONFIG,
)

__all__ = [
    "VirtualAddress",
    "IntermediatePhysicalAddress",
    "PhysicalAddress",
    "DescriptorType",
    "Descriptor",
    "TableDescriptor",
    "PageDescriptor",
    "BlockDescriptor",
    "TTBR",
    "TCR",
    "VTCR",
    "GranuleType",
    "GranuleConfig",
    "get_granule_config",
    "GRANULE_4KB_CONFIG",
    "GRANULE_16KB_CONFIG",
    "GRANULE_64KB_CONFIG",
]
