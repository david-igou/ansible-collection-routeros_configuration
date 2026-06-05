#!/usr/bin/env python3
"""Generate / verify roles/configure/vars/main.yml's ``rcfg_path_order``.

This is the source of truth for the canonical apply order. ``SECTIONS`` below is
the hand-maintained dependency spine (referenced object before referencer; parent
before child). Every other *configurable* path that ``community.routeros``
``api_modify`` understands is appended automatically, grouped by top-level and
ordered parent-first, so the list always covers the full configurable surface.

Usage:
  python3 extensions/tests/gen_path_order.py            # rewrite the vars file
  python3 extensions/tests/gen_path_order.py --check    # exit 1 if out of date

"Configurable" = api_modify marks the path ``fully_understood`` and not
``modify_not_supported`` (read-only/status paths are excluded on purpose).
Requires the community.routeros collection to be installed/importable.
"""
import argparse
import glob
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VARS = os.path.join(REPO, 'roles', 'configure', 'vars', 'main.yml')


def load_registry():
    """Import api_modify's path registry, discovering the collection path."""
    try:
        from ansible_collections.community.routeros.plugins.module_utils import _api_data
        return _api_data
    except ImportError:
        pass
    roots = []
    env = os.environ.get('ANSIBLE_COLLECTIONS_PATH', '')
    roots += [os.path.join(p, 'ansible_collections') for p in env.split(':') if p]
    roots += [os.path.expanduser('~/.ansible/collections/ansible_collections')]
    roots += glob.glob(os.path.join(REPO, '.ansible', 'collections', 'ansible_collections'))
    for r in roots:
        parent = os.path.dirname(r)
        if os.path.isdir(os.path.join(r, 'community', 'routeros')) and parent not in sys.path:
            sys.path.insert(0, parent)
    from ansible_collections.community.routeros.plugins.module_utils import _api_data
    return _api_data


# ── Hand-maintained dependency spine. Add new chains here. ──────────────────
SECTIONS = [
    ("certificates (services and tunnels reference them)", [
        '/certificate/settings', '/certificate', '/certificate/crl',
        '/certificate/scep-server', '/certificate/scep-server/ra']),
    ("PPP auth building blocks (tunnels and hotspot reference profiles)", [
        '/ppp/profile', '/ppp/aaa', '/ppp/secret', '/ppp/l2tp-secret']),
    ("physical interfaces", [
        '/interface/ethernet', '/interface/ethernet/poe',
        '/interface/lte/settings', '/interface/lte', '/interface/lte/apn']),
    ("wireless: security-profiles/channels before the radios, then sub-lists", [
        '/interface/wireless/security-profiles', '/interface/wireless/channels',
        '/interface/wireless/manual-tx-power-table', '/interface/wireless',
        '/interface/wireless/connect-list', '/interface/wireless/access-list',
        '/interface/wireless/interworking-profiles', '/interface/wireless/nstreme',
        '/interface/wireless/nstreme-dual', '/interface/wireless/align',
        '/interface/wireless/sniffer', '/interface/wireless/snooper',
        '/interface/wireless/wds', '/interface/wireless/cap']),
    ("wifi: datapath/channel/security -> configuration -> provisioning -> APs", [
        '/interface/wifi/datapath', '/interface/wifi/channel', '/interface/wifi/security',
        '/interface/wifi/security/multi-passphrase', '/interface/wifi/interworking',
        '/interface/wifi/steering', '/interface/wifi/configuration', '/interface/wifi',
        '/interface/wifi/provisioning', '/interface/wifi/network',
        '/interface/wifi/network/radio', '/interface/wifi/radio/settings',
        '/interface/wifi/aaa', '/interface/wifi/access-list', '/interface/wifi/cap',
        '/interface/wifi/capsman']),
    ("wifiwave2 (legacy wifi stack, same dependency shape)", [
        '/interface/wifiwave2/datapath', '/interface/wifiwave2/channel',
        '/interface/wifiwave2/security', '/interface/wifiwave2/interworking',
        '/interface/wifiwave2/steering', '/interface/wifiwave2/configuration',
        '/interface/wifiwave2', '/interface/wifiwave2/provisioning',
        '/interface/wifiwave2/aaa', '/interface/wifiwave2/access-list',
        '/interface/wifiwave2/cap', '/interface/wifiwave2/capsman']),
    ("CAPsMAN: channel/datapath/security -> configuration -> provisioning", [
        '/caps-man/channel', '/caps-man/datapath', '/caps-man/security',
        '/caps-man/rates', '/caps-man/configuration', '/caps-man/provisioning',
        '/caps-man/access-list', '/caps-man/aaa', '/caps-man/manager',
        '/caps-man/manager/interface', '/caps-man/interface',
        '/caps-man/actual-interface-configuration']),
    ("link aggregation / virtual ports on physical interfaces", [
        '/interface/bonding', '/interface/macvlan', '/interface/veth',
        '/interface/macsec/profile', '/interface/macsec']),
    ("bridge: bridge -> settings -> ports/vlans/...", [
        '/interface/bridge', '/interface/bridge/settings', '/interface/bridge/msti',
        '/interface/bridge/port', '/interface/bridge/port/mst-override',
        '/interface/bridge/vlan', '/interface/bridge/mdb', '/interface/bridge/host',
        '/interface/bridge/nat', '/interface/bridge/filter', '/interface/bridge/mlag',
        '/interface/bridge/calea', '/interface/bridge/port-controller',
        '/interface/bridge/port-controller/device',
        '/interface/bridge/port-controller/port', '/interface/bridge/port-extender']),
    ("VLANs and other logical interfaces atop the above", [
        '/interface/vlan', '/interface/vxlan', '/interface/vxlan/vteps',
        '/interface/vrrp', '/interface/mesh', '/interface/mesh/port']),
    ("tunnels", [
        '/interface/6to4', '/interface/eoip', '/interface/eoipv6', '/interface/gre',
        '/interface/gre6', '/interface/ipip', '/interface/ipipv6', '/interface/vpls',
        '/interface/wireguard', '/interface/wireguard/peers', '/interface/l2tp-client',
        '/interface/l2tp-server', '/interface/l2tp-server/server', '/interface/l2tp-ether',
        '/interface/pptp-client', '/interface/pptp-server', '/interface/pptp-server/server',
        '/interface/sstp-client', '/interface/sstp-server', '/interface/sstp-server/server',
        '/interface/ovpn-client', '/interface/ovpn-server', '/interface/ovpn-server/server',
        '/interface/pppoe-client', '/interface/pppoe-server', '/interface/pppoe-server/server',
        '/interface/ppp-client', '/interface/ppp-server', '/interface/dot1x/client',
        '/interface/dot1x/server', '/interface/amt', '/interface/detect-internet']),
    ("interface lists and members (reference the interfaces above)", [
        '/interface/list', '/interface/list/member']),
    ("address pools (referenced by dhcp / hotspot / ppp / ipv6)", [
        '/ip/pool', '/ipv6/pool']),
    ("IP addressing", ['/ip/address', '/ip/arp']),
    ("VRFs and routing tables (routes and rules reference them)", [
        '/ip/vrf', '/ip/route/vrf', '/routing/table']),
    ("core IP services / settings", [
        '/ip/settings', '/ip/neighbor/discovery-settings', '/ip/cloud', '/ip/dns',
        '/ip/dns/forwarders', '/ip/dns/static', '/ip/dns/adlist', '/ip/ssh',
        '/ip/service', '/ip/service/webserver']),
    ("DHCP: client/relay, then server -> network/lease/options", [
        '/ip/dhcp-client', '/ip/dhcp-client/option', '/ip/dhcp-relay',
        '/ip/dhcp-server', '/ip/dhcp-server/config', '/ip/dhcp-server/network',
        '/ip/dhcp-server/option', '/ip/dhcp-server/option/sets', '/ip/dhcp-server/lease',
        '/ip/dhcp-server/matcher', '/ip/dhcp-server/alert']),
    ("firewall: address-lists/helpers before rules", [
        '/ip/firewall/address-list', '/ip/firewall/layer7-protocol',
        '/ip/firewall/service-port', '/ip/firewall/connection/tracking',
        '/ip/firewall/filter', '/ip/firewall/nat', '/ip/firewall/mangle',
        '/ip/firewall/raw', '/ip/firewall/calea']),
    ("routes and policy-routing rules (after addressing/vrf/tables)", [
        '/ip/route', '/ip/route/rule', '/routing/rule', '/routing/route/rule']),
    ("hotspot chain (pool/dns/profile already applied)", [
        '/ip/hotspot/profile', '/ip/hotspot/user/profile', '/ip/hotspot',
        '/ip/hotspot/user', '/ip/hotspot/ip-binding', '/ip/hotspot/service-port',
        '/ip/hotspot/walled-garden', '/ip/hotspot/walled-garden/ip']),
    ("IPsec: proposal/profile/keys -> peer/identity -> policy", [
        '/ip/ipsec/settings', '/ip/ipsec/proposal', '/ip/ipsec/profile', '/ip/ipsec/key',
        '/ip/ipsec/key/psk', '/ip/ipsec/key/rsa', '/ip/ipsec/key/qkd',
        '/ip/ipsec/mode-config', '/ip/ipsec/peer', '/ip/ipsec/identity',
        '/ip/ipsec/policy/group', '/ip/ipsec/policy']),
    ("other IP services", [
        '/ip/proxy', '/ip/smb', '/ip/socks', '/ip/upnp', '/ip/tftp', '/ip/traffic-flow',
        '/ip/kid-control', '/ip/media', '/ip/nat-pmp']),
    ("IPv6: settings -> addressing/nd -> dhcp -> firewall -> routes", [
        '/ipv6/settings', '/ipv6/address', '/ipv6/nd', '/ipv6/nd/prefix',
        '/ipv6/nd/prefix/default', '/ipv6/nd/proxy', '/ipv6/neighbor',
        '/ipv6/dhcp-client', '/ipv6/dhcp-client/option', '/ipv6/dhcp-relay',
        '/ipv6/dhcp-relay/option', '/ipv6/dhcp-server', '/ipv6/dhcp-server/option',
        '/ipv6/dhcp-server/option/sets', '/ipv6/dhcp-server/binding',
        '/ipv6/firewall/address-list', '/ipv6/firewall/filter', '/ipv6/firewall/nat',
        '/ipv6/firewall/mangle', '/ipv6/firewall/raw', '/ipv6/route']),
    ("routing: global -> instances -> areas/templates/neighbors -> filters", [
        '/routing/id', '/routing/settings', '/routing/bfd/configuration',
        '/routing/ospf/instance', '/routing/ospf/area', '/routing/ospf/area/range',
        '/routing/ospf/interface-template', '/routing/ospf/static-neighbor',
        '/routing/bgp/template', '/routing/bgp/connection', '/routing/bgp/instance',
        '/routing/bgp/aggregate', '/routing/bgp/network', '/routing/bgp/peer',
        '/routing/bgp/vpn', '/routing/bgp/vpls', '/routing/bgp/evpn',
        '/routing/rip/instance', '/routing/rip/interface-template', '/routing/rip/keys',
        '/routing/rip/static-neighbor', '/routing/rip', '/routing/ripng',
        '/routing/isis/instance', '/routing/isis/interface-template',
        '/routing/isis/interface', '/routing/isis/neighbor', '/routing/isis/lsp',
        '/routing/pimsm/instance', '/routing/pimsm/interface-template',
        '/routing/pimsm/igmp-interface-template', '/routing/pimsm/static-rp',
        '/routing/pimsm/bsr/candidate', '/routing/pimsm/bsr/rp-candidate',
        '/routing/igmp-proxy', '/routing/igmp-proxy/interface', '/routing/igmp-proxy/mfc',
        '/routing/gmp', '/routing/mme', '/routing/rpki', '/routing/fantasy',
        '/routing/filter/num-list', '/routing/filter/community-list',
        '/routing/filter/community-ext-list', '/routing/filter/community-large-list',
        '/routing/filter', '/routing/filter/rule', '/routing/filter/select-rule']),
    ("MPLS: settings/interface -> ldp -> traffic-eng", [
        '/mpls/settings', '/mpls', '/mpls/interface', '/mpls/ldp', '/mpls/ldp/interface',
        '/mpls/ldp/neighbor', '/mpls/ldp/accept-filter', '/mpls/ldp/advertise-filter',
        '/mpls/ldp/local-mapping', '/mpls/ldp/remote-mapping', '/mpls/mangle',
        '/mpls/traffic-eng/interface', '/mpls/traffic-eng/path', '/mpls/traffic-eng/tunnel']),
    ("queues (type before simple/tree/interface)", [
        '/queue/type', '/queue/simple', '/queue/tree', '/queue/interface']),
    ("monitoring / auth singletons", [
        '/snmp/community', '/snmp', '/radius', '/radius/incoming']),
    ("containers (config/envs/mounts referenced by the container)", [
        '/container/config', '/container/envs', '/container/mounts', '/container']),
    ("users (group before user)", [
        '/user/group', '/user/aaa', '/user/settings', '/user', '/user/ssh-keys']),
]

# Top-level order for the auto-appended leaf/independent paths.
TAIL_TOP = ['interface', 'ip', 'ipv6', 'routing', 'mpls', 'ppp', 'queue', 'snmp',
            'radius', 'certificate', 'caps-man', 'tool', 'system', 'user',
            'user-manager', 'container', 'disk', 'port', 'file', 'console',
            'special-login', 'task', 'partitions', 'rsync-daemon', 'tr069-client',
            'openflow', 'zerotier', 'app', 'lcd', 'lora', 'iot', 'dude']


def build():
    api = load_registry()
    configurable = {'/' + '/'.join(k) for k, a in api.PATHS.items()
                    if a.fully_understood and not a.modify_not_supported}
    spine = [p for _, ps in SECTIONS for p in ps]
    bad = [p for p in spine if p not in configurable]
    if bad:
        raise SystemExit("spine entries are not configurable api_modify paths:\n  "
                         + "\n  ".join(bad))
    if len(spine) != len(set(spine)):
        seen, dup = set(), set()
        for p in spine:
            (dup if p in seen else seen).add(p)
        raise SystemExit("duplicate spine entries: %s" % sorted(dup))

    def tailkey(p):
        seg = p.strip('/').split('/')
        top = seg[0]
        return (TAIL_TOP.index(top) if top in TAIL_TOP else len(TAIL_TOP), len(seg), p)

    tail = sorted(configurable - set(spine), key=tailkey)
    return spine, tail


def render(spine, tail):
    out = [
        "---",
        "# Canonical apply order for routeros_config paths. Only the RELATIVE order of",
        "# dependency-related paths matters; independent paths may sit anywhere, and any",
        "# path NOT listed here is applied last (in declared order). Keys are slash paths",
        "# (RouterOS notation), matching routeros_config keys.",
        "#",
        "# Covers every configurable path in community.routeros api_modify (the paths that",
        "# are fully understood and writable; read-only/status paths are intentionally",
        '# excluded). The leading sections are a hand-curated dependency spine (referenced',
        '# object before referencer; parent before child). The trailing "leaf / independent"',
        "# sections are paths with no cross-path dependency, ordered parent-first.",
        "#",
        "# GENERATED by extensions/tests/gen_path_order.py — edit SECTIONS there, not here.",
        "rcfg_path_order:",
    ]
    for comment, ps in SECTIONS:
        out.append(f"  # {comment}")
        out += [f"  - {p}" for p in ps]
    out.append("  # leaf / independent paths (no cross-path dependency; parent-first)")
    last = None
    for p in tail:
        top = p.strip('/').split('/')[0]
        if top != last:
            out.append(f"  # {top}")
            last = top
        out.append(f"  - {p}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if the vars file is out of date instead of writing it')
    args = ap.parse_args()
    spine, tail = build()
    content = render(spine, tail)
    if args.check:
        current = open(VARS).read() if os.path.exists(VARS) else ''
        if current != content:
            print("roles/configure/vars/main.yml is out of date; run "
                  "extensions/tests/gen_path_order.py", file=sys.stderr)
            return 1
        print(f"up to date ({len(spine) + len(tail)} paths)")
        return 0
    open(VARS, 'w').write(content)
    print(f"wrote {VARS}: spine={len(spine)} tail={len(tail)} total={len(spine) + len(tail)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
