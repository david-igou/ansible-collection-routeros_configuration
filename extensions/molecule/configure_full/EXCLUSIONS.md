# configure_full — path coverage & exclusions

`api_modify` exposes **523** paths. This CHR (7.21.4, bare VM) makes:

- **128 configurable** — of which **75 are exercised** by `configure_full`.
- **192 read-only / status** — not configurable (no write mechanism in the registry).
  Note: the probe's `writable()` heuristic only counts paths with
  primary_keys/single_value/fixed_entries, so it under-counts *keyless* paths
  (matched by content, like `/ip/firewall/nat`) as read-only. `configure_full`
  exercises several of these (`/ip/firewall/{nat,mangle,raw}`). `/ip/route` is
  also keyless but is **not idempotently reconcilable** on a bare CHR: with no
  primary key, a static route's read-back content differs from what was sent, so
  `api_modify` re-adds it on re-apply. It is therefore left out of this
  idempotence-checked scenario (verified empirically — `changed=1` on the second
  pass).
- **203 absent** — the feature/hardware/license is not present on a CHR.

Reproduce: boot the shared CHR, then `python3 extensions/molecule/utils/scripts/probe_paths.py`.

## Configurable but NOT exercised

| Path | Reason |
| --- | --- |
| `certificate settings` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `disk settings` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `interface 6to4` | tunnel — needs a live remote endpoint / server profile |
| `interface dot1x client` | 802.1x — needs supplicant/authenticator setup |
| `interface dot1x server` | 802.1x — needs supplicant/authenticator setup |
| `interface l2tp-client` | tunnel — needs a live remote endpoint / server profile |
| `interface l2tp-server server` | tunnel — needs a live remote endpoint / server profile |
| `interface ovpn-client` | tunnel — needs a live remote endpoint / server profile |
| `interface ppp-client` | tunnel — needs a live remote endpoint / server profile |
| `interface pppoe-client` | tunnel — needs a live remote endpoint / server profile |
| `interface pppoe-server server` | tunnel — needs a live remote endpoint / server profile |
| `interface pptp-server server` | tunnel — needs a live remote endpoint / server profile |
| `interface sstp-server server` | tunnel — needs a live remote endpoint / server profile |
| `ip cloud advanced` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip dhcp-client option` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip dhcp-server config` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip dhcp-server option sets` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip hotspot` | hotspot — needs an interface + profile setup chain |
| `ip hotspot profile` | hotspot — needs an interface + profile setup chain |
| `ip hotspot service-port` | hotspot — needs an interface + profile setup chain |
| `ip hotspot user` | hotspot — needs an interface + profile setup chain |
| `ip hotspot user profile` | hotspot — needs an interface + profile setup chain |
| `ip ipsec mode-config` | ipsec — multi-object chain (peer needs profile/proposal); not reconcilable as isolated entries on a bare CHR |
| `ip ipsec peer` | ipsec — multi-object chain (peer needs profile/proposal); not reconcilable as isolated entries on a bare CHR |
| `ip ipsec profile` | ipsec — multi-object chain (peer needs profile/proposal); not reconcilable as isolated entries on a bare CHR |
| `ip ipsec proposal` | ipsec — multi-object chain (peer needs profile/proposal); not reconcilable as isolated entries on a bare CHR |
| `ip ipsec settings` | ipsec — multi-object chain (peer needs profile/proposal); not reconcilable as isolated entries on a bare CHR |
| `ip tftp settings` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip traffic-flow ipfix` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ip upnp interfaces` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `ipv6 dhcp-client` | ipv6 DHCP/ND — needs an upstream PD / RA context |
| `ipv6 dhcp-server` | ipv6 DHCP/ND — needs an upstream PD / RA context |
| `ipv6 dhcp-server option` | ipv6 DHCP/ND — needs an upstream PD / RA context |
| `ipv6 nd` | ipv6 DHCP/ND — needs an upstream PD / RA context |
| `ppp aaa` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `queue interface` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `routing bgp template` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `routing igmp-proxy` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `routing igmp-proxy interface` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `routing ospf area range` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `routing pimsm instance` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `system clock manual` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `system ntp client servers` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `system ups` | needs a UPS device |
| `tool graphing` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `tool mac-server` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `tool mac-server mac-winbox` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `tool mac-server ping` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `tool sms` | needs a cellular modem |
| `tool sniffer` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `tool traffic-generator` | configurable but not authored in this pass (no representative idempotent value within the test budget) |
| `user` | policy field normalises to the full !-negated list on read-back (idempotence trap) |
| `user group` | policy field normalises to the full !-negated list on read-back (idempotence trap) |

## Absent on a CHR (need hardware/feature/license)

| Top-level | Count | Examples |
| --- | --- | --- |
| `app` | 2 | app, app settings |
| `caps-man` | 12 | caps-man aaa, caps-man access-list, caps-man actual-interface-configuration, caps-man channel … |
| `container` | 4 | container, container config, container envs, container mounts |
| `disk` | 3 | disk btrfs filesystem, disk btrfs subvolume, disk btrfs transfer |
| `dude` | 17 | dude, dude agent, dude device, dude device-type … |
| `file` | 2 | file rsync-daemon, file sync |
| `interface` | 73 | interface amt, interface bridge mlag, interface bridge port-controller, interface bridge port-controller device … |
| `iot` | 17 | iot bluetooth, iot bluetooth advertisers, iot bluetooth advertisers ad-structures, iot bluetooth peripheral-devices … |
| `ip` | 10 | ip accounting, ip accounting web-access, ip cloud back-to-home-file, ip cloud back-to-home-file settings … |
| `lcd` | 5 | lcd, lcd interface, lcd interface pages, lcd pin … |
| `lora` | 7 | lora, lora channels, lora joineui, lora netid … |
| `mpls` | 1 | mpls |
| `openflow` | 2 | openflow, openflow port |
| `partitions` | 1 | partitions |
| `port` | 1 | port firmware |
| `routing` | 11 | routing bfd interface, routing bgp aggregate, routing bgp network, routing bgp peer … |
| `rsync-daemon` | 1 | rsync-daemon |
| `system` | 15 | system gps, system hardware, system health settings, system resource irq rps … |
| `tool` | 1 | tool calea |
| `tr069-client` | 1 | tr069-client |
| `user-manager` | 13 | user-manager, user-manager advanced, user-manager attribute, user-manager database … |
| `zerotier` | 4 | zerotier, zerotier controller, zerotier controller member, zerotier interface |

## Read-only / status (not configurable)

`certificate` (4), `console` (1), `disk` (1), `file` (1), `interface` (48), `ip` (42), `ipv6` (11), `mpls` (13), `port` (2), `ppp` (1), `radius` (1), `routing` (38), `special-login` (1), `system` (13), `task` (1), `tool` (12), `user` (2)
