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
        return {
            ipaddress.ip_address(parts[1].split(';')[0]): "DHCP Range",
        }
    else:
        start = ''
        end = ''
        for part in parts:
            if part not in ('range', ''):
                if ';' in part:
                    end = part.split(';')[0]
                else:
                    start = part
        subnet = None
        for sub in SUBNETS:
            if ipaddress.ip_address(start) in sub:
                subnet = sub
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


def main():
    # Get all subnets before parsing ranges
    with open(CONF) as file:
        for line in file.readlines():
            line = line.strip()
            if "subnet" in line:
                parts = line.split(' ')
                SUBNETS.append(ipaddress.ip_network(f'{parts[1]}/{parts[3]}'))

    dynamic = {}
    with open(CONF) as file:
        for line in file.readlines():
            line = line.strip()
            if "range" in line:
                new_dynamic = parse_ranges(line)
                dynamic = {**dynamic, **new_dynamic}

    hosts = {}
    with open(CONF) as file:
        text = file.read()

    for host, ip in re.findall(re.compile(r'host (.*) {\n.*\n.*fixed-address (.*);\n}', re.MULTILINE), text,):
        hosts[ipaddress.ip_address(ip)] = host

    leases = {}
    with open(LEASE) as file:
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

    all_addresses = {**dynamic, **hosts, **leases}
    for subnet in SUBNETS:
        print(subnet)
        for addr in subnet:
            if addr in all_addresses:
                print(" ", addr, all_addresses[addr])
            else:
                print(" ", addr, "EMPTY")


if __name__ == '__main__':
    main()
