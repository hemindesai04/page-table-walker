"""
Fault exception models for ARM v9 page table walks.

This module defines the exceptions that can occur during address translation.

TRANSLATION FAULTS:
-------------------
Occur when a descriptor is marked as invalid (bit[0] = 0) at any level.
The fault syndrome indicates which level caused the fault.

PERMISSION FAULTS:
------------------
Occur when the access type violates the permissions in the descriptor:
- Read to a region without read permission
- Write to a read-only region
- Execute from an execute-never region

ADDRESS SIZE FAULTS:
--------------------
Occur when the output address exceeds the configured PA size.

FAULT ADDRESS REGISTER (FAR):
-----------------------------
When a fault occurs, the failing address is saved to FAR_ELn:
- FAR_EL1: For Stage 1 faults (contains the failing VA)
- FAR_EL2: For Stage 2 faults (contains the failing IPA)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class FaultType(Enum):
    """Types of faults that can occur during translation."""

    TRANSLATION_FAULT = auto()  # Invalid descriptor
    PERMISSION_FAULT = auto()   # Access permission violation
    ADDRESS_SIZE_FAULT = auto()  # Address exceeds configured size
    ACCESS_FLAG_FAULT = auto()  # Access flag not set


class AccessType(Enum):
    """Type of memory access being performed."""

    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"


@dataclass
class BaseFault(Exception):
    """
    Base class for all translation faults.

    Attributes:
        stage: Translation stage where fault occurred (1 or 2).
        level: Translation table level where fault occurred (0-3).
        address: The address that caused the fault.
        message: Human-readable fault description.
    """

    stage: int
    level: int
    address: int
    message: str = ""

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__} at Stage {self.stage} Level {self.level}: "
            f"address=0x{self.address:016X} - {self.message}"
        )


@dataclass
class TranslationFault(BaseFault):
    """
    Translation fault - invalid descriptor encountered.

    This fault occurs when the walker encounters a descriptor with
    bit[0] = 0 (invalid descriptor). The translation cannot proceed
    and software must handle the fault (e.g., by populating the table).

    ESR_ELn.DFSC/IFSC encoding for translation faults:
        0b0001xx where xx = level (00=L0, 01=L1, 10=L2, 11=L3)
    """

    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Invalid descriptor at Stage {self.stage} Level {self.level}"
            )


@dataclass
class PermissionFault(BaseFault):
    """
    Permission fault - access type not permitted.

    This fault occurs when the descriptor is valid but the access
    permissions do not allow the requested access type.

    Attributes:
        access_type: The type of access that was denied.
        permissions_found: Description of permissions in the descriptor.

    ESR_ELn.DFSC/IFSC encoding for permission faults:
        0b0011xx where xx = level
    """

    access_type: AccessType = AccessType.READ
    permissions_found: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"{self.access_type.value} access denied. "
                f"Permissions: {self.permissions_found}"
            )


@dataclass
class AddressSizeFault(BaseFault):
    """
    Address size fault - output address too large.

    This fault occurs when the output address from a descriptor
    exceeds the configured physical address size.

    Attributes:
        configured_bits: The configured PA size.
        address_bits_needed: The actual bits needed for the address.

    ESR_ELn.DFSC/IFSC encoding for address size faults:
        0b0000xx where xx = level
    """

    configured_bits: int = 48
    address_bits_needed: int = 0

    def __post_init__(self) -> None:
        if not self.message:
            self.message = (
                f"Address requires {self.address_bits_needed} bits, "
                f"but only {self.configured_bits} bits configured"
            )


@dataclass
class FaultRecord:
    """
    Record of a fault for logging and visualization.

    This is a non-exception class used to record fault information
    in the walk trace without raising an exception.
    """

    fault_type: FaultType
    stage: int
    level: int
    address: int
    access_type: Optional[AccessType] = None
    message: str = ""
    far_el1: Optional[int] = None  # Fault Address Register EL1
    far_el2: Optional[int] = None  # Fault Address Register EL2

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "fault_type": self.fault_type.name,
            "stage": self.stage,
            "level": self.level,
            "address": f"0x{self.address:016X}",
            "access_type": self.access_type.value if self.access_type else None,
            "message": self.message,
            "FAR_EL1": f"0x{self.far_el1:016X}" if self.far_el1 else None,
            "FAR_EL2": f"0x{self.far_el2:016X}" if self.far_el2 else None,
        }


def check_permission(
    access_type: AccessType,
    ap: int,
    uxn: bool,
    pxn: bool,
    is_el0: bool
) -> bool:
    """
    Check if an access is permitted based on descriptor permissions.

    Args:
        access_type: The type of access being performed.
        ap: AP[7:6] value from the descriptor.
        uxn: UXN (Unprivileged Execute Never) bit.
        pxn: PXN (Privileged Execute Never) bit.
        is_el0: True if access is from EL0 (unprivileged).

    Returns:
        True if access is permitted, False otherwise.
    """
    if access_type == AccessType.EXECUTE:
        # Check execute permissions
        if is_el0:
            return not uxn
        else:
            return not pxn

    # Read/Write permissions based on AP bits
    if is_el0:
        # EL0 access
        if access_type == AccessType.READ:
            return ap in (0b01, 0b11)  # EL0 can read
        else:  # WRITE
            return ap == 0b01  # Only AP=01 allows EL0 write
    else:
        # EL1 access
        if access_type == AccessType.READ:
            return True  # EL1 can always read
        else:  # WRITE
            return ap in (0b00, 0b01)  # AP=00 or 01 allows EL1 write


def check_stage2_permission(
    access_type: AccessType,
    s2ap: int,
    xn: bool
) -> bool:
    """
    Check Stage 2 permissions.

    Args:
        access_type: The type of access.
        s2ap: S2AP[1:0] value from Stage 2 descriptor.
        xn: Execute Never bit.

    Returns:
        True if access is permitted.
    """
    if access_type == AccessType.EXECUTE:
        return not xn

    if access_type == AccessType.READ:
        return s2ap in (0b01, 0b11)
    else:  # WRITE
        return s2ap in (0b10, 0b11)
