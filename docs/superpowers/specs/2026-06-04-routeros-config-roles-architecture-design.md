# RouterOS Configuration Roles — Architecture Design

- **Date:** 2026-06-04
- **Status:** Approved (ready for implementation planning)
- **Collection:** `david_igou.routeros_configuration`

## Purpose

Provide a collection of thin, single-purpose Ansible roles that declaratively
manage the state of MikroTik RouterOS devices. Each role manages exactly one
RouterOS configuration path (one CLI menu, e.g. `/ip/firewall/filter`), modeled
after `redhat-cop/infra.aap_configuration` where each API endpoint is its own
role. State is expressed entirely through declared variables.

## Key decisions (locked during brainstorming)

| Decision | Choice |
|----------|--------|
| Transport | **Binary API** via `community.routeros.api_modify` (`connection: local`, port 8728/8729). NOT network_cli/CLI. |
| Engine | **Shared internal `_reconcile` role.** Subsystem roles are thin wrappers that `include_role` it. |
| v1 scope | **Vertical slice of 3 roles** spanning every pattern class, plus the engine. |
| Purge default | **Additive by default** (`handle_absent_entries: ignore`); per-role `_purge` toggle opts into exact-state. |
| Molecule | **One scenario per role**, each booting a fresh CHR. |
| Naming | Role name = full RouterOS path, `/`→`_`, space→`_`, **no abbreviation** (`ip_firewall_filter`, not `firewall_filter`). |

## Why `api_modify` is the foundation

`community.routeros.api_modify` is already a full declarative reconciliation
engine for ~450 config paths. Given a `path` and a `data` list of desired
entries, it computes and applies the diff idempotently. Relevant parameters:

- `path` — the config path (space-separated, e.g. `ip firewall filter`).
- `data` — the desired list of entry dicts.
- `handle_absent_entries` — `ignore` (default, additive) or `remove` (purge
  device entries not in `data` → exact-state). It ignores dynamic/built-in entries.
- `handle_entries_content` — `ignore` / `remove` / `remove_as_much_as_possible`
  (whether unspecified fields within a matched entry reset to default).
- `ensure_order` (bool) — enforce entry order to match `data` (matters for
  ordered paths like firewall rules). **Requires `handle_absent_entries: remove`.**
- Connection params: `hostname`, `username`, `password`, `tls` (true→8729,
  false→8728), `validate_certs`, `port`.

`community.routeros.api_info` is the read-only counterpart (same path enum) used
for drift detection and molecule `verify` (read state back, assert it matches).

## Architecture

```
Playbook
  └─ role: david_igou.routeros_configuration.ip_address
        defaults: routeros_ip_address: []   (+ _purge, _order toggles)
        tasks/main.yml ─ include_role: _reconcile
                              vars: rcfg_path: ip address
                                    rcfg_data: "{{ routeros_ip_address }}"
        └─ role: _reconcile
              connection: local
              community.routeros.api_modify:
                path: "{{ rcfg_path }}"
                data: "{{ rcfg_data }}"
                handle_absent_entries: "{{ rcfg_purge | ternary('remove','ignore') }}"
                ensure_order: "{{ rcfg_order }}"
                + hostname/username/password/tls from routeros_api_* vars
```

**Data flow:** user sets `routeros_<path>` vars (group_vars/host_vars) → subsystem
role forwards them to `_reconcile` → `api_modify` computes & applies the diff →
idempotent. Reads/drift use `api_info` at the same path.

### The `_reconcile` engine role

The single piece of real logic. Underscore prefix signals "internal, not a user
entrypoint."

- **Private inputs (`rcfg_*` namespace):** `rcfg_path`, `rcfg_data`,
  `rcfg_purge` (bool→`handle_absent_entries`), `rcfg_order` (bool→`ensure_order`),
  `rcfg_content` (→`handle_entries_content`, default `ignore`).
- **Shared connection vars (`routeros_api_*`):** `routeros_api_hostname`,
  `routeros_api_username`, `routeros_api_password`, `routeros_api_tls`,
  `routeros_api_validate_certs`, `routeros_api_port`. Configured once by the user;
  every role authenticates identically.
- **Behavior:** one `api_modify` task, `connection: local`, native check-mode and
  `--diff`. A guard assert enforces the `api_modify` constraint that
  `rcfg_order: true` implies `rcfg_purge: true`.

### Anatomy of a subsystem role (uniform)

```
roles/<full_path>/
  defaults/main.yml        routeros_<full_path>: []          # additive-safe default
                           routeros_<full_path>_purge: false # opt-in exact-state
                           routeros_<full_path>_order: false # ordered paths set true
  meta/argument_specs.yml  documents the entry list shape + options
  meta/main.yml            galaxy_info; no hard role dependency (engine included by name)
  tasks/main.yml           include_role: _reconcile  (maps the rcfg_* vars)
  README.md                path, example vars, purge caveat
```

### Naming convention

Role name = full RouterOS path with `/`→`_` and space→`_`, **no abbreviation**.
Var prefix matches the role name, prefixed `routeros_`.

| Role | Path | `api_modify` path arg | Primary var |
|------|------|----------------------|-------------|
| `system_identity` | `/system/identity` | `system identity` | `routeros_system_identity` |
| `ip_address` | `/ip/address` | `ip address` | `routeros_ip_address` |
| `ip_firewall_filter` | `/ip/firewall/filter` | `ip firewall filter` | `routeros_ip_firewall_filter` |

Future roles follow the same rule: `interface_bridge`, `interface_bridge_port`,
`interface_vlan`, `interface_list`, `interface_list_member`, `ip_dns`,
`ip_dhcp_server`, `ip_firewall_nat`, `ip_firewall_address_list`,
`system_ntp_client`, `snmp`, `interface_wireguard`, etc.

## v1 vertical slice

Three roles exercise the full engine surface; the rest become mechanical copies.

| Role | Path | Pattern class proven | Key toggle |
|------|------|----------------------|------------|
| `system_identity` | `system identity` | **singleton/settings** (single entry; no purge) | — |
| `ip_address` | `ip address` | **simple unordered list** | `_purge` |
| `ip_firewall_filter` | `ip firewall filter` | **ordered list** (rule order matters) | `_order` + `_purge` |

## Molecule strategy — one scenario per role

Each role gets `extensions/molecule/<role>/`, reusing the proven `chr` bootstrap
(`create`/`prepare`/`destroy`) factored into shared playbooks under
`extensions/molecule/utils/`. Per-scenario files differ only in:

- **`converge`** — apply the role with representative test data (`connection: local`,
  `routeros_api_*` pointed at the forwarded API port).
- **`verify`** — read state back via `api_info` and assert it matches the declared
  data, **plus a second converge asserting `changed == false`** (idempotency).
  For `_purge` roles, also assert that an entry removed from `data` is gone after
  a purge-enabled run; for ordered roles, assert order.

### API connectivity bootstrap (validated first in `system_identity`)

`api_modify` runs from the controller (`connection: local`) and reaches the CHR
over TCP, but the qemu provisioner only forwards a per-host SSH port
(`mp_qemu_slirp_port_base + index`, no extra-forward variable). So each scenario:

- **`create`/inventory:** adds one `extra_args` SLIRP netdev with
  `hostfwd=tcp::8728-:8728` (the API port).
- **`prepare`:** over the existing SSH bootstrap path, runs `/ip service enable api`
  and enables a `dhcp-client` on the API netdev's interface so the forwarded port
  reaches a live RouterOS address.

**Fallback** if hostfwd-to-secondary-interface is flaky: an `sshpass` SSH
local-forward tunnel established in `prepare`. Each scenario stays fully isolated
(fresh CHR per role).

## Directory layout

```
roles/
  _reconcile/              # shared engine
  system_identity/
  ip_address/
  ip_firewall_filter/
  # run/ scaffold is retired (pure placeholder)
extensions/molecule/
  chr/                     # existing feasibility spike (kept as reference)
  system_identity/  ip_address/  ip_firewall_filter/
  utils/                   # shared bootstrap playbooks (create/prepare/destroy)
```

## Out of scope (v1)

- The remaining ~18 high-value roles (mechanical follow-ups once the slice lands).
- CLI/network_cli fallback transport.
- A custom action/module plugin engine.
- Dynamic routing (OSPF/BGP), wireless, IPsec, queues — later phases.

## Risks / open technical detail

1. **API port forwarding through SLIRP** is the one unproven mechanic; it is the
   first thing validated in the `system_identity` scenario, with the SSH-tunnel
   fallback documented above.
2. **CHR default config** DHCPs only `ether1`; the API netdev's interface needs an
   explicit `dhcp-client` enable in `prepare`.
3. `api_modify`'s `ensure_order` requires `handle_absent_entries: remove`; the
   engine guards this with an assert so a misconfigured role fails loudly.
