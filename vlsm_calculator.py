#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Enterprise VLSM Subnet Planner & Address Automation Engine
================================================================================
Author: Senior Network Engineer & Software Developer
License: MIT
Compatibility: Python 3.8+ (Standard Library: ipaddress, math, dataclasses, argparse, json, csv)

Description:
    A modular, production-grade tool designed for automating enterprise IPv4 subnet
    allocation and planning using VLSM (Variable Length Subnet Masking).
    Fully compliant with RFC 1918 and RFC 4632 standards.

Engineering & Design Principles:
 1. Optimal Allocation Without Fragmentation:
    - Sorts subnet requirements strictly in descending order of host counts.
    - Naturally aligns subnets to binary powers-of-two boundaries.
 2. Robust Capacity & Boundary Validation:
    - Validates IPv4 CIDR syntax (strict network check or automatic normalization).
    - Preventive detection of prefix overflow and total address space exhaustion.
 3. Capacity & IPAM Planning:
    - Calculates and summarizes remaining unallocated space into optimal CIDR blocks.
    - Exports structured data to CSV and JSON formats for audit and IPAM integration.
================================================================================
"""

import sys
import math
import json
import csv
import argparse
import ipaddress
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


class VLSMError(Exception):
    """Base exception class for VLSM calculator errors."""
    pass


class VLSMOverflowError(VLSMError):
    """Raised when requested subnets exceed available address space."""
    pass


class VLSMInvalidNetworkError(VLSMError):
    """Raised when the base network provided is invalid."""
    pass


@dataclass(frozen=True)
class SubnetRequirement:
    """Represents a subnet allocation request for a department or function."""
    department_name: str
    subnet_index: int
    needed_hosts: int

    @property
    def identifier(self) -> str:
        """Formatted human-readable identifier for the subnet."""
        if self.subnet_index > 0:
            return f"{self.department_name} (Subnet #{self.subnet_index})"
        return self.department_name


@dataclass(frozen=True)
class SubnetAllocation:
    """Detailed result of a calculated and assigned subnet."""
    identifier: str
    needed_hosts: int
    network: ipaddress.IPv4Network
    first_usable: ipaddress.IPv4Address
    last_usable: ipaddress.IPv4Address
    broadcast: ipaddress.IPv4Address
    total_ips: int
    usable_hosts: int

    @property
    def netmask_decimal(self) -> str:
        """Subnet mask in dotted-decimal format (e.g., 255.255.255.192)."""
        return str(self.network.netmask)

    @property
    def cidr_notation(self) -> str:
        """Network address with CIDR prefix (e.g., 192.168.10.0/26)."""
        return f"{self.network.network_address}/{self.network.prefixlen}"

    @property
    def efficiency_pct(self) -> float:
        """Efficiency percentage of usable host capacity utilization."""
        if self.usable_hosts <= 0:
            return 0.0
        return min(100.0, (self.needed_hosts / self.usable_hosts) * 100.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the allocation to a standard dictionary."""
        return {
            "identifier": self.identifier,
            "needed_hosts": self.needed_hosts,
            "network_id": str(self.network.network_address),
            "prefix_cidr": f"/{self.network.prefixlen}",
            "network_cidr": self.cidr_notation,
            "netmask_decimal": self.netmask_decimal,
            "first_usable": str(self.first_usable),
            "last_usable": str(self.last_usable),
            "broadcast": str(self.broadcast),
            "total_ips": self.total_ips,
            "usable_hosts": self.usable_hosts,
            "efficiency_pct": round(self.efficiency_pct, 2)
        }


@dataclass
class VLSMPlanResult:
    """Container holding the complete output of an enterprise subnetting plan."""
    base_network: ipaddress.IPv4Network
    allocations: List[SubnetAllocation]
    total_requested_hosts: int
    total_allocated_ips: int
    total_usable_hosts: int
    free_ips: int
    free_cidr_blocks: List[ipaddress.IPv4Network]


class VLSMSubnetEngine:
    """
    Decoupled VLSM calculation and allocation engine.
    Suitable for integration into CI/CD pipelines, automation scripts, or REST APIs.
    """

    def __init__(self, base_cidr: str, strict: bool = False):
        """
        :param base_cidr: Initial network in CIDR notation (e.g., '192.168.0.0/16', '10.0.0.0/8').
        :param strict: If True, disallows host bits set in the base network address.
        """
        self.base_network: ipaddress.IPv4Network = self._parse_network(base_cidr, strict=strict)
        self.requirements: List[SubnetRequirement] = []

    @staticmethod
    def _parse_network(cidr: str, strict: bool) -> ipaddress.IPv4Network:
        try:
            net = ipaddress.ip_network(cidr.strip(), strict=strict)
            if not isinstance(net, ipaddress.IPv4Network):
                raise VLSMInvalidNetworkError(
                    f"Enterprise VLSM calculator requires an IPv4 network. Received: '{cidr}'"
                )
            return net
        except ValueError as ex:
            raise VLSMInvalidNetworkError(
                f"Invalid base network CIDR format '{cidr}': {ex}"
            ) from ex

    @staticmethod
    def calculate_prefix(needed_hosts: int) -> int:
        """
        Calculates the optimal CIDR prefix (/P) required to host 'needed_hosts' usable IPs.
        Formula: 2^h >= needed_hosts + 2 (1 Network ID + 1 Broadcast) => prefix = 32 - h
        """
        if needed_hosts < 1:
            raise ValueError("Usable hosts requirement must be an integer >= 1.")

        total_ips_needed = needed_hosts + 2
        host_bits = max(2, (total_ips_needed - 1).bit_length())
        prefix = 32 - host_bits

        if prefix < 0:
            raise ValueError(f"Requested hosts count ({needed_hosts:,}) exceeds theoretical IPv4 limit.")

        return prefix

    def add_department(self, name: str, subnets_count: int, hosts_per_subnet: int) -> None:
        """
        Registers a department or business unit subnet requirement.

        :param name: Department or functional name.
        :param subnets_count: Number of identical subnets needed.
        :param hosts_per_subnet: Number of usable hosts needed per subnet.
        """
        clean_name = name.strip() or "Subnet"
        if subnets_count < 1:
            raise ValueError("Number of subnets must be an integer >= 1.")
        if hosts_per_subnet < 1:
            raise ValueError("Usable hosts per subnet must be an integer >= 1.")

        for i in range(1, subnets_count + 1):
            idx = i if subnets_count > 1 else 0
            self.requirements.append(
                SubnetRequirement(
                    department_name=clean_name,
                    subnet_index=idx,
                    needed_hosts=hosts_per_subnet
                )
            )

    def plan(self) -> VLSMPlanResult:
        """
        Executes the VLSM planning algorithm, sorting descending and allocating contiguous blocks.

        :return: VLSMPlanResult object containing assigned subnets and summarized free space.
        :raises VLSMOverflowError: If requested subnets exceed available address capacity.
        """
        if not self.requirements:
            raise VLSMError("No subnet requirements have been registered for planning.")

        # 1. DESCENDING SORT: Essential for zero-fragmentation binary alignment
        sorted_reqs = sorted(self.requirements, key=lambda r: r.needed_hosts, reverse=True)

        # 2. PREVENTIVE CAPACITY & PREFIX VALIDATION
        total_block_ips_needed = 0
        base_capacity = self.base_network.num_addresses

        for req in sorted_reqs:
            prefix = self.calculate_prefix(req.needed_hosts)
            block_size = 1 << (32 - prefix)

            if prefix < self.base_network.prefixlen:
                raise VLSMOverflowError(
                    f"Prefix Overflow Error:\n"
                    f"  Requirement '{req.identifier}' requires {req.needed_hosts:,} usable hosts "
                    f"(/{prefix} block of {block_size:,} IPs), which individually exceeds the total "
                    f"base network {self.base_network} (max /{self.base_network.prefixlen}, "
                    f"{base_capacity:,} IPs)."
                )

            total_block_ips_needed += block_size

        if total_block_ips_needed > base_capacity:
            deficit = total_block_ips_needed - base_capacity
            raise VLSMOverflowError(
                f"Address Space Overflow Error:\n"
                f"  * Base network capacity ({self.base_network}) : {base_capacity:,} total IPs.\n"
                f"  * Total space required by VLSM blocks        : {total_block_ips_needed:,} IPs.\n"
                f"  * Addressing deficit                         : {deficit:,} missing IPs.\n"
                f"  [Suggested Fix]: Expand base network (e.g., prefix "
                f"/{self.base_network.prefixlen - 1} or larger)."
            )

        # 3. SEQUENTIAL CONTIGUOUS ALLOCATION
        allocations: List[SubnetAllocation] = []
        current_ip_int = int(self.base_network.network_address)
        base_broadcast_int = int(self.base_network.broadcast_address)
        total_requested_hosts = 0
        total_usable_hosts = 0

        for req in sorted_reqs:
            prefix = self.calculate_prefix(req.needed_hosts)
            block_size = 1 << (32 - prefix)

            # Enforce power-of-two boundary alignment
            if current_ip_int % block_size != 0:
                remainder = current_ip_int % block_size
                current_ip_int += (block_size - remainder)

            # Check boundary overflow
            if (current_ip_int + block_size - 1) > base_broadcast_int:
                raise VLSMOverflowError(
                    f"Boundary overflow while allocating '{req.identifier}' within {self.base_network}."
                )

            subnet = ipaddress.IPv4Network((current_ip_int, prefix))
            first_usable = subnet.network_address + 1
            last_usable = subnet.broadcast_address - 1
            usable_count = subnet.num_addresses - 2

            allocations.append(
                SubnetAllocation(
                    identifier=req.identifier,
                    needed_hosts=req.needed_hosts,
                    network=subnet,
                    first_usable=first_usable,
                    last_usable=last_usable,
                    broadcast=subnet.broadcast_address,
                    total_ips=subnet.num_addresses,
                    usable_hosts=usable_count
                )
            )

            total_requested_hosts += req.needed_hosts
            total_usable_hosts += usable_count
            current_ip_int += block_size

        # 4. REMAINING FREE SPACE CALCULATION (SUMMARIZED CIDR BLOCKS)
        free_ips = (base_broadcast_int + 1) - current_ip_int
        free_cidr_blocks: List[ipaddress.IPv4Network] = []
        if free_ips > 0:
            free_start = ipaddress.IPv4Address(current_ip_int)
            free_end = ipaddress.IPv4Address(base_broadcast_int)
            free_cidr_blocks = list(ipaddress.summarize_address_range(free_start, free_end))

        return VLSMPlanResult(
            base_network=self.base_network,
            allocations=allocations,
            total_requested_hosts=total_requested_hosts,
            total_allocated_ips=total_block_ips_needed,
            total_usable_hosts=total_usable_hosts,
            free_ips=free_ips,
            free_cidr_blocks=free_cidr_blocks
        )


class VLSMConsoleReporter:
    """Generates dynamic console tables, executive summaries, and export files."""

    @staticmethod
    def print_report(result: VLSMPlanResult) -> None:
        """Renders an executive summary table dynamically fitted to content dimensions."""
        base_net = result.base_network
        capacity = base_net.num_addresses
        used_pct = (result.total_allocated_ips / capacity) * 100.0
        free_pct = (result.free_ips / capacity) * 100.0

        print("\n" + "=" * 132)
        print(" ENTERPRISE VLSM SUBNET PLANNER - EXECUTIVE ADDRESSING SUMMARY")
        print("=" * 132)
        print(f" Base Network           : {base_net} (Subnet Mask: {base_net.netmask})")
        print(f" Global Range           : {base_net.network_address}  -->  {base_net.broadcast_address}")
        print(f" Total Block Capacity   : {capacity:,} total IPs ({capacity - 2:,} usable)")
        print(f" Allocated Space        : {result.total_allocated_ips:,} IPs ({used_pct:.2f}% of base network)")
        print(f" Planned Hosts          : {result.total_requested_hosts:,} requested | {result.total_usable_hosts:,} allocatable")
        print(f" Remaining Free Space   : {result.free_ips:,} IPs ({free_pct:.2f}%)")
        print("=" * 132)

        # Dynamic column width calculation to prevent truncation
        col_id_w = max(24, max(len(a.identifier) for a in result.allocations) + 2)
        col_net_w = max(36, max(len(f"{a.cidr_notation} ({a.netmask_decimal})") for a in result.allocations) + 2)
        col_first_w = max(16, max(len(str(a.first_usable)) for a in result.allocations) + 2)
        col_last_w = max(16, max(len(str(a.last_usable)) for a in result.allocations) + 2)
        col_bcast_w = max(16, max(len(str(a.broadcast)) for a in result.allocations) + 2)
        col_ips_w = 18

        header_fmt = (
            f"| {{:<{col_id_w}}} | {{:<{col_net_w}}} | {{:<{col_first_w}}} | "
            f"{{:<{col_last_w}}} | {{:<{col_bcast_w}}} | {{:>{col_ips_w}}} |"
        )
        sep_char = (
            f"+-{'-'*col_id_w}-+-{'-'*col_net_w}-+-{'-'*col_first_w}-+-"
            f"{'-'*col_last_w}-+-{'-'*col_bcast_w}-+-{'-'*col_ips_w}-+"
        )
        sep_double = (
            f"+={'='*col_id_w}=+={'='*col_net_w}=+={'='*col_first_w}=+="
            f"{'='*col_last_w}=+={'='*col_bcast_w}=+={'='*col_ips_w}=+"
        )

        print(sep_char)
        print(header_fmt.format(
            "Subnet Identifier",
            "Network ID & Mask (CIDR / Dec)",
            "First Usable Host",
            "Last Usable Host",
            "Broadcast Address",
            "Total IPs (Usable)"
        ))
        print(sep_double)

        for alloc in result.allocations:
            net_display = f"{alloc.cidr_notation} ({alloc.netmask_decimal})"
            ips_display = f"{alloc.total_ips:,} ({alloc.usable_hosts:,})"
            print(header_fmt.format(
                alloc.identifier,
                net_display,
                str(alloc.first_usable),
                str(alloc.last_usable),
                str(alloc.broadcast),
                ips_display
            ))

        print(sep_char)

        # Remaining free blocks section
        if result.free_cidr_blocks:
            print("\n" + "-" * 90)
            print(" AVAILABLE BLOCKS FOR FUTURE EXPANSION (SUMMARIZED UNALLOCATED SPACE)")
            print("-" * 90)
            for blk in result.free_cidr_blocks:
                print(f"  * CIDR Block: {blk.with_prefixlen:<18} | Mask: {str(blk.netmask):<15} | "
                      f"Range: {blk.network_address} - {blk.broadcast_address} ({blk.num_addresses:,} IPs)")
            print("-" * 90)
        else:
            print("\n [!] No unallocated blocks remaining: address space is 100% utilized.")
        print()

    @staticmethod
    def export_csv(result: VLSMPlanResult, filepath: str) -> None:
        """Exports the subnet allocation table to a structured CSV file."""
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Identifier", "Needed Hosts", "Network ID", "Prefix CIDR",
                "Subnet Mask Decimal", "First Usable Host", "Last Usable Host",
                "Broadcast Address", "Total IPs", "Usable Hosts", "Efficiency %"
            ])
            for a in result.allocations:
                writer.writerow([
                    a.identifier, a.needed_hosts, str(a.network.network_address),
                    f"/{a.network.prefixlen}", a.netmask_decimal,
                    str(a.first_usable), str(a.last_usable), str(a.broadcast),
                    a.total_ips, a.usable_hosts, f"{a.efficiency_pct:.2f}%"
                ])
        print(f" [Export] Subnet allocation successfully saved to CSV: {filepath}")

    @staticmethod
    def export_json(result: VLSMPlanResult, filepath: str) -> None:
        """Exports the subnet plan to a JSON document for IPAM / API consumption."""
        payload = {
            "base_network": str(result.base_network),
            "base_netmask": str(result.base_network.netmask),
            "total_capacity_ips": result.base_network.num_addresses,
            "total_allocated_ips": result.total_allocated_ips,
            "total_requested_hosts": result.total_requested_hosts,
            "total_usable_hosts": result.total_usable_hosts,
            "free_ips": result.free_ips,
            "subnets": [a.to_dict() for a in result.allocations],
            "free_cidr_blocks": [str(b) for b in result.free_cidr_blocks]
        }
        with open(filepath, mode="w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f" [Export] Subnet plan successfully saved to JSON: {filepath}")


def interactive_wizard(export_csv: Optional[str] = None, export_json: Optional[str] = None) -> None:
    """Interactive CLI wizard for real-time input and guided subnetting."""
    print("+" + "=" * 78 + "+")
    print("|           ENTERPRISE VLSM SUBNET PLANNER - NETWORK ENGINEERING CLI           |")
    print("+" + "=" * 78 + "+")

    # 1. Base IP Input & Validation
    engine: Optional[VLSMSubnetEngine] = None
    while not engine:
        try:
            raw_ip = input("\n[?] Enter base network in CIDR format (e.g., 192.168.0.0/16 or 10.0.0.0/8): ").strip()
            if not raw_ip:
                print(" [X] Input cannot be empty. Please provide a valid CIDR network.")
                continue

            try:
                engine = VLSMSubnetEngine(raw_ip, strict=True)
            except ValueError:
                engine = VLSMSubnetEngine(raw_ip, strict=False)
                print(f" [*] Notice: Host bits were set. Normalized to valid network base: {engine.base_network}")

            print(f" [OK] Base Network validated: {engine.base_network} ({engine.base_network.num_addresses:,} total IPs)")
        except (VLSMInvalidNetworkError, Exception) as err:
            print(f" [X] Validation Error: {err}")
            engine = None

    # 2. Number of Departments / Groups
    num_departments = 0
    while num_departments < 1:
        try:
            raw_val = input("\n[?] Enter the number of network departments/groups to configure: ").strip()
            val = int(raw_val)
            if val < 1:
                print(" [X] Value must be an integer >= 1.")
                continue
            num_departments = val
        except ValueError:
            print(" [X] Invalid input. Please enter an integer.")

    # 3. Department Requirements
    print(f"\n--- Subnet Requirements for {num_departments} Department(s) ---")
    for i in range(1, num_departments + 1):
        print(f"\n[ Department #{i} ]")
        dept_name = input(f"  -> Department or function name (e.g., Sales, DataCenter): ").strip()
        if not dept_name:
            dept_name = f"Department_{i}"

        # Subnets count
        subnets_count = 0
        while subnets_count < 1:
            try:
                raw_count = input(f"  -> Number of subnets required for '{dept_name}': ").strip()
                val = int(raw_count)
                if val < 1:
                    print("     [X] Number of subnets must be >= 1.")
                    continue
                subnets_count = val
            except ValueError:
                print("     [X] Please enter a valid integer.")

        # Usable hosts needed
        hosts_needed = 0
        while hosts_needed < 1:
            try:
                raw_hosts = input(f"  -> Number of usable hosts needed per subnet: ").strip()
                val = int(raw_hosts)
                if val < 1:
                    print("     [X] Usable hosts needed must be >= 1.")
                    continue
                hosts_needed = val
            except ValueError:
                print("     [X] Please enter a valid integer.")

        engine.add_department(dept_name, subnets_count, hosts_needed)

    # 4. Calculation and presentation
    try:
        print("\n[+] Computing optimal VLSM subnet allocation...")
        result = engine.plan()
        VLSMConsoleReporter.print_report(result)

        if export_csv:
            VLSMConsoleReporter.export_csv(result, export_csv)
        if export_json:
            VLSMConsoleReporter.export_json(result, export_json)

    except VLSMOverflowError as overflow_err:
        print("\n" + "!" * 80)
        print(" [!] CRITICAL ADDRESSING ERROR:")
        print(f"{overflow_err}")
        print("!" * 80 + "\n")
        sys.exit(1)
    except Exception as general_err:
        print(f"\n[X] Unexpected error during calculation: {general_err}\n")
        sys.exit(1)


def run_demo(export_csv: Optional[str] = None, export_json: Optional[str] = None) -> None:
    """Executes a demonstration with an enterprise corporate topology."""
    print("=" * 80)
    print(" EXECUTING ENTERPRISE VLSM ARCHITECTURE DEMO")
    print("=" * 80)
    base_cidr = "10.50.0.0/20"
    print(f"Corporate Base Network : {base_cidr} (4,096 IPs)")
    print("Enterprise Requirements:")
    print(" - Data Center Core   : 2 subnets of 500 usable hosts")
    print(" - Main Campus        : 4 subnets of 200 usable hosts")
    print(" - Remote Branches    : 8 subnets of 50 usable hosts")
    print(" - IoT Infrastructure : 2 subnets of 25 usable hosts")
    print(" - P2P WAN Links      : 6 subnets of 2 usable hosts (/30)")

    engine = VLSMSubnetEngine(base_cidr)
    engine.add_department("Data Center Core", 2, 500)
    engine.add_department("Main Campus", 4, 200)
    engine.add_department("Remote Branches", 8, 50)
    engine.add_department("IoT Infrastructure", 2, 25)
    engine.add_department("P2P WAN Links", 6, 2)

    result = engine.plan()
    VLSMConsoleReporter.print_report(result)

    if export_csv:
        VLSMConsoleReporter.export_csv(result, export_csv)
    if export_json:
        VLSMConsoleReporter.export_json(result, export_json)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enterprise VLSM Subnet Planner & Address Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  python3 vlsm_calculator.py                    # Interactive guided wizard
  python3 vlsm_calculator.py --demo             # Enterprise architecture demo
  python3 vlsm_calculator.py --demo --csv subnets.csv --json subnets.json
        """
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a preconfigured enterprise topology demonstration."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="File path to export results in CSV format."
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="File path to export results in JSON format."
    )
    args = parser.parse_args()

    if args.demo:
        run_demo(export_csv=args.csv, export_json=args.json)
    else:
        try:
            interactive_wizard(export_csv=args.csv, export_json=args.json)
        except KeyboardInterrupt:
            print("\n\nOperation aborted by user. Exiting...")
            sys.exit(0)


if __name__ == "__main__":
    main()
