# Interface / IP / Bridge Roles — Architecture Design

- **Date:** 2026-06-04
- **Status:** Approved (ready for implementation planning)
- **Collection:** `david_igou.routeros_configuration`
- **Builds on:** `2026-06-04-routeros-config-roles-architecture-design.md` (the `_reconcile`
  engine + the merged vertical slice). This spec extends that pattern; it does not change it.

## Purpose

Add declarative roles for the commonly-managed RouterOS `/interface`, `/ip`, and
`/interface/bridge` configuration paths. Each role is a thin wrapper around the
existing internal `_reconcile` engine — one role per `api_modify` path, exactly
like the merged `system_identity` / `ip_address` / `ip_firewall_filter` roles.

## Key decisions (locked during brainstorming)

| Decision | Choice |
|----------|--------|
| Breadth | **Curated practical set (~40 roles)** — paths a real admin manages. Excludes legacy wireless, wifi internals, ethernet-switch ACL/QoS internals, hotspot, ipsec, iot, dude. |
| Granularity | **One role per `api_modify` path** (child paths are their own roles, e.g. `ip_dhcp_server` vs `ip_dhcp_server_network`). |
| Testing | **One CHR molecule scenario per role** (keep the merged 1:1 convention). |
| Test infra | Shared `extensions/molecule/utils/` bootstrap, bumped to ~8 ether NICs. Each scenario creates its own prerequisites in `converge`. |
| CI | Extend the existing `molecule-qemu` matrix per plan; parallel jobs, `fail-fast: false`. |
| Decomposition | One spec (this doc); **three independently-shippable implementation plans / PRs**: Interface+bridge, IP core, IP firewall. |
| IPv6 | Out of scope (the user said "ip"; `/ipv6/*` is a later effort). |

## Reuse — no architecture change

Every role is the established skeleton:

```
roles/<full_path>/
  defaults/main.yml        routeros_<full_path>: []     (+ type-specific toggles)
  meta/argument_specs.yml  documents the entry list + options
  meta/main.yml            galaxy_info; dependencies: []
  tasks/main.yml           include_role: _reconcile  (maps rcfg_* vars)
  README.md                path, example vars, caveats
```

Role name = full RouterOS path, `/`→`_`, space→`_`, no abbreviation. User var =
`routeros_<role_name>`. Connection via the shared `routeros_api_*` vars. The
engine and its semantics (`rcfg_purge` → `handle_absent_entries`, `rcfg_order` →
`ensure_order`, `rcfg_content` → `handle_entries_content`) are unchanged.

### Type → defaults

| Type | Defaults | Notes |
|------|----------|-------|
| **list** | `routeros_<r>: []`, `routeros_<r>_purge: false` | additive; purge opt-in |
| **singleton** | `routeros_<r>: []` | settings path, single entry, no purge |
| **ordered** | list defaults + `routeros_<r>_order: false`, `routeros_<r>_content: remove_as_much_as_possible` | the `ip_firewall_filter` recipe |
| **modify-only list** | `routeros_<r>: []` (no `_purge`) | entries are built-in; only field-set, never add/remove (`interface_ethernet`, `ip_service`, `ip_firewall_service_port`) |

## Role inventory (~40 roles; `ip_address` and `ip_firewall_filter` already exist)

### Plan 1 — Interface + bridge (15 roles)

| Role | `api_modify` path | Type |
|------|-------------------|------|
| `interface_ethernet` | `interface ethernet` | modify-only list |
| `interface_bridge` | `interface bridge` | list |
| `interface_bridge_port` | `interface bridge port` | list |
| `interface_bridge_vlan` | `interface bridge vlan` | list |
| `interface_bridge_settings` | `interface bridge settings` | singleton |
| `interface_vlan` | `interface vlan` | list |
| `interface_bonding` | `interface bonding` | list |
| `interface_list` | `interface list` | list |
| `interface_list_member` | `interface list member` | list |
| `interface_vrrp` | `interface vrrp` | list |
| `interface_vxlan` | `interface vxlan` | list |
| `interface_wireguard` | `interface wireguard` | list |
| `interface_wireguard_peers` | `interface wireguard peers` | list |
| `interface_gre` | `interface gre` | list |
| `interface_eoip` | `interface eoip` | list |

### Plan 2 — IP core (16 new roles)

| Role | `api_modify` path | Type |
|------|-------------------|------|
| `ip_pool` | `ip pool` | list |
| `ip_dns` | `ip dns` | singleton |
| `ip_dns_static` | `ip dns static` | list |
| `ip_dhcp_server` | `ip dhcp-server` | list |
| `ip_dhcp_server_network` | `ip dhcp-server network` | list |
| `ip_dhcp_server_lease` | `ip dhcp-server lease` | list |
| `ip_dhcp_server_option` | `ip dhcp-server option` | list |
| `ip_dhcp_client` | `ip dhcp-client` | list |
| `ip_dhcp_relay` | `ip dhcp-relay` | list |
| `ip_route` | `ip route` | list |
| `ip_service` | `ip service` | modify-only list |
| `ip_arp` | `ip arp` | list |
| `ip_neighbor_discovery_settings` | `ip neighbor discovery-settings` | singleton |
| `ip_settings` | `ip settings` | singleton |
| `ip_cloud` | `ip cloud` | singleton |
| `ip_vrf` | `ip vrf` | list |
| `ip_ssh` | `ip ssh` | singleton |

(16 new roles. `ip_address` already exists and belongs to this group but is not re-listed.)

### Plan 3 — IP firewall (6 new roles)

| Role | `api_modify` path | Type |
|------|-------------------|------|
| `ip_firewall_nat` | `ip firewall nat` | ordered |
| `ip_firewall_mangle` | `ip firewall mangle` | ordered |
| `ip_firewall_raw` | `ip firewall raw` | ordered |
| `ip_firewall_address_list` | `ip firewall address-list` | list |
| `ip_firewall_connection_tracking` | `ip firewall connection tracking` | singleton |
| `ip_firewall_service_port` | `ip firewall service-port` | modify-only list |

## Testing

One molecule scenario per role under `extensions/molecule/<role>/`, reusing the
shared `utils/` bootstrap (create/prepare/destroy, inventory, `routeros_api_*`).
Each scenario: `converge` (create prerequisites, then apply the role with
representative data) → `idempotence` → `verify` (read back via `api_info`, assert
state; for list/ordered roles also assert purge/order as the merged scenarios do).

### Prerequisite chains (handled inside each scenario's `converge`)

Some paths require other objects to exist first; the scenario creates them before
applying the role under test:

- `interface_bridge_port`, `interface_bridge_vlan` → create a bridge first.
- `interface_vlan` → parent ether (use a spare NIC).
- `interface_bonding` → ≥2 free ethers as slaves.
- `interface_list_member` → create an interface list first.
- `interface_wireguard_peers` → create a wireguard interface first.
- `ip_dhcp_server` → an address + pool on a spare ether; `ip_dhcp_server_network`
  / `_lease` / `_option` → a dhcp-server first.
- `interface_vrrp`, `ip_arp`, `ip_dhcp_client`, `ip_dhcp_relay` → a spare ether.

### Shared CHR fixture

Bump `extensions/molecule/utils/inventory/hosts.yml` from the current 2 extra
NICs (apinet=ether2 + ether3/4) to **8 ethers** (ether1 SSH, ether2 API, ether3–8
spare) via additional SLIRP `-netdev`/`-device` `extra_args`, so interface,
bridge, bonding, and vlan scenarios have ports to bind. SLIRP user NICs need no
host L2 reachability — they only have to appear in RouterOS.

### CI

Extend the `molecule-qemu` matrix in `.github/workflows/tests.yml` with the new
scenarios as each plan lands. `fail-fast: false`; jobs run concurrently. End
state ≈ 44 matrix jobs. (`librouteros` is already installed; the `chr` and merged
role scenarios already pass.)

### `modify-only` test approach

For `interface_ethernet`, `ip_service`, `ip_firewall_service_port`: `converge`
sets a field on an existing built-in entry (e.g. `interface_ethernet` sets a
`comment`/`mtu` on `ether3`; `ip_service` sets `disabled`/`port` on `telnet`);
`verify` reads it back. No add/remove, no purge.

## Out of scope

- IPv6 (`/ipv6/*`), routing protocols (`/routing/*`), queues, tools, wireless/wifi,
  ipsec, hotspot, container, iot — later efforts.
- Changing the `_reconcile` engine or the connection contract.
- Cross-role orchestration / a top-level "configure everything" role (possible later).

## Risks / notes

1. **CI job count** (~44 molecule jobs). Accepted; parallel matrix keeps wall-time
   bounded, but watch GitHub concurrency limits — if jobs queue too long, a future
   option is grouping, deliberately deferred here.
2. **Prerequisite setup in scenarios** is the main new complexity vs the merged
   slice; each scenario must be self-contained and tear down cleanly (fresh CHR
   per scenario makes teardown free).
3. **Field schemas vary per path**; `argument_specs` documents each role's list as
   `list/elements: dict` (free-form), mirroring the merged roles — `api_modify`
   validates field names against the device, not the role.
