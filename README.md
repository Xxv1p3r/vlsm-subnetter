# Enterprise VLSM Subnet Planner & Address Automation Engine

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![RFC Compliant](https://img.shields.io/badge/RFC-1918%20%7C%204632-orange.svg)](https://datatracker.ietf.org/doc/html/rfc4632)
[![Dependencies](https://img.shields.io/badge/dependencies-None%20(Stdlib)-brightgreen.svg)](#requirements)

A modular, production-grade Python tool designed by network engineers for automated IPv4 enterprise subnetting using **VLSM (Variable Length Subnet Masking)**. 

Calculates address spaces, guarantees zero-fragmentation binary boundary alignment, validates capacity against overflows, and summarizes unallocated IP space into optimal CIDR blocks for future growth.

---

## Key Features

- **Zero-Fragmentation VLSM Allocation**: Sorts requests strictly in descending order of host requirements to align subnets along natural binary boundaries ($2^n$).
- **$O(1)$ Host Arithmetic via Standard Library**: Implements high-performance address calculations using Python's built-in `ipaddress` library without memory bloat on large supernets (`/8` to `/16`).
- **Preventive Overflow Validation**:
  - **Prefix Overflow**: Verifies whether any single department requires more addresses than the entire base supernet.
  - **Address Space Overflow**: Computes block sums upfront and halts execution with descriptive diagnostics if total demand exceeds available capacity.
- **Dynamic Terminal Table**: Adapts column widths dynamically to prevent truncated department names, displaying CIDR, decimal netmasks, usable host ranges, and broadcast addresses.
- **IPAM & Future Capacity Planning**: Analyzes remaining contiguous IP ranges and summarizes them into minimal CIDR blocks via `summarize_address_range()`.
- **Export Capabilities**: Exports allocation results to structured **CSV** and **JSON** formats for documentation and IPAM integration.
- **Zero External Dependencies**: Runs out-of-the-box on standard Python 3.8+ installations.

---

## Architectural & Mathematical Principles

### 1. Host Calculation & Prefix Determination
In standard corporate IPv4 networks, every subnet requires:
- **1 Network ID** (host bits all `0`)
- **1 Broadcast Address** (host bits all `1`)
- **$H$ Usable Host Addresses**

The number of required host bits $n$ satisfies:
$$2^n \ge H + 2 \implies n = \lceil \log_2(H + 2) \rceil$$

The resulting CIDR prefix length is:
$$P = 32 - n$$

### 2. Binary Alignment & Boundary Rule
In CIDR subnetting, a block of size $S = 2^n$ must have its network address start at an integer multiple of $S$:
$$\text{Base IP Integer} \pmod{S} = 0$$

By sorting subnet requests in non-increasing order ($S_0 \ge S_1 \ge S_2 \ge \dots$), every subsequently allocated block $S_{i+1}$ is a divisor of all preceding blocks, guaranteeing clean boundary alignment without leaving unreachable gaps.

---

## Installation & Requirements

- Python 3.8 or higher
- No third-party packages required (`ipaddress`, `math`, `dataclasses`, `argparse`, `json`, and `csv` are part of the Python Standard Library).

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/vlsm-subnet-calculator.git
cd vlsm-subnet-calculator

# Make the script executable (Linux / macOS)
chmod +x vlsm_calculator.py
```

---

## Usage

### 1. Interactive CLI Wizard (Default)
Run without arguments to launch the guided interactive assistant:

```bash
./vlsm_calculator.py
```

```text
+==============================================================================+
|           ENTERPRISE VLSM SUBNET PLANNER - NETWORK ENGINEERING CLI           |
+==============================================================================+

[?] Enter base network in CIDR format (e.g., 192.168.0.0/16 or 10.0.0.0/8): 192.168.10.0/24
 [OK] Base Network validated: 192.168.10.0/24 (256 total IPs)

[?] Enter the number of network departments/groups to configure: 2

--- Subnet Requirements for 2 Department(s) ---

[ Department #1 ]
  -> Department or function name (e.g., Sales, DataCenter): Sales
  -> Number of subnets required for 'Sales': 1
  -> Number of usable hosts needed per subnet: 50

[ Department #2 ]
  -> Department or function name (e.g., Sales, DataCenter): IT_Staff
  -> Number of subnets required for 'IT_Staff': 2
  -> Number of usable hosts needed per subnet: 20

[+] Computing optimal VLSM subnet allocation...
```

### 2. Enterprise Demo Mode
Simulates a multi-tier corporate network infrastructure (`10.50.0.0/20` with Core Data Center, Campus LAN, Remote Branches, IoT, and P2P WAN links):

```bash
./vlsm_calculator.py --demo
```

### 3. Export to CSV & JSON
Generate structured export files for network auditing or IPAM importing:

```bash
./vlsm_calculator.py --demo --csv corporate_subnets.csv --json corporate_subnets.json
```

---

## Sample Console Output

```text
====================================================================================================================================
 ENTERPRISE VLSM SUBNET PLANNER - EXECUTIVE ADDRESSING SUMMARY
====================================================================================================================================
 Base Network           : 10.50.0.0/20 (Subnet Mask: 255.255.240.0)
 Global Range           : 10.50.0.0  -->  10.50.15.255
 Total Block Capacity   : 4,096 total IPs (4,094 usable)
 Allocated Space        : 2,648 IPs (64.65% of base network)
 Planned Hosts          : 2,262 requested | 2,604 allocatable
 Remaining Free Space   : 1,448 IPs (35.35%)
====================================================================================================================================
+----------------------------------+--------------------------------------+------------------+------------------+------------------+--------------------+
| Subnet Identifier                | Network ID & Mask (CIDR / Dec)       | First Usable Host | Last Usable Host | Broadcast Address | Total IPs (Usable) |
+==================================+======================================+==================+==================+==================+====================+
| Data Center Core (Subnet #1)     | 10.50.0.0/23 (255.255.254.0)         | 10.50.0.1        | 10.50.1.254      | 10.50.1.255      |          512 (510) |
| Data Center Core (Subnet #2)     | 10.50.2.0/23 (255.255.254.0)         | 10.50.2.1        | 10.50.3.254      | 10.50.3.255      |          512 (510) |
| Main Campus (Subnet #1)          | 10.50.4.0/24 (255.255.255.0)         | 10.50.4.1        | 10.50.4.254      | 10.50.4.255      |          256 (254) |
| Main Campus (Subnet #2)          | 10.50.5.0/24 (255.255.255.0)         | 10.50.5.1        | 10.50.5.254      | 10.50.5.255      |          256 (254) |
| Remote Branches (Subnet #1)      | 10.50.8.0/26 (255.255.255.192)       | 10.50.8.1        | 10.50.8.62       | 10.50.8.63       |            64 (62) |
| Remote Branches (Subnet #2)      | 10.50.8.64/26 (255.255.255.192)      | 10.50.8.65       | 10.50.8.126      | 10.50.8.127      |            64 (62) |
| P2P WAN Links (Subnet #1)        | 10.50.10.64/30 (255.255.255.252)     | 10.50.10.65      | 10.50.10.66      | 10.50.10.67      |              4 (2) |
| P2P WAN Links (Subnet #2)        | 10.50.10.68/30 (255.255.255.252)     | 10.50.10.69      | 10.50.10.70      | 10.50.10.71      |              4 (2) |
+----------------------------------+--------------------------------------+------------------+------------------+------------------+--------------------+

------------------------------------------------------------------------------------------
 AVAILABLE BLOCKS FOR FUTURE EXPANSION (SUMMARIZED UNALLOCATED SPACE)
------------------------------------------------------------------------------------------
  * CIDR Block: 10.50.10.88/29     | Mask: 255.255.255.248 | Range: 10.50.10.88 - 10.50.10.95 (8 IPs)
  * CIDR Block: 10.50.10.96/27     | Mask: 255.255.255.224 | Range: 10.50.10.96 - 10.50.10.127 (32 IPs)
  * CIDR Block: 10.50.10.128/25    | Mask: 255.255.255.128 | Range: 10.50.10.128 - 10.50.10.255 (128 IPs)
  * CIDR Block: 10.50.11.0/24      | Mask: 255.255.255.0   | Range: 10.50.11.0 - 10.50.11.255 (256 IPs)
  * CIDR Block: 10.50.12.0/22      | Mask: 255.255.252.0   | Range: 10.50.12.0 - 10.50.15.255 (1,024 IPs)
------------------------------------------------------------------------------------------
```

---

## Python API Integration

You can integrate `VLSMSubnetEngine` directly into Python scripts, automation playbooks, or FastAPI backends:

```python
from vlsm_calculator import VLSMSubnetEngine

# Initialize with base supernet
engine = VLSMSubnetEngine("172.16.0.0/21")

# Add department demands: (name, subnets_count, usable_hosts_per_subnet)
engine.add_department("Servers_Cluster", subnets_count=2, hosts_per_subnet=240)
engine.add_department("VoIP_Telephony", subnets_count=1, hosts_per_subnet=120)
engine.add_department("WAN_PointToPoint", subnets_count=4, hosts_per_subnet=2)

# Compute optimal allocations
result = engine.plan()

for subnet in result.allocations:
    print(f"[{subnet.identifier}] {subnet.cidr_notation} | Mask: {subnet.netmask_decimal} | Usable: {subnet.first_usable} - {subnet.last_usable}")

print(f"\nRemaining free IPs: {result.free_ips:,}")
for block in result.free_cidr_blocks:
    print(f"Available free block: {block}")
```

---

## Error Handling & Overflow Diagnostics

When network demand exceeds available address space, the engine raises a `VLSMOverflowError` with precise troubleshooting context:

```text
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
 [!] CRITICAL ADDRESSING ERROR:
Address Space Overflow Error:
  * Base network capacity (192.168.1.0/28) : 16 total IPs.
  * Total space required by VLSM blocks        : 20 IPs.
  * Addressing deficit                         : 4 missing IPs.
  [Suggested Fix]: Expand base network (e.g., prefix /27 or larger).
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

---

## Project Structure

```text
vlsm-subnet-calculator/
├── .gitignore             # Standard Python ignore rules
├── README.md              # Project documentation and specifications
└── vlsm_calculator.py     # Main executable engine and CLI interface
```

---

## Contributing

Pull requests are welcome! For major architectural changes or additional RFC implementations (such as IPv6 subnets or RFC 3021 /31 point-to-point links), please open an issue first to discuss the design.

## License

This project is licensed under the [MIT License](LICENSE).
