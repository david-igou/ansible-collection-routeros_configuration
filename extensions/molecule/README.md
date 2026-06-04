# Molecule scenarios

Each scenario lives in its own subdirectory. Invoke from the **collection root**:

```bash
# Resolve runtime deps once, then run a scenario:
make molecule SCENARIO=chr

# Or directly (after `make install`), from the collection root:
MOLECULE_GLOB="extensions/molecule/*/molecule.yml" molecule test -s chr
```

`MOLECULE_GLOB` overrides molecule's default `molecule/<scenario>/` layout to
point at this collection's `extensions/molecule/<scenario>/` layout. Running
from the collection root also lets molecule auto-discover
`extensions/molecule/config.yml` (which only fires from the collection root, not
a scenario subdir).

## Deterministic collection resolution

- **Test-only** provisioner backends come from
  [`david_igou.molecule_provisioners`](https://galaxy.ansible.com/ui/repo/published/david_igou/molecule_provisioners/),
  pinned in `extensions/molecule/requirements-test.yml` and installed
  automatically by molecule's `dependency` step (configured in
  `extensions/molecule/config.yml`). It is **not** in the root `requirements.yml`,
  so consumers of this collection never auto-pull test tooling.
- **Runtime** deps (`community.routeros`, `ansible.netcommon`) come from the root
  `requirements.yml` / `galaxy.yml` and are installed by `make install` (which
  `make molecule` runs first).

No collection needs to be manually pre-installed: `make molecule SCENARIO=chr`
resolves everything.

## Scenarios

| Scenario | Backend | What it proves |
| --- | --- | --- |
| `chr` | qemu | A MikroTik CHR VM boots via the qemu provider and RouterOS is reachable over `community.routeros` (network_cli). See `chr/README.md`. |
| `system_identity` | qemu | The `system_identity` role applies a singleton `/system/identity` over the binary API; idempotent; verified via `api_info`. Also proves the shared API-over-SLIRP bootstrap (`utils/`). |
| `ip_address` | qemu | The `ip_address` role applies a list of `/ip/address` entries additively, and `_purge: true` removes entries dropped from the declared list. |
| `ip_firewall_filter` | qemu | The `ip_firewall_filter` role applies an ordered `/ip/firewall/filter` rule set with purge + order + content management; verify asserts on-device order. |

Scenarios `system_identity`, `ip_address`, `ip_firewall_filter`, and the 15
`interface_*` roles share their CHR bootstrap (create/prepare/destroy, inventory,
connection vars) from `extensions/molecule/utils/`. The provisioner wiring (and
the test_sequence + verifier) lives once in `extensions/molecule/config.yml` and
is merged into every scenario, so each subsystem scenario's `molecule.yml` is
reduced to just `scenario.name`; the per-scenario `converge.yml` / `verify.yml`
playbooks stay in the scenario directory (config.yml's relative paths resolve
against each scenario's own dir). (The `chr` scenario keeps its own `molecule.yml`
block because it uses a local inventory and create/destroy playbooks, and
`integration_hello_world` zeroes the inventory args; molecule's per-key merge
lets those override the shared defaults.) The binary API (port 8728) is exposed to the
controller through a dedicated SLIRP `hostfwd` on its own subnet, and the shared
host now provides 8 ether NICs (ether1 SSH, ether2 API, ether3–8 spare) so
interface/bridge/bonding/vlan scenarios have ports to bind — see
`utils/inventory/hosts.yml`. Each scenario creates any prerequisites (a bridge,
a list, a wireguard interface, …) in its own `converge`.

The 17 IP-core scenarios (`ip_pool`, `ip_dns`, `ip_dns_static`, the
`ip_dhcp_server`/`_network`/`_lease`/`_option` set, `ip_dhcp_client`,
`ip_dhcp_relay`, `ip_route`, `ip_service`, `ip_arp`,
`ip_neighbor_discovery_settings`, `ip_settings`, `ip_cloud`, `ip_vrf`, `ip_ssh`)
follow the same shape. The dhcp-server lease/server scenarios create their pool
and (disabled) server prerequisites in `converge` first; `ip_dhcp_client`,
`ip_dhcp_relay`, and `ip_dhcp_server` are created `disabled: true` because the
ephemeral CHR has no live DHCP segment; `ip_route` uses a `disabled` route with
an explicit gateway (stored without a reachable next hop, and idempotent — a
`blackhole` route is not); and `ip_service` only modifies the built-in `telnet`
entry so it never disturbs the SSH/API the harness depends on.
