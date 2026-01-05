# ARM v9 2-Stage Page Table Walk: A Technical Guide

This document explains the generic process of address translation in ARM v9 architecture when 2-stage translation is enabled (typically used in Virtualization/Hypervisors).

---

## 1. The Core Components

### The Two Stages
1.  **Stage 1 (S1):** Translates a **Virtual Address (VA)** to an **Intermediate Physical Address (IPA)**. This stage is usually controlled by the Guest OS (e.g., Linux kernel in a VM).
2.  **Stage 2 (S2):** Translates the **IPA** to a final **Physical Address (PA)**. This stage is controlled by the Hypervisor.

### The Granule (4KB Pages)
While ARM supports 4KB, 16KB, and 64KB granules, **4KB** is the most common. In a 48-bit address space with a 4KB granule, the address is split into 9-bit indices:

| Level | Bits | Purpose |
| :--- | :--- | :--- |
| **L0 Index** | [47:39] | Selects entry in Level 0 Table |
| **L1 Index** | [38:30] | Selects entry in Level 1 Table |
| **L2 Index** | [29:21] | Selects entry in Level 2 Table |
| **L3 Index** | [20:12] | Selects entry in Level 3 Table |
| **Offset** | [11:0] | Index into the 4KB data page |

---

## 2. Step 1: Selecting the Base Register

### Stage 1 (VA → IPA)
The hardware looks at the Virtual Address to decide which base register to use:
*   **TTBR0_EL1:** Used for "User Space" addresses (High bits are 0).
*   **TTBR1_EL1:** Used for "Kernel Space" addresses (High bits are 1).
*   **NOTE:** The value in these registers is an **IPA**.

### Stage 2 (IPA → PA)
*   **VTTBR_EL2:** Used for *every* Stage 2 translation.
*   **NOTE:** The value in this register is a **PA**.

---

## 3. The Nested Walk Process (The "Walk within a Walk")

This is the most complex part. Because Stage 1 base addresses and pointers are IPAs, the hardware cannot read them directly. **Every time Stage 1 needs to read a table, it triggers a full Stage 2 translation.**

### The Global Sequence:
1.  **Start S1 Walk:** Look at TTBR (IPA).
2.  **Nested S2 Walk:** Translate TTBR IPA → PA.
3.  **Read S1 Table:** Read Descriptor from memory at the PA found.
4.  **Process S1 Descriptor:**
    *   If it points to another table (L0-L2), it gives a new IPA. **Go back to Step 2.**
    *   If it maps a page (L3), it gives the **Final Target IPA**.
5.  **Final S2 Walk:** Translate the Final Target IPA → Final PA.
6.  **Done:** Final PA + original Offset = Destination.

---

## 4. Understanding Descriptors (64-bit)

A descriptor is an 8-byte value. The lower 2 bits [1:0] determine the type:

| Type | Bit [1:0] | Meaning |
| :--- | :---: | :--- |
| **Invalid** | `00` | Translation Fault. Access is denied. |
| **Block** | `01` | Map a large chunk (1GB at L1, 2MB at L2). Walk ends. |
| **Table** | `11` | Points to the next-level table base address. Only at L0-L2. |
| **Page** | `11` | Points to the final 4KB page base address. Only at L3. |

### Bit Field Layout:
*   **[47:12]: Output Address.** The base address (of the next table or final page).
*   **[11:2]: Attributes.** Metadata (Access Permissions, Cacheability, etc.).
*   **[1]: Descriptor Type.**
*   **[0]: Valid Bit.** Must be 1.

---

## 5. Termination Conditions

The walk stops immediately if:
1.  **Invalid Descriptor:** Encountering a value with Bit 0 = 0.
2.  **Page Descriptor:** Reaching Level 3 and finding a valid descriptor.
3.  **Block Descriptor:** Reaching Level 1 or 2 and finding a descriptor with `0b01` in the low bits.
4.  **Permission Fault:** The attributes in the descriptor forbid the requested access (e.g., trying to write to a Read-Only page).

---

## 6. Real-World Example Walk

**Input:** VA `0x1000` (Index L0-L2 = 0, L3 = 1).

1.  **S1 L0:** TTBR0 points to IPA `X`.
2.  **Nested S2:** Translate IPA `X` → PA `Y`. 
3.  **Read S1 L0:** Read PA `Y`. It contains a **Table Descriptor** pointing to IPA `Z`.
4.  **S1 L1:** Translate IPA `Z` → PA `W`.
5.  **Read S1 L1:** Read PA `W`. It contains a **Table Descriptor** pointing to IPA `V`.
6.  (Repeat for L2...)
7.  **Final S1 L3:** Returns target IPA `0x50000`.
8.  **Final S2:** Translate IPA `0x50000` → PA `0x90000`.
9.  **Output:** Final PA is `0x90000` + Offset.
