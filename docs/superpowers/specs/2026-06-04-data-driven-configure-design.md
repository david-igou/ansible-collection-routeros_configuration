# Data-Driven `configure` Role — Design

**Status:** Approved (brainstormed 2026-06-04)

**Supersedes:** the per-path role model from
`2026-06-04-routeros-config-roles-architecture-design.md` and
`2026-06-04-interface-ip-bridge-roles-design.md`. Those efforts proved the
reconciliation engine and the four pattern classes on real CHR hardware
(merged as PRs #1–#4); this design distils that proof into a form that scales to
hundreds of RouterOS paths **without per-path boilerplate**.

---

## Problem

The collection currently ships **41 user-facing roles** (~210 files), one per
RouterOS `api_modify` path. Each is a near-identical thin wrapper around the
internal `_reconcile` engine: a `tasks/main.yml` that calls `_reconcile` with a
`rcfg_path` and a `routeros_<name>` var, plus `defaults`, `meta/main`,
`meta/argument_specs`, and a `README`. Roughly **~200 of the 210 files are
boilerplate** following only **four shapes** (list, singleton, modify-only,
ordered).

RouterOS exposes hundreds of paths. Continuing one-role-per-path means
hand-authoring 5 files **and** a molecule scenario for every new path forever.
The growth cost — not the current 41 — is the problem.

## Goals

- Adding support for a new RouterOS path costs **zero role code** — data only.
- Collapse the public surface to a single declarative entrypoint.
- **Centralise cross-path dependency ordering** (pool → dhcp-server → lease,
  bridge → port, …), which the per-role model left implicit in playbooks and
  molecule prereqs.
- Keep the validated reconciliation behaviour and the shared-state molecule
  infrastructure already built.

## Non-goals

- Per-path `argument_specs` field validation. `api_modify` already validates
  field names against the device; `configure` validates only the input
  *structure*. (Accepted trade-off.)
- A named role per path. The data-driven entrypoint replaces them.
- Changing the `_reconcile` engine or the `routeros_api_*` connection contract.
- Back-compatibility shims. The collection is `0.0.1-alpha` with no consumers.

---

## Architecture

Two roles total:

```
roles/
  _reconcile/    # internal engine — reconciles ONE path (unchanged)
  configure/     # public entrypoint — loops _reconcile over routeros_config
                 # in a canonical dependency order
```

### `_reconcile` (unchanged)

The existing engine. Takes `rcfg_path`, `rcfg_data`, `rcfg_purge`, `rcfg_order`,
`rcfg_content`; asserts `rcfg_order` implies `rcfg_purge`; calls
`community.routeros.api_modify` for that one path with `delegate_to: localhost`,
`connection: local`. Connection comes from the shared `routeros_api_*` vars.

### `configure` (new public entrypoint)

`roles/configure/tasks/main.yml` — the whole role is two tasks: build the
ordered key list, then loop `_reconcile` over it, dereferencing each path's
options from `routeros_config`.

```yaml
---
# tasks file for david_igou.routeros_configuration.configure

# Requested paths, re-sorted into canonical dependency order: the paths that
# appear in rcfg_path_order first (in that order), then any remaining requested
# paths (dependency-independent) in declared order.
- name: Order the requested paths by dependency
  ansible.builtin.set_fact:
    rcfg_ordered_paths: >-
      {{ (rcfg_path_order | intersect(routeros_config.keys() | list))
         + (routeros_config.keys() | list | difference(rcfg_path_order)) }}

- name: "Reconcile {{ rcfg_key }}"
  ansible.builtin.include_role:
    name: _reconcile
  loop: "{{ rcfg_ordered_paths }}"
  loop_control:
    loop_var: rcfg_key
  vars:
    rcfg_path: "{{ rcfg_key }}"
    rcfg_data: "{{ routeros_config[rcfg_key].data }}"
    rcfg_purge: "{{ routeros_config[rcfg_key].purge | default(false) }}"
    rcfg_order: "{{ routeros_config[rcfg_key].order | default(false) }}"
    rcfg_content: "{{ routeros_config[rcfg_key].content | default('ignore') }}"
```

`rcfg_ordered_paths` is an ordered **list of path keys**; the loop dereferences
each path's options from `routeros_config[rcfg_key]`. Paths present in
`routeros_config` but absent from `rcfg_path_order` fall to the **end**, in
declared order — they are dependency-independent by assumption.

## Input contract

`routeros_config` — a dict keyed by the space-separated `api_modify` path. Each
value is a dict:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `data` | list of dict | **required** | desired entries for the path (passed to `api_modify.data`) |
| `purge` | bool | `false` | remove on-device entries not in `data` (`handle_absent_entries: remove`) |
| `order` | bool | `false` | enforce entry order (`ensure_order`); requires `purge: true` |
| `content` | str | `ignore` | `handle_entries_content`: `ignore` / `remove` / `remove_as_much_as_possible` |

```yaml
routeros_config:
  "ip pool":
    data:
      - name: lan
        ranges: "192.168.88.10-192.168.88.254"
  "ip dns":
    data:
      - servers: "1.1.1.1,8.8.8.8"
        allow-remote-requests: false
  "ip firewall filter":
    purge: true
    order: true
    data:
      - { chain: input, action: accept, connection-state: "established,related" }
      - { chain: input, action: accept, protocol: tcp, dst-port: "22,8728" }
      - { chain: input, action: drop }
```

`configure`'s `meta/argument_specs.yml` validates the **structure**:
`routeros_config` is a dict; each value has a required `data` list and optional
`purge`/`order` bool and `content` enum. Field names inside `data` are validated
by `api_modify` against the device, exactly as today.

## Ordering — two distinct concerns

### Within a path (handled by the module)

`api_modify`'s `ensure_order: true` (which requires `handle_absent_entries:
remove`) reconciles the on-device entry order to match the `data` list. This is
per-path and automatic — used by the ordered firewall paths. Exposed through the
`order` key. **No design work needed; the module owns this.**

### Across paths (owned by `configure`)

`api_modify` operates on **one path per call** and has **no cross-path
awareness**. RouterOS enforces referential integrity (it errors if you create an
object referencing a missing one), so dependent paths must be reconciled in
order: e.g. `ip pool` before `ip dhcp-server` before `ip dhcp-server lease`;
`interface bridge` before `interface bridge port`.

The per-role model left this to the consumer (role-call order) and to molecule
prereq tasks. `configure` instead owns a single canonical, dependency-sorted
list and applies `routeros_config` in that order regardless of how the dict was
authored or merged across `group_vars`/`host_vars`:

```yaml
# roles/configure/vars/main.yml
# Canonical apply order. Only the RELATIVE order of dependency-related paths
# matters; independent paths may sit anywhere, and any path NOT listed here is
# applied last (in declared order). Add a path here only when it must precede or
# follow another.
rcfg_path_order:
  # 1. interfaces (parents first)
  - interface ethernet
  - interface bonding
  - interface bridge
  - interface vlan
  - interface vxlan
  - interface gre
  - interface eoip
  - interface wireguard
  # 2. interface membership / sub-objects (need their parent above)
  - interface bridge settings
  - interface bridge port
  - interface bridge vlan
  - interface list
  - interface list member
  - interface wireguard peers
  - interface vrrp
  # 3. IP addressing (needs interfaces)
  - ip pool
  - ip address
  - ip arp
  - ip vrf
  # 4. IP services (dhcp-server needs pool + interface; lease/network/option need the server)
  - ip dhcp-server
  - ip dhcp-server network
  - ip dhcp-server option
  - ip dhcp-server lease
  - ip dhcp-client
  - ip dhcp-relay
  - ip dns
  - ip dns static
  - ip route
  - ip service
  - ip ssh
  - ip settings
  - ip cloud
  - ip neighbor discovery-settings
  # 5. firewall (address-list referenced by rules; rules ordered within their own chain)
  - ip firewall address-list
  - ip firewall connection tracking
  - ip firewall service-port
  - ip firewall filter
  - ip firewall nat
  - ip firewall mangle
  - ip firewall raw
  # system identity is order-independent; omitted -> applied last
```

This turns the dependency knowledge — previously scattered and untested — into
one reviewable list, and is the single most valuable thing `configure` adds over
the per-role model.

## Migration

The collection is alpha with no downstream consumers, so the 41 named roles are
**removed wholesale**:

- `git rm` all `roles/<name>/` except `roles/_reconcile/`.
- Add `roles/configure/`.
- `git rm` the 41 per-role molecule scenarios under `extensions/molecule/`;
  replace with the `configure_*` scenarios below.
- The shared-state molecule infrastructure (`default` scenario, `utils/`, the
  11-ether fixture, `config.yml`) is **kept unchanged**.
- The two prior plan docs remain as historical record; this spec supersedes
  them. Top-level `README.md` Roles tables collapse to document `configure` +
  the `routeros_config` schema, pointing at `community.routeros`'s path
  documentation rather than re-listing every path.
- Changelog: a `major_changes` (or `breaking_changes`, acceptable pre-1.0)
  fragment noting the per-path roles are replaced by the single `configure`
  role.

End state: **2 roles** (`_reconcile`, `configure`).

## Testing

The shared-state CHR infrastructure is unchanged. The 41 per-role scenarios are
replaced by ~5 scenarios that exercise `configure` across the pattern classes
**and** the cross-path ordering, each a single `configure` call →
`converge → idempotence → verify` on the shared CHR:

| Scenario | Proves |
|---|---|
| `configure_lists` | list apply + `purge` round-trip (pool, dns-static, address) |
| `configure_singletons` | singleton paths (dns, identity, settings) |
| `configure_ordered` | `purge`+`order` firewall (filter, nat) — on-device entry order |
| `configure_modify_only` | `fixed_entries` paths (ip service, interface ethernet) |
| `configure_dependency_chain` | one `routeros_config` containing `bridge→port`, `pool→dhcp-server→lease`, `list→member`, authored in **shuffled** key order; asserts all objects exist (canonical ordering worked) and the second converge is idempotent |

`configure_dependency_chain` is the scenario that locks in the cross-path
ordering guarantee the per-role model never tested. The same lockout-safety and
dedicated-port deconfliction rules from the shared-state work apply (these
scenarios still all run on the one shared CHR).

## Risks / notes

1. **Dict ordering under var merging.** Mitigated by `configure` re-sorting into
   `rcfg_path_order` rather than trusting dict insertion order — the central
   reason for the canonical list.
2. **Unlisted paths applied last.** A genuinely new path that has a dependency
   not yet in `rcfg_path_order` could apply out of order. Mitigation: adding a
   dependency edge to the list is a one-line change, and `configure_dependency_chain`
   plus real use will surface any gap. Independent paths (the common case) need
   no entry.
3. **Loss of per-path discoverability.** A consumer can no longer `ansible-doc`
   a `routeros_ip_pool` role. Mitigated by a documented `routeros_config` schema
   + examples and by `api_modify`'s own path docs. Accepted per the interface
   decision.
4. **`include_role` in a loop** re-includes `_reconcile` per item. Acceptable —
   it is how the per-role scenarios already invoked it, and the engine is tiny.
