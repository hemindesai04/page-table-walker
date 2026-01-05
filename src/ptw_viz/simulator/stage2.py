"""
Stage 2 translation walker for ARM v9 architecture.

This module handles the IPA → PA translation (Stage 2).

Stage 2 translation is simpler than Stage 1 because:
1. It translates IPA to PA (no further nested translation)
2. The Stage 2 tables themselves are in physical address space
3. Each table read is a direct memory access

The Stage 2 walk uses VTTBR_EL2 as the base and VTCR_EL2 for configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ptw_viz.models.address import (
    IntermediatePhysicalAddress,
    PhysicalAddress,
    calculate_descriptor_address,
)
from ptw_viz.models.descriptor import (
    Descriptor,
    TableDescriptor,
    PageDescriptor,
    BlockDescriptor,
    DescriptorType,
    create_descriptor,
)
from ptw_viz.simulator.faults import (
    TranslationFault,
    PermissionFault,
    AccessType,
    FaultRecord,
    FaultType,
)


@dataclass
class Stage2WalkEvent:
    """
    Record of a single Stage 2 translation table read.

    These are the "T-events" for Stage 2 (translation read events).

    Attributes:
        event_id: Sequential event identifier.
        level: Translation table level (0-3).
        table_base_pa: Physical address of the translation table.
        index: Index into the table (from IPA bits).
        descriptor_address: Physical address of the descriptor.
        descriptor_value: Raw value read from the descriptor.
        descriptor_type: Type of descriptor found.
        output_address: Next table PA or final page PA.
        description: Human-readable event description.
    """

    event_id: int
    level: int
    table_base_pa: int
    index: int
    descriptor_address: int
    descriptor_value: int
    descriptor_type: DescriptorType
    output_address: int
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": "T",
            "stage": 2,
            "level": self.level,
            "table_base_pa": f"0x{self.table_base_pa:016X}",
            "index": f"0x{self.index:03X}",
            "descriptor_address": f"0x{self.descriptor_address:016X}",
            "descriptor_value": f"0x{self.descriptor_value:016X}",
            "descriptor_type": self.descriptor_type.name,
            "output_address": f"0x{self.output_address:016X}",
            "description": self.description,
        }


@dataclass
class Stage2WalkResult:
    """
    Result of a complete Stage 2 walk.

    Attributes:
        success: True if translation completed successfully.
        input_ipa: The IPA that was translated.
        output_pa: The resulting PA (if successful).
        events: List of translation table reads.
        fault: Fault record if translation failed.
    """

    success: bool
    input_ipa: IntermediatePhysicalAddress
    output_pa: Optional[PhysicalAddress] = None
    events: List[Stage2WalkEvent] = field(default_factory=list)
    fault: Optional[FaultRecord] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "input_ipa": self.input_ipa.to_hex(),
            "output_pa": self.output_pa.to_hex() if self.output_pa else None,
            "events": [e.to_dict() for e in self.events],
            "fault": self.fault.to_dict() if self.fault else None,
        }


class Stage2Walker:
    """
    Stage 2 translation walker (IPA → PA).

    This class performs the actual Stage 2 translation by walking
    through the translation tables pointed to by VTTBR_EL2.

    The walk reads translation tables from physical memory (since
    Stage 2 tables are in PA space) and produces the final PA.

    Attributes:
        vttbr_base: Base physical address from VTTBR_EL2.
        starting_level: First level of the walk (from VTCR.SL0).
        translation_tables: Dictionary mapping PA → descriptor value.
        event_counter: Counter for generating event IDs.
    """

    def __init__(
        self,
        vttbr_base: int,
        starting_level: int = 0,
        translation_tables: Optional[dict] = None
    ):
        """
        Initialize the Stage 2 walker.

        Args:
            vttbr_base: Base PA of Stage 2 translation table.
            starting_level: Starting level (0-2).
            translation_tables: Pre-populated table data for simulation.
        """
        self.vttbr_base = vttbr_base
        self.starting_level = starting_level
        self.translation_tables = translation_tables or {}
        self.event_counter = 0

    def walk(
        self,
        ipa: IntermediatePhysicalAddress,
        access_type: AccessType = AccessType.READ,
        parent_event_id: Optional[int] = None
    ) -> Stage2WalkResult:
        """
        Perform a Stage 2 translation walk.

        Args:
            ipa: The IPA to translate.
            access_type: Type of access being performed.
            parent_event_id: Event ID from Stage 1 (for linking).

        Returns:
            Stage2WalkResult with translation outcome.
        """
        events: List[Stage2WalkEvent] = []
        current_table_pa = self.vttbr_base

        for level in range(self.starting_level, 4):
            # Get index from IPA for this level
            index = ipa.get_index(level)

            # Calculate descriptor address (8 bytes per descriptor)
            descriptor_addr = calculate_descriptor_address(
                current_table_pa, index, descriptor_size=8
            )

            # Read descriptor from our simulated memory
            descriptor_value = self._read_descriptor(descriptor_addr)

            # Create descriptor object
            descriptor = create_descriptor(descriptor_value, level, is_stage2=True)

            # Create event record
            self.event_counter += 1
            event = Stage2WalkEvent(
                event_id=self.event_counter,
                level=level,
                table_base_pa=current_table_pa,
                index=index,
                descriptor_address=descriptor_addr,
                descriptor_value=descriptor_value,
                descriptor_type=descriptor.descriptor_type,
                output_address=0,  # Will be filled based on type
                description=f"Stage 2 Level {level} lookup"
            )

            # Check for invalid descriptor (Translation Fault)
            if not descriptor.is_valid:
                event.description = f"Stage 2 Level {level} - INVALID DESCRIPTOR"
                events.append(event)

                fault = FaultRecord(
                    fault_type=FaultType.TRANSLATION_FAULT,
                    stage=2,
                    level=level,
                    address=ipa.value,
                    message=f"Invalid descriptor at Stage 2 Level {level}",
                    far_el2=ipa.value
                )

                return Stage2WalkResult(
                    success=False,
                    input_ipa=ipa,
                    events=events,
                    fault=fault
                )

            # Process based on descriptor type
            if descriptor.is_table:
                # Table descriptor - continue walk
                table_desc = TableDescriptor(
                    value=descriptor_value, level=level, is_stage2=True
                )
                current_table_pa = table_desc.next_table_address
                event.output_address = current_table_pa
                event.description = f"Stage 2 Level {level} - Table → 0x{current_table_pa:X}"
                events.append(event)

            elif descriptor.is_page or descriptor.is_block:
                # Page/Block descriptor - final translation
                if descriptor.is_block:
                    data_desc = BlockDescriptor(value=descriptor_value, level=level, is_stage2=True)
                else:
                    data_desc = PageDescriptor(value=descriptor_value, level=level, is_stage2=True)
                    
                output_base = data_desc.output_address
                
                # Calculate final PA based on block/page size
                if descriptor.level == 1:
                    final_pa = output_base | ipa.l1_block_offset
                    desc_str = "Block (1GB)"
                elif descriptor.level == 2:
                    final_pa = output_base | ipa.l2_block_offset
                    desc_str = "Block (2MB)"
                else:
                    final_pa = output_base | ipa.page_offset
                    desc_str = "Page (4KB)"

                event.output_address = output_base
                event.description = f"Stage 2 Level {level} - {desc_str} → PA 0x{final_pa:X}"
                events.append(event)

                return Stage2WalkResult(
                    success=True,
                    input_ipa=ipa,
                    output_pa=PhysicalAddress(final_pa),
                    events=events
                )

        # Should not reach here with valid tables
        return Stage2WalkResult(
            success=False,
            input_ipa=ipa,
            events=events,
            fault=FaultRecord(
                fault_type=FaultType.TRANSLATION_FAULT,
                stage=2,
                level=3,
                address=ipa.value,
                message="Stage 2 walk completed without finding page descriptor"
            )
        )

    def _read_descriptor(self, address: int) -> int:
        """
        Read a descriptor from simulated memory.

        In a real system, this would be a memory read. Here we look up
        the value in our pre-populated translation tables.

        Args:
            address: Physical address of the descriptor.

        Returns:
            64-bit descriptor value (0 if not found = invalid).
        """
        return self.translation_tables.get(address, 0)

    def reset_event_counter(self) -> None:
        """Reset the event counter for a new walk."""
        self.event_counter = 0

    def set_event_counter(self, value: int) -> None:
        """Set the event counter to a specific value."""
        self.event_counter = value
