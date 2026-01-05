"""
Stage 1 translation walker for ARM v9 architecture.

This module handles the VA → IPA translation (Stage 1).

The complexity of Stage 1 translation comes from the "recursive" nature:
- Each Stage 1 table is stored at an IPA address
- Before we can read a Stage 1 table entry, we must first translate
  that table's IPA address to PA using Stage 2 translation
- This means each Stage 1 level triggers a full Stage 2 walk

For a 4-level walk with 4KB granules:
- 4 Stage 1 levels
- Each S1 table address requires a 4-level S2 walk = 16 S2 reads
- Total for S1 table reads: 4 S1 + 16 S2 = 20 reads
- Plus 4 more S2 reads to translate the final IPA
- Grand total: 24 memory accesses maximum
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Callable

from ptw_viz.models.address import (
    VirtualAddress,
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
    AccessPermissions,
)
from ptw_viz.simulator.faults import (
    TranslationFault,
    PermissionFault,
    AccessType,
    FaultRecord,
    FaultType,
    check_permission,
)
from ptw_viz.simulator.stage2 import Stage2Walker, Stage2WalkEvent, Stage2WalkResult


@dataclass
class Stage1WalkEvent:
    """
    Record of a Stage 1 translation table read.

    Attributes:
        event_id: Sequential event identifier.
        level: Translation table level (0-3).
        table_base_ipa: IPA of the translation table.
        table_base_pa: PA of the translation table (after S2 translation).
        index: Index into the table (from VA bits).
        descriptor_address_pa: PA where descriptor was read.
        descriptor_value: Raw value of the descriptor.
        descriptor_type: Type of descriptor found.
        output_address: Next table IPA or final page IPA.
        s2_events: Stage 2 events for translating table address.
        description: Human-readable description.
    """

    event_id: int
    level: int
    table_base_ipa: int
    table_base_pa: int
    index: int
    descriptor_address_pa: int
    descriptor_value: int
    descriptor_type: DescriptorType
    output_address: int
    s2_events: List[Stage2WalkEvent] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": "T",
            "stage": 1,
            "level": self.level,
            "table_base_ipa": f"0x{self.table_base_ipa:016X}",
            "table_base_pa": f"0x{self.table_base_pa:016X}",
            "index": f"0x{self.index:03X}",
            "descriptor_address_pa": f"0x{self.descriptor_address_pa:016X}",
            "descriptor_value": f"0x{self.descriptor_value:016X}",
            "descriptor_type": self.descriptor_type.name,
            "output_address": f"0x{self.output_address:016X}",
            "s2_walk": [e.to_dict() for e in self.s2_events],
            "description": self.description,
        }


@dataclass
class Stage1WalkResult:
    """
    Result of a complete Stage 1 walk.

    Attributes:
        success: True if translation completed.
        input_va: The VA that was translated.
        output_ipa: The resulting IPA (if successful).
        events: List of S1 translation events (each with nested S2 events).
        fault: Fault record if translation failed.
        final_permissions: Combined permissions from all levels.
    """

    success: bool
    input_va: VirtualAddress
    output_ipa: Optional[IntermediatePhysicalAddress] = None
    events: List[Stage1WalkEvent] = field(default_factory=list)
    fault: Optional[FaultRecord] = None
    final_permissions: Optional[AccessPermissions] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        perm_dict = None
        if self.final_permissions:
            perm_dict = {
                "read_el0": self.final_permissions.read_el0,
                "write_el0": self.final_permissions.write_el0,
                "read_el1": self.final_permissions.read_el1,
                "write_el1": self.final_permissions.write_el1,
                "execute_el0": self.final_permissions.execute_el0,
                "execute_el1": self.final_permissions.execute_el1,
            }
        return {
            "success": self.success,
            "input_va": self.input_va.to_hex(),
            "output_ipa": self.output_ipa.to_hex() if self.output_ipa else None,
            "events": [e.to_dict() for e in self.events],
            "fault": self.fault.to_dict() if self.fault else None,
            "final_permissions": perm_dict,
        }


class Stage1Walker:
    """
    Stage 1 translation walker (VA → IPA).

    This walker traverses Stage 1 translation tables, calling the
    Stage 2 walker as needed to translate table addresses.

    Attributes:
        ttbr_base: Base IPA from TTBR0/TTBR1 (this is an IPA in EL1 context).
        starting_level: First level of the walk.
        stage2_walker: Stage 2 walker for table address translation.
        translation_tables: Simulated table data (PA → descriptor value).
        event_counter: Counter for generating event IDs.
    """

    def __init__(
        self,
        ttbr_base: int,
        stage2_walker: Stage2Walker,
        starting_level: int = 0,
        translation_tables: Optional[dict] = None
    ):
        """
        Initialize the Stage 1 walker.

        Args:
            ttbr_base: Base IPA of Stage 1 translation table.
            stage2_walker: Walker for Stage 2 translations.
            starting_level: Starting level (0-2).
            translation_tables: Simulated table data (PA → value).
        """
        self.ttbr_base = ttbr_base
        self.stage2_walker = stage2_walker
        self.starting_level = starting_level
        self.translation_tables = translation_tables or {}
        self.event_counter = 0

    def walk(
        self,
        va: VirtualAddress,
        access_type: AccessType = AccessType.READ,
        is_el0: bool = True
    ) -> Stage1WalkResult:
        """
        Perform a Stage 1 translation walk.

        For each level:
        1. Take the current table IPA
        2. Translate it to PA using Stage 2
        3. Read the descriptor from that PA
        4. Process the descriptor

        Args:
            va: The virtual address to translate.
            access_type: Type of access being performed.
            is_el0: True if access is from EL0 (unprivileged).

        Returns:
            Stage1WalkResult with translation outcome.
        """
        events: List[Stage1WalkEvent] = []
        current_table_ipa = self.ttbr_base

        # Track permission restrictions from table descriptors
        uxn_limit = False
        pxn_limit = False
        ap_limit = 0  # 0 = no limit

        for level in range(self.starting_level, 4):
            # Get index from VA for this level
            index = va.get_index(level)

            # First, translate the table IPA to PA using Stage 2
            table_ipa = IntermediatePhysicalAddress(current_table_ipa)
            s2_result = self.stage2_walker.walk(table_ipa, access_type)

            if not s2_result.success:
                # Stage 2 fault while translating table address
                self.event_counter += 1
                event = Stage1WalkEvent(
                    event_id=self.event_counter,
                    level=level,
                    table_base_ipa=current_table_ipa,
                    table_base_pa=0,
                    index=index,
                    descriptor_address_pa=0,
                    descriptor_value=0,
                    descriptor_type=DescriptorType.INVALID,
                    output_address=0,
                    s2_events=s2_result.events,
                    description=f"Stage 1 Level {level} - S2 FAULT translating table"
                )
                events.append(event)

                return Stage1WalkResult(
                    success=False,
                    input_va=va,
                    events=events,
                    fault=s2_result.fault
                )

            # Successfully translated table IPA to PA
            table_pa = s2_result.output_pa.value

            # Calculate descriptor PA
            descriptor_pa = calculate_descriptor_address(
                table_pa, index, descriptor_size=8
            )

            # Read descriptor from physical memory
            descriptor_value = self._read_descriptor(descriptor_pa)
            descriptor = create_descriptor(descriptor_value, level, is_stage2=False)

            # Create event record
            self.event_counter += 1
            event = Stage1WalkEvent(
                event_id=self.event_counter,
                level=level,
                table_base_ipa=current_table_ipa,
                table_base_pa=table_pa,
                index=index,
                descriptor_address_pa=descriptor_pa,
                descriptor_value=descriptor_value,
                descriptor_type=descriptor.descriptor_type,
                output_address=0,
                s2_events=s2_result.events,
                description=f"Stage 1 Level {level} lookup"
            )

            # Check for invalid descriptor
            if not descriptor.is_valid:
                event.description = f"Stage 1 Level {level} - INVALID DESCRIPTOR"
                events.append(event)

                return Stage1WalkResult(
                    success=False,
                    input_va=va,
                    events=events,
                    fault=FaultRecord(
                        fault_type=FaultType.TRANSLATION_FAULT,
                        stage=1,
                        level=level,
                        address=va.value,
                        message=f"Invalid descriptor at Stage 1 Level {level}",
                        far_el1=va.value
                    )
                )

            # Process based on descriptor type
            if descriptor.is_table:
                # Table descriptor - continue walk
                table_desc = TableDescriptor(value=descriptor_value, level=level)
                current_table_ipa = table_desc.next_table_address

                # Accumulate permission limits from table descriptor
                if table_desc.uxn_table:
                    uxn_limit = True
                if table_desc.pxn_table:
                    pxn_limit = True
                if table_desc.ap_table != 0:
                    ap_limit = max(ap_limit, table_desc.ap_table)

                event.output_address = current_table_ipa
                event.description = (
                    f"Stage 1 Level {level} - Table → IPA 0x{current_table_ipa:X}"
                )
                events.append(event)

            elif descriptor.is_page or descriptor.is_block:
                # Page/Block descriptor - final translation
                if descriptor.is_block:
                    data_desc = BlockDescriptor(value=descriptor_value, level=level)
                else:
                    data_desc = PageDescriptor(value=descriptor_value, level=level)
                    
                output_base = data_desc.output_address
                
                # Calculate final IPA based on block/page size
                if descriptor.level == 1:
                    final_ipa = output_base | va.l1_block_offset
                    desc_str = "Block (1GB)"
                elif descriptor.level == 2:
                    final_ipa = output_base | va.l2_block_offset
                    desc_str = "Block (2MB)"
                else:
                    final_ipa = output_base | va.page_offset
                    desc_str = "Page (4KB)"

                # Apply permission limits from table descriptors
                final_uxn = data_desc.uxn or uxn_limit
                final_pxn = data_desc.pxn or pxn_limit
                final_ap = data_desc.ap

                # Check permissions
                if not check_permission(
                    access_type, final_ap, final_uxn, final_pxn, is_el0
                ):
                    event.description = (
                        f"Stage 1 Level {level} - PERMISSION FAULT"
                    )
                    events.append(event)

                    return Stage1WalkResult(
                        success=False,
                        input_va=va,
                        events=events,
                        fault=FaultRecord(
                            fault_type=FaultType.PERMISSION_FAULT,
                            stage=1,
                            level=level,
                            address=va.value,
                            access_type=access_type,
                            message=(
                                f"{access_type.value} denied by AP={final_ap:02b}, "
                                f"UXN={final_uxn}, PXN={final_pxn}"
                            ),
                            far_el1=va.value
                        )
                    )

                event.output_address = output_base
                event.description = (
                    f"Stage 1 Level {level} - {desc_str} → IPA 0x{final_ipa:X}"
                )
                events.append(event)

                # Build final permissions
                final_permissions = AccessPermissions.from_ap_bits(
                    final_ap, final_uxn, final_pxn
                )

                return Stage1WalkResult(
                    success=True,
                    input_va=va,
                    output_ipa=IntermediatePhysicalAddress(final_ipa),
                    events=events,
                    final_permissions=final_permissions
                )

        # Should not reach here
        return Stage1WalkResult(
            success=False,
            input_va=va,
            events=events,
            fault=FaultRecord(
                fault_type=FaultType.TRANSLATION_FAULT,
                stage=1,
                level=3,
                address=va.value,
                message="Stage 1 walk completed without finding page descriptor"
            )
        )

    def _read_descriptor(self, address: int) -> int:
        """
        Read a descriptor from simulated memory.

        Args:
            address: Physical address of the descriptor.

        Returns:
            64-bit descriptor value.
        """
        return self.translation_tables.get(address, 0)

    def reset_event_counter(self) -> None:
        """Reset the event counter."""
        self.event_counter = 0

    def set_event_counter(self, value: int) -> None:
        """Set the event counter to a specific value."""
        self.event_counter = value
