import netifaces as ni


def get_local_ip_addresses():
    ip_addresses = []
    interfaces = ni.interfaces()
    for interface in interfaces:
        addresses = ni.ifaddresses(interface)
        if ni.AF_INET in addresses:
            for address in addresses[ni.AF_INET]:
                if "127" not in address['addr']:
                    return address['addr']

    return "127.0.0.1"


if __name__ == '__main__':
    print(get_local_ip_addresses())
