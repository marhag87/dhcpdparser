#!/bin/env python36
import ipaddress
import re

SUBNETS = []
RANGES = []
CONF = '/etc/dhcp/dhcpd.conf'
LEASE = '/var/lib/dhcpd/dhcpd.leases'


def parse_ranges(ranges):
    parts = ranges.split(' ')
    if len(parts) == 2:
        # The range only contains one IP address
        return {
            ipaddress.ip_address(parts[1].split(';')[0]): "DHCP Range",
        }
    else:
        # The range contains more than one IP address
        # Find the start and end of the range
        start = ''
        end = ''
        for part in parts:
            if part not in ('range', ''):
                if ';' in part:
                    end = part.split(';')[0]
                else:
                    start = part

        # Find which subnet the range belongs to
        subnet = None
        for sub in SUBNETS:
            if ipaddress.ip_address(start) in sub:
                subnet = sub

        # Loop through all the addresses in the subnet
        # Add the ip address if it's between the start and end of range
        addresses = {}
        started = False
        for address in subnet:
            if ipaddress.ip_address(start) == address:
                started = True
            if started:
                addresses[address] = "Unused DHCP pool"
            if ipaddress.ip_address(end) == address:
                break
        return addresses


def parse_lease(leasefile):
    # Parse the dhcpd leases file
    # Binding state free is an unused address
    # Binding state active tries to use the hostname, if it is undefined it uses the MAC address
    leases = {}
    with open(leasefile) as file:
        ip = None
        hostname = None
        binding_state = None
        hardware = None
        for line in file.readlines():
            if line.startswith('lease'):
                ip = line.split(' ')[1]
            if line.startswith('  binding state'):
                if 'free' in line:
                    binding_state = 'free'
                if 'active' in line:
                    binding_state = 'active'
            if line.startswith('  hardware ethernet'):
                hardware = re.split('[ ;]', line)[4]
            if line.startswith('  client-hostname'):
                hostname = line.split('"')[1]
            if line.startswith('}'):
                # Lease entry finished, compile address entry and reset
                if binding_state == 'free':
                    leases[ipaddress.ip_address(ip)] = 'Unused DHCP pool'
                elif binding_state == 'active':
                    if hostname is None:
                        leases[ipaddress.ip_address(ip)] = hardware
                    else:
                        leases[ipaddress.ip_address(ip)] = hostname
                ip = None
                hostname = None
                binding_state = None
                hardware = None
    return leases


def human_readable(addresses):
    # Print data in a human readable format
    for subnet in SUBNETS:
        print(subnet)
        for addr in subnet:
            if addr in addresses:
                print(" ", addr, addresses[addr])
            else:
                print(" ", addr, "EMPTY")


def main():
    # Get all subnets defined in the config file
    with open(CONF) as file:
        for line in file.readlines():
            line = line.strip()
            if "subnet" in line:
                parts = line.split(' ')
                SUBNETS.append(ipaddress.ip_network(f'{parts[1]}/{parts[3]}'))

    # Get all ranges defined in the config file
    dynamic = {}
    with open(CONF) as file:
        for line in file.readlines():
            line = line.strip()
            if "range" in line:
                new_dynamic = parse_ranges(line)
                dynamic = {**dynamic, **new_dynamic}

    # Get all hosts defined in the config file
    hosts = {}
    with open(CONF) as file:
        text = file.read()
    for host, ip in re.findall(re.compile(r'host (.*) {\n.*\n.*fixed-address (.*);\n}', re.MULTILINE), text,):
        hosts[ipaddress.ip_address(ip)] = host

    # Get all leases defined in the lease file
    leases = parse_lease(LEASE)

    # Merge all ranges. Leases have prio over hosts that have prio over ranges.
    return {**dynamic, **hosts, **leases}


if __name__ == '__main__':
    human_readable(main())
