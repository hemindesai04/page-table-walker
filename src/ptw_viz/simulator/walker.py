"""
Main page table walker - Facade for 2-stage translation.

This module provides the high-level interface for simulating ARM v9
2-stage page table walks. It orchestrates Stage 1 and Stage 2 walkers
and produces a complete walk trace.

WALK PROCESS:
-------------
1. Stage 1 translates VA → IPA
   - Each S1 table address requires S2 translation
   - Maximum 4 S1 reads, each triggering 4 S2 reads = 20 reads
2. Stage 2 translates final IPA → PA
   - 4 more S2 reads
3. Total: up to 24 memory accesses

CACHING NOTE:
-------------
In real hardware, Translation Lookaside Buffers (TLBs) cache translations,
dramatically reducing the number of memory accesses. This simulator shows
the worst-case scenario with no TLB hits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from ptw_viz.models.address import (
    VirtualAddress,
    IntermediatePhysicalAddress,
    PhysicalAddress,
)
from ptw_viz.models.descriptor import AccessPermissions, MemoryAttributes
from ptw_viz.models.registers import RegisterState, TTBR, TCR, VTCR
from ptw_viz.simulator.stage1 import Stage1Walker, Stage1WalkResult
from ptw_viz.simulator.stage2 import Stage2Walker, Stage2WalkResult, Stage2WalkEvent
from ptw_viz.simulator.faults import (
    AccessType,
    FaultRecord,
    FaultType,
)


class WalkStatus(Enum):
    """Overall status of the translation walk."""

    SUCCESS = auto()          # Translation completed successfully
    S1_FAULT = auto()         # Fault during Stage 1
    S2_FAULT = auto()         # Fault during Stage 2
    S2_FINAL_FAULT = auto()   # Fault during final IPA→PA translation


@dataclass
class WalkEvent:
    """
    Unified event for walk visualization.

    This flattens S1 and S2 events into a chronological sequence
    suitable for visualization.

    Attributes:
        event_id: Global event ID.
        event_type: 'T' for translation read, 'M' for memory access.
        stage: 1 or 2.
        level: Translation table level (0-3).
        purpose: What this event is for (e.g., "S1 L0 table", "S2 for S1 L0").
        address: Address being processed.
        descriptor_value: Descriptor value read.
        result: What the descriptor means ("Table", "Page", "Invalid").
        output: Next address or final address.
    """

    event_id: int
    event_type: str
    stage: int
    level: int
    purpose: str
    address: int
    descriptor_value: int
    result: str
    output: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "stage": self.stage,
            "level": self.level,
            "purpose": self.purpose,
            "address": f"0x{self.address:016X}",
            "descriptor_value": f"0x{self.descriptor_value:016X}",
            "result": self.result,
            "output": f"0x{self.output:016X}",
        }


@dataclass
class WalkResult:
    """
    Complete result of a 2-stage page table walk.

    Attributes:
        status: Overall walk status.
        input_va: The virtual address that was translated.
        output_pa: The final physical address (if successful).
        ipa: The intermediate physical address from Stage 1.
        events: Chronological list of all events (flattened).
        s1_result: Detailed Stage 1 result.
        s2_final_result: Stage 2 result for final IPA→PA.
        total_memory_accesses: Count of T-events.
        fault: Fault record if any.
        final_permissions: Combined permissions.
        final_attributes: Memory attributes.
        register_snapshots: Register values at key points.
    """

    status: WalkStatus
    input_va: VirtualAddress
    output_pa: Optional[PhysicalAddress] = None
    ipa: Optional[IntermediatePhysicalAddress] = None
    events: List[WalkEvent] = field(default_factory=list)
    s1_result: Optional[Stage1WalkResult] = None
    s2_final_result: Optional[Stage2WalkResult] = None
    total_memory_accesses: int = 0
    fault: Optional[FaultRecord] = None
    final_permissions: Optional[AccessPermissions] = None
    final_attributes: Optional[MemoryAttributes] = None
    register_snapshots: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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

        attr_dict = None
        if self.final_attributes:
            attr_dict = {
                "shareability": self.final_attributes.shareability.name,
                "memory_type": self.final_attributes.memory_type.name,
                "attr_index": self.final_attributes.attr_index,
                "access_flag": self.final_attributes.access_flag,
            }

        return {
            "status": self.status.name,
            "input_va": self.input_va.to_hex(),
            "output_pa": self.output_pa.to_hex() if self.output_pa else None,
            "ipa": self.ipa.to_hex() if self.ipa else None,
            "total_memory_accesses": self.total_memory_accesses,
            "events": [e.to_dict() for e in self.events],
            "fault": self.fault.to_dict() if self.fault else None,
            "final_permissions": perm_dict,
            "final_attributes": attr_dict,
            "register_snapshots": self.register_snapshots,
        }


class PageTableWalker:
    """
    Facade for complete 2-stage page table walks.

    This class provides a simple interface for performing address
    translation and produces a complete trace of all operations.

    Usage:
        walker = PageTableWalker(register_state, translation_tables)
        result = walker.walk(virtual_address)

    Design Pattern: Facade
        - Hides complexity of Stage1/Stage2 walkers
        - Provides single entry point for translation
        - Coordinates event sequencing and result aggregation
    """

    def __init__(
        self,
        register_state: RegisterState,
        s1_tables: Optional[Dict[int, int]] = None,
        s2_tables: Optional[Dict[int, int]] = None
    ):
        """
        Initialize the page table walker.

        Args:
            register_state: Complete register state (TTBRs, TCRs).
            s1_tables: Stage 1 translation tables (PA → descriptor).
            s2_tables: Stage 2 translation tables (PA → descriptor).
        """
        self.register_state = register_state
        self.s1_tables = s1_tables or {}
        self.s2_tables = s2_tables or {}

        # Create Stage 2 walker (no nested translation)
        self.stage2_walker = Stage2Walker(
            vttbr_base=register_state.get_stage2_table_base(),
            starting_level=register_state.vtcr_el2.starting_level,
            translation_tables=s2_tables
        )

    def walk(
        self,
        va: VirtualAddress,
        access_type: AccessType = AccessType.READ,
        is_el0: bool = True
    ) -> WalkResult:
        """
        Perform a complete 2-stage translation walk.

        Args:
            va: Virtual address to translate.
            access_type: Type of memory access.
            is_el0: True if access is from EL0 (unprivileged).

        Returns:
            WalkResult with complete translation trace.
        """
        events: List[WalkEvent] = []
        event_counter = 0

        # Record initial register state
        register_snapshots = [{
            "point": "start",
            "VA": va.to_hex(),
            "IPA": None,
            "PA": None,
            "TTBR0_EL1": self.register_state.ttbr0_el1.to_hex(),
            "TTBR1_EL1": self.register_state.ttbr1_el1.to_hex(),
            "VTTBR_EL2": self.register_state.vttbr_el2.to_hex(),
        }]

        # Determine which TTBR to use based on VA
        uses_ttbr1 = va.uses_ttbr1()
        ttbr_base = self.register_state.get_stage1_table_base(uses_ttbr1)

        # Create Stage 1 walker
        stage1_walker = Stage1Walker(
            ttbr_base=ttbr_base,
            stage2_walker=self.stage2_walker,
            starting_level=self.register_state.tcr_el1.starting_level(uses_ttbr1),
            translation_tables=self.s1_tables
        )

        # Reset event counters
        self.stage2_walker.reset_event_counter()
        stage1_walker.reset_event_counter()

        # Perform Stage 1 walk (VA → IPA)
        s1_result = stage1_walker.walk(va, access_type, is_el0)

        # Flatten S1 events with their nested S2 events
        for s1_event in s1_result.events:
            # First, add all S2 events for translating the table address
            for s2_event in s1_event.s2_events:
                event_counter += 1
                events.append(WalkEvent(
                    event_id=event_counter,
                    event_type="T",
                    stage=2,
                    level=s2_event.level,
                    purpose=f"S2 for S1 L{s1_event.level} table @ IPA 0x{s1_event.table_base_ipa:X}",
                    address=s2_event.descriptor_address,
                    descriptor_value=s2_event.descriptor_value,
                    result=s2_event.descriptor_type.name,
                    output=s2_event.output_address
                ))

            # Then add the S1 event itself
            event_counter += 1
            events.append(WalkEvent(
                event_id=event_counter,
                event_type="T",
                stage=1,
                level=s1_event.level,
                purpose=f"S1 L{s1_event.level} lookup",
                address=s1_event.descriptor_address_pa,
                descriptor_value=s1_event.descriptor_value,
                result=s1_event.descriptor_type.name,
                output=s1_event.output_address
            ))

        # Check if Stage 1 failed
        if not s1_result.success:
            return WalkResult(
                status=WalkStatus.S1_FAULT,
                input_va=va,
                events=events,
                s1_result=s1_result,
                total_memory_accesses=event_counter,
                fault=s1_result.fault,
                register_snapshots=register_snapshots
            )

        # Stage 1 succeeded - record IPA
        ipa = s1_result.output_ipa
        register_snapshots.append({
            "point": "after_s1",
            "VA": va.to_hex(),
            "IPA": ipa.to_hex() if ipa else None,
            "PA": None,
        })

        # Perform final Stage 2 walk (IPA → PA)
        self.stage2_walker.set_event_counter(event_counter)
        s2_result = self.stage2_walker.walk(ipa, access_type)

        # Add final S2 events
        for s2_event in s2_result.events:
            event_counter += 1
            events.append(WalkEvent(
                event_id=event_counter,
                event_type="T",
                stage=2,
                level=s2_event.level,
                purpose=f"Final S2 L{s2_event.level} for IPA 0x{ipa.value:X}",
                address=s2_event.descriptor_address,
                descriptor_value=s2_event.descriptor_value,
                result=s2_event.descriptor_type.name,
                output=s2_event.output_address
            ))

        # Check if final Stage 2 failed
        if not s2_result.success:
            return WalkResult(
                status=WalkStatus.S2_FINAL_FAULT,
                input_va=va,
                ipa=ipa,
                events=events,
                s1_result=s1_result,
                s2_final_result=s2_result,
                total_memory_accesses=event_counter,
                fault=s2_result.fault,
                final_permissions=s1_result.final_permissions,
                register_snapshots=register_snapshots
            )

        # Complete success!
        pa = s2_result.output_pa
        register_snapshots.append({
            "point": "complete",
            "VA": va.to_hex(),
            "IPA": ipa.to_hex(),
            "PA": pa.to_hex() if pa else None,
        })

        return WalkResult(
            status=WalkStatus.SUCCESS,
            input_va=va,
            output_pa=pa,
            ipa=ipa,
            events=events,
            s1_result=s1_result,
            s2_final_result=s2_result,
            total_memory_accesses=event_counter,
            final_permissions=s1_result.final_permissions,
            register_snapshots=register_snapshots
        )
