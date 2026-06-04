# IP Core Roles — Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 17 declarative `/ip` roles (the IP-core group), each a thin `_reconcile` wrapper with its own CHR molecule scenario, plus CI matrix entries and docs.

**Architecture:** Identical to the merged `system_identity`/`ip_address`/interface roles — each role maps a `routeros_<role>` var to the internal `_reconcile` engine which calls `community.routeros.api_modify` for one path. Roles are `list`, `singleton`, or `modify-only` typed (no ordered paths in this plan — ordered firewall paths are Plan 3). Provisioner wiring, `test_sequence`, and `verifier` are centralised in `extensions/molecule/config.yml`, so each new scenario's `molecule.yml` declares only its `scenario.name`. Each scenario boots a fresh CHR (shared `extensions/molecule/utils/` bootstrap), creates any prerequisites in `converge`, and verifies via `api_info`.

**Tech Stack:** Ansible roles, `community.routeros` 3.20.0 (`api_modify`/`api_info` + `librouteros`), molecule + `david_igou.molecule_provisioners` qemu, MikroTik CHR 7.21.4.

**Reference spec:** `docs/superpowers/specs/2026-06-04-interface-ip-bridge-roles-design.md` (§ "Plan 2 — IP core").

> **Scope note (count):** the spec's "Plan 2 — IP core" table lists **17** rows while its prose says "16 new roles"; the table is authoritative. This plan implements all 17: `ip_pool`, `ip_dns`, `ip_dns_static`, `ip_dhcp_server`, `ip_dhcp_server_network`, `ip_dhcp_server_lease`, `ip_dhcp_server_option`, `ip_dhcp_client`, `ip_dhcp_relay`, `ip_route`, `ip_service`, `ip_arp`, `ip_neighbor_discovery_settings`, `ip_settings`, `ip_cloud`, `ip_vrf`, `ip_ssh`. (`ip_address` already exists from Plan 1's slice and is not re-created.)

> **Path support pre-verified:** all 17 `api_modify` paths exist in the installed `community.routeros` 3.20.0 registry (`plugins/module_utils/_api_data.py`). Field names, primary keys, and required fields used in the converge/verify data below come from that registry — they are not guessed.

> **Fixture:** the shared CHR already exposes 8 ethers (ether1 SSH, ether2 API, ether3–8 spare) from Plan 1. **No fixture change is needed.** The scenarios below bind prerequisites on the spare ethers (ether3/ether5/ether6).

---

## Conventions (apply to every task)

- **No flow-style YAML.** Write all list/dict data as block YAML (`- key: val` on its own lines), never `- {key: val}`. This matches the merged convention.
- **Each role lives in `roles/<role>/`** with exactly five files: `defaults/main.yml`, `meta/main.yml`, `meta/argument_specs.yml`, `tasks/main.yml`, `README.md`.
- **Each scenario lives in `extensions/molecule/<role>/`** with three files: `molecule.yml`, `converge.yml`, `verify.yml`.
- **Run a scenario** with: `make molecule SCENARIO=<role>` (from the collection root). Expected for every scenario: CHR boots → `prepare` opens the API → `converge` applies → `idempotence` reports **no changes** on the second converge → `verify` asserts state via `api_info` → `destroy` tears down. The whole run must PASS.
- **Disabled-by-default for runtime-affecting entries.** dhcp-client, dhcp-relay, and the dhcp-server are created with `disabled: true` so the ephemeral CHR doesn't start handing out leases or racing DHCP; the test only proves declarative apply + read-back, not live DHCP.
- **Never disable the management services.** `ip_service` modifies only the built-in `telnet` entry. Do **not** touch `ssh`, `api`, `www`, or `ftp` — the harness reaches the device over SSH (prepare) and the API (8728).

---

## Templates (used by every role task below)

Four files are pure boilerplate produced from a template with substitutions. Each role task names its substitutions; produce the file by substituting into the template here.

### Template `meta/main.yml` (substitute `<DESC>`, `<TAG3>`)

```yaml
---
galaxy_info:
  author: David Igou
  description: <DESC>
  company: david_igou
  license: GPL-2.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - <TAG3>
dependencies: []
```

### Template `README.md` (substitute `<ROLE>`, `<PATH_SLASH>`, `<EXAMPLE>`)

`<PATH_SLASH>` is the slash form (e.g. `/ip/pool`). `<EXAMPLE>` is the role's
representative var block, indented 4 spaces.

```markdown
# <ROLE>

Declaratively manage `<PATH_SLASH>` over the RouterOS API.

    <EXAMPLE>

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
```

### Template `tasks/main.yml` — **list** type (substitute `<ROLE>`, `<PATH_SPACE>`)

`<PATH_SPACE>` is the space-separated `api_modify` path (e.g. `ip pool`).

```yaml
---
# tasks file for david_igou.routeros_configuration.<ROLE>
- name: "Reconcile <PATH_SPACE>"
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: <PATH_SPACE>
    rcfg_data: "{{ routeros_<ROLE> }}"
    rcfg_purge: "{{ routeros_<ROLE>_purge | default(false) }}"
    rcfg_order: false
```

### Template `tasks/main.yml` — **singleton** and **modify-only** types (substitute `<ROLE>`, `<PATH_SPACE>`)

Identical to the list template but with `rcfg_purge: false` hard-coded —
singletons have nothing to purge, and modify-only paths use `fixed_entries`
(entries can't be added/removed, only modified).

```yaml
---
# tasks file for david_igou.routeros_configuration.<ROLE>
- name: "Reconcile <PATH_SPACE>"
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: <PATH_SPACE>
    rcfg_data: "{{ routeros_<ROLE> }}"
    rcfg_purge: false
    rcfg_order: false
```

### Template `molecule.yml` (substitute `<ROLE>`)

Provisioner wiring, `test_sequence`, and `verifier` are centralised in
`extensions/molecule/config.yml`; the per-scenario file is name-only.

```yaml
---
# Provisioner wiring, test_sequence, and verifier are centralised in
# extensions/molecule/config.yml and merged in by molecule. This file declares
# only the scenario name.
scenario:
  name: <ROLE>
```

### Template — **list verify** (read-back + assert present)

Most list scenarios use this shape; the per-task verify gives the exact path and
assertion. The `_purge` round-trip is exercised only where the task says so.

---

## Task 1: `ip_pool` (list)

**Files:**
- Create: `roles/ip_pool/defaults/main.yml`, `roles/ip_pool/meta/main.yml`, `roles/ip_pool/meta/argument_specs.yml`, `roles/ip_pool/tasks/main.yml`, `roles/ip_pool/README.md`
- Create: `extensions/molecule/ip_pool/molecule.yml`, `extensions/molecule/ip_pool/converge.yml`, `extensions/molecule/ip_pool/verify.yml`

- [ ] **Step 1: Write `roles/ip_pool/defaults/main.yml`**

```yaml
---
# List of /ip/pool entries, e.g.:
#   - name: lan-pool
#     ranges: "192.168.88.10-192.168.88.254"
routeros_ip_pool: []
# Set true to delete pools not present above (exact-state).
routeros_ip_pool_purge: false
```

- [ ] **Step 2: Write `roles/ip_pool/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/pool entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_pool/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/pool declaratively.
    options:
      routeros_ip_pool:
        type: list
        elements: dict
        default: []
        description: IP pool entries (name, ranges, next-pool).
      routeros_ip_pool_purge:
        type: bool
        default: false
        description: Remove pools not present in routeros_ip_pool.
```

- [ ] **Step 4: Write `roles/ip_pool/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_pool`, `<PATH_SPACE>` = `ip pool`.

- [ ] **Step 5: Write `roles/ip_pool/README.md`** from the **README template** with `<ROLE>` = `ip_pool`, `<PATH_SLASH>` = `/ip/pool`, `<EXAMPLE>` =

```
routeros_ip_pool:
      - name: lan-pool
        ranges: "192.168.88.10-192.168.88.254"
    routeros_ip_pool_purge: true   # optional: exact-state
```

- [ ] **Step 6: Write `extensions/molecule/ip_pool/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_pool`.

- [ ] **Step 7: Write `extensions/molecule/ip_pool/converge.yml`**

```yaml
---
- name: Converge — create two IP pools
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_pool:
      - name: pool-a
        ranges: "192.168.60.10-192.168.60.50"
      - name: pool-b
        ranges: "192.168.61.10-192.168.61.50"
  roles:
    - role: david_igou.routeros_configuration.ip_pool
```

- [ ] **Step 8: Write `extensions/molecule/ip_pool/verify.yml`** (additive read-back, then purge round-trip)

```yaml
---
- name: Verify — ip_pool apply + purge semantics
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/pool after additive converge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pool_before

    - name: Assert both declared pools are present
      ansible.builtin.assert:
        that:
          - pool_before.result | selectattr('name', 'equalto', 'pool-a') | list | length == 1
          - pool_before.result | selectattr('name', 'equalto', 'pool-b') | list | length == 1

    - name: Re-apply with a reduced list and purge enabled
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ip_pool
      vars:
        routeros_ip_pool:
          - name: pool-a
            ranges: "192.168.60.10-192.168.60.50"
        routeros_ip_pool_purge: true

    - name: Read /ip/pool after purge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pool_after

    - name: Assert pool-b was purged and pool-a remains
      ansible.builtin.assert:
        that:
          - pool_after.result | selectattr('name', 'equalto', 'pool-a') | list | length == 1
          - pool_after.result | selectattr('name', 'equalto', 'pool-b') | list | length == 0
        success_msg: "purge removed pool-b, kept pool-a"
        fail_msg: "purge did not behave as expected: {{ pool_after.result }}"
```

- [ ] **Step 9: Run the scenario**

Run: `make molecule SCENARIO=ip_pool`
Expected: PASSES — converge creates both pools, idempotence clean, verify confirms additive then purge.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_pool extensions/molecule/ip_pool
git commit -m "feat(ip_pool): declarative /ip/pool role + molecule scenario"
```

---

## Task 2: `ip_dns` (singleton)

**Files:**
- Create: `roles/ip_dns/{defaults,meta,tasks}/...`, `roles/ip_dns/README.md`
- Create: `extensions/molecule/ip_dns/{molecule,converge,verify}.yml`

- [ ] **Step 1: Write `roles/ip_dns/defaults/main.yml`**

```yaml
---
# /ip/dns is a singleton path. Provide a single-element list with the desired
# settings, e.g. [{servers: "1.1.1.1,8.8.8.8", allow-remote-requests: false}].
# Empty -> no change.
routeros_ip_dns: []
```

- [ ] **Step 2: Write `roles/ip_dns/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dns settings (singleton).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dns/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dns declaratively (singleton).
    options:
      routeros_ip_dns:
        type: list
        elements: dict
        default: []
        description: Single-element list of DNS settings (servers, ...).
```

- [ ] **Step 4: Write `roles/ip_dns/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_dns`, `<PATH_SPACE>` = `ip dns`.

- [ ] **Step 5: Write `roles/ip_dns/README.md`** from the **README template** with `<ROLE>` = `ip_dns`, `<PATH_SLASH>` = `/ip/dns`, `<EXAMPLE>` =

```
routeros_ip_dns:
      - servers: "1.1.1.1,8.8.8.8"
        allow-remote-requests: false
```

- [ ] **Step 6: Write `extensions/molecule/ip_dns/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dns`.

- [ ] **Step 7: Write `extensions/molecule/ip_dns/converge.yml`**

```yaml
---
- name: Converge — set DNS servers
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dns:
      - servers: "1.1.1.1,8.8.8.8"
        allow-remote-requests: false
  roles:
    - role: david_igou.routeros_configuration.ip_dns
```

- [ ] **Step 8: Write `extensions/molecule/ip_dns/verify.yml`**

```yaml
---
- name: Verify — /ip/dns reflects declared servers
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dns over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dns
      delegate_to: localhost
      connection: local
      register: dns

    - name: Assert the DNS servers were applied
      ansible.builtin.assert:
        that:
          - dns.result | selectattr('servers', 'search', '1.1.1.1') | list | length == 1
        success_msg: "dns servers applied: {{ dns.result | map(attribute='servers') | list }}"
        fail_msg: "unexpected dns settings: {{ dns.result }}"
```

- [ ] **Step 9: Run the scenario**

Run: `make molecule SCENARIO=ip_dns`
Expected: PASSES — converge sets the servers, idempotence clean, verify confirms.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dns extensions/molecule/ip_dns
git commit -m "feat(ip_dns): declarative /ip/dns role + molecule scenario"
```

---

## Task 3: `ip_dns_static` (list)

**Files:** `roles/ip_dns_static/...` + `extensions/molecule/ip_dns_static/...`

- [ ] **Step 1: Write `roles/ip_dns_static/defaults/main.yml`**

```yaml
---
# List of /ip/dns/static entries, e.g.:
#   - name: router.lan
#     address: "192.168.88.1"
routeros_ip_dns_static: []
routeros_ip_dns_static_purge: false
```

- [ ] **Step 2: Write `roles/ip_dns_static/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dns/static records.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dns_static/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dns/static declaratively.
    options:
      routeros_ip_dns_static:
        type: list
        elements: dict
        default: []
        description: Static DNS records (name, address, cname, type, ...).
      routeros_ip_dns_static_purge:
        type: bool
        default: false
        description: Remove records not present in routeros_ip_dns_static.
```

- [ ] **Step 4: Write `roles/ip_dns_static/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dns_static`, `<PATH_SPACE>` = `ip dns static`.

- [ ] **Step 5: Write `roles/ip_dns_static/README.md`** from the **README template** with `<ROLE>` = `ip_dns_static`, `<PATH_SLASH>` = `/ip/dns/static`, `<EXAMPLE>` =

```
routeros_ip_dns_static:
      - name: router.lan
        address: "192.168.88.1"
```

- [ ] **Step 6: Write `extensions/molecule/ip_dns_static/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dns_static`.

- [ ] **Step 7: Write `extensions/molecule/ip_dns_static/converge.yml`**

```yaml
---
- name: Converge — add static DNS records
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dns_static:
      - name: router.lan
        address: "192.168.88.1"
      - name: nas.lan
        address: "192.168.88.2"
  roles:
    - role: david_igou.routeros_configuration.ip_dns_static
```

- [ ] **Step 8: Write `extensions/molecule/ip_dns_static/verify.yml`**

```yaml
---
- name: Verify — static DNS records present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dns/static over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dns static
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert both records are present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'router.lan') | list | length == 1
          - q.result | selectattr('name', 'equalto', 'nas.lan') | list | length == 1
        fail_msg: "unexpected static DNS records: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dns_static` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dns_static extensions/molecule/ip_dns_static
git commit -m "feat(ip_dns_static): declarative /ip/dns/static role + molecule scenario"
```

---

## Task 4: `ip_route` (list)

> **Note:** `/ip/route` has no primary key in the registry; `api_modify` matches on the full entry. Use a **`disabled: true`** route with an explicit gateway (stored verbatim without a reachable next hop) and leave purge **off** — purging routes on a live device can remove connected/default routes.
>
> **Do NOT use a `blackhole` route here:** it is not idempotent under `api_modify`. RouterOS stores the blackhole flag as the empty string `""` while the module sends `true`, so every re-converge reports a change and the molecule `idempotence` step fails. (Verified on CHR 7.21.4.)

**Files:** `roles/ip_route/...` + `extensions/molecule/ip_route/...`

- [ ] **Step 1: Write `roles/ip_route/defaults/main.yml`**

```yaml
---
# List of /ip/route entries, e.g.:
#   - dst-address: "10.0.0.0/8"
#     gateway: "192.168.88.254"
routeros_ip_route: []
# Purge is OFF by default and not recommended for routes: exact-state would
# remove connected/dynamic routes. Enable only with a complete static list.
routeros_ip_route_purge: false
```

- [ ] **Step 2: Write `roles/ip_route/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/route static routes.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_route/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/route declaratively.
    options:
      routeros_ip_route:
        type: list
        elements: dict
        default: []
        description: Static route entries (dst-address, gateway, distance, ...).
      routeros_ip_route_purge:
        type: bool
        default: false
        description: Remove routes not present in routeros_ip_route (use with care).
```

- [ ] **Step 4: Write `roles/ip_route/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_route`, `<PATH_SPACE>` = `ip route`.

- [ ] **Step 5: Write `roles/ip_route/README.md`** from the **README template** with `<ROLE>` = `ip_route`, `<PATH_SLASH>` = `/ip/route`, `<EXAMPLE>` =

```
routeros_ip_route:
      - dst-address: "10.0.0.0/8"
        gateway: "192.168.88.254"
```

- [ ] **Step 6: Write `extensions/molecule/ip_route/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_route`.

- [ ] **Step 7: Write `extensions/molecule/ip_route/converge.yml`**

```yaml
---
- name: Converge — add a disabled static route
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_route:
      - dst-address: "10.99.0.0/24"
        gateway: "192.0.2.1"
        disabled: true
        comment: "route-test"
  roles:
    - role: david_igou.routeros_configuration.ip_route
```

- [ ] **Step 8: Write `extensions/molecule/ip_route/verify.yml`**

```yaml
---
- name: Verify — static route present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/route over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip route
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the static route was added
      ansible.builtin.assert:
        that:
          - q.result | selectattr('comment', 'defined') | selectattr('comment', 'equalto', 'route-test') | list | length == 1
        fail_msg: "route-test not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_route` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_route extensions/molecule/ip_route
git commit -m "feat(ip_route): declarative /ip/route role + molecule scenario"
```

---

## Task 5: `ip_service` (modify-only)

> **Modify-only:** `/ip/service` is `fixed_entries` — you cannot add or remove services, only modify the built-in ones (telnet, ftp, www, ssh, api, ...). `converge` sets a field on the built-in **`telnet`** entry (safe; the harness never uses telnet). Purge is off.

**Files:** `roles/ip_service/...` + `extensions/molecule/ip_service/...`

- [ ] **Step 1: Write `roles/ip_service/defaults/main.yml`**

```yaml
---
# Modify-only list of /ip/service entries (built-in services keyed by name).
# Cannot add/remove; only change fields like disabled/port, e.g.:
#   - name: telnet
#     disabled: true
routeros_ip_service: []
```

- [ ] **Step 2: Write `roles/ip_service/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/service (modify-only).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_service/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/service declaratively (modify-only).
    options:
      routeros_ip_service:
        type: list
        elements: dict
        default: []
        description: Built-in service entries to modify (name, disabled, port, ...).
```

- [ ] **Step 4: Write `roles/ip_service/tasks/main.yml`** from the **singleton/modify-only tasks template** with `<ROLE>` = `ip_service`, `<PATH_SPACE>` = `ip service`.

- [ ] **Step 5: Write `roles/ip_service/README.md`** from the **README template** with `<ROLE>` = `ip_service`, `<PATH_SLASH>` = `/ip/service`, `<EXAMPLE>` =

```
routeros_ip_service:
      - name: telnet
        disabled: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_service/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_service`.

- [ ] **Step 7: Write `extensions/molecule/ip_service/converge.yml`**

```yaml
---
- name: Converge — disable the built-in telnet service
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_service:
      - name: telnet
        disabled: true
  roles:
    - role: david_igou.routeros_configuration.ip_service
```

- [ ] **Step 8: Write `extensions/molecule/ip_service/verify.yml`**

```yaml
---
- name: Verify — telnet service disabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/service over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip service
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert telnet is disabled
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'telnet') | selectattr('disabled', 'equalto', true) | list | length == 1
        fail_msg: "telnet not disabled: {{ q.result | selectattr('name','equalto','telnet') | list }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_service` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_service extensions/molecule/ip_service
git commit -m "feat(ip_service): declarative /ip/service role + molecule scenario (modify-only)"
```

---

## Task 6: `ip_arp` (list)

> **Prereq:** static ARP entries require an interface. Bind on the spare **ether3** (exists in the shared fixture); no IP address is needed for a static ARP entry.

**Files:** `roles/ip_arp/...` + `extensions/molecule/ip_arp/...`

- [ ] **Step 1: Write `roles/ip_arp/defaults/main.yml`**

```yaml
---
# List of /ip/arp entries, e.g.:
#   - address: "192.168.88.10"
#     mac-address: "00:11:22:33:44:55"
#     interface: ether1
routeros_ip_arp: []
routeros_ip_arp_purge: false
```

- [ ] **Step 2: Write `roles/ip_arp/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/arp static entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_arp/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/arp declaratively.
    options:
      routeros_ip_arp:
        type: list
        elements: dict
        default: []
        description: Static ARP entries (address, mac-address, interface, ...).
      routeros_ip_arp_purge:
        type: bool
        default: false
        description: Remove ARP entries not present in routeros_ip_arp.
```

- [ ] **Step 4: Write `roles/ip_arp/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_arp`, `<PATH_SPACE>` = `ip arp`.

- [ ] **Step 5: Write `roles/ip_arp/README.md`** from the **README template** with `<ROLE>` = `ip_arp`, `<PATH_SLASH>` = `/ip/arp`, `<EXAMPLE>` =

```
routeros_ip_arp:
      - address: "192.168.88.10"
        mac-address: "00:11:22:33:44:55"
        interface: ether1
```

- [ ] **Step 6: Write `extensions/molecule/ip_arp/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_arp`.

- [ ] **Step 7: Write `extensions/molecule/ip_arp/converge.yml`**

```yaml
---
- name: Converge — add a static ARP entry on ether3
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_arp:
      - address: "192.168.50.5"
        mac-address: "00:11:22:33:44:55"
        interface: ether3
  roles:
    - role: david_igou.routeros_configuration.ip_arp
```

- [ ] **Step 8: Write `extensions/molecule/ip_arp/verify.yml`**

```yaml
---
- name: Verify — static ARP entry present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/arp over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip arp
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the static ARP entry was added
      ansible.builtin.assert:
        that:
          - q.result | selectattr('address', 'equalto', '192.168.50.5') | selectattr('mac-address', 'equalto', '00:11:22:33:44:55') | list | length == 1
        fail_msg: "static ARP not found: {{ q.result | selectattr('address','equalto','192.168.50.5') | list }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_arp` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_arp extensions/molecule/ip_arp
git commit -m "feat(ip_arp): declarative /ip/arp role + molecule scenario"
```

---

## Task 7: `ip_vrf` (list)

**Files:** `roles/ip_vrf/...` + `extensions/molecule/ip_vrf/...`

- [ ] **Step 1: Write `roles/ip_vrf/defaults/main.yml`**

```yaml
---
# List of /ip/vrf entries, e.g.:
#   - name: mgmt
#     interfaces: ether5
routeros_ip_vrf: []
routeros_ip_vrf_purge: false
```

- [ ] **Step 2: Write `roles/ip_vrf/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/vrf instances.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_vrf/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/vrf declaratively.
    options:
      routeros_ip_vrf:
        type: list
        elements: dict
        default: []
        description: VRF instances (name, interfaces, ...).
      routeros_ip_vrf_purge:
        type: bool
        default: false
        description: Remove VRFs not present in routeros_ip_vrf.
```

- [ ] **Step 4: Write `roles/ip_vrf/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_vrf`, `<PATH_SPACE>` = `ip vrf`.

- [ ] **Step 5: Write `roles/ip_vrf/README.md`** from the **README template** with `<ROLE>` = `ip_vrf`, `<PATH_SLASH>` = `/ip/vrf`, `<EXAMPLE>` =

```
routeros_ip_vrf:
      - name: mgmt
        interfaces: ether5
```

- [ ] **Step 6: Write `extensions/molecule/ip_vrf/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_vrf`.

- [ ] **Step 7: Write `extensions/molecule/ip_vrf/converge.yml`**

```yaml
---
- name: Converge — create a VRF bound to ether6
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_vrf:
      - name: vrf-test
        interfaces: ether6
  roles:
    - role: david_igou.routeros_configuration.ip_vrf
```

- [ ] **Step 8: Write `extensions/molecule/ip_vrf/verify.yml`**

```yaml
---
- name: Verify — VRF present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/vrf over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip vrf
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the VRF was created
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'vrf-test') | list | length == 1
        fail_msg: "vrf-test not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_vrf` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_vrf extensions/molecule/ip_vrf
git commit -m "feat(ip_vrf): declarative /ip/vrf role + molecule scenario"
```

---

## Task 8: `ip_settings` (singleton)

**Files:** `roles/ip_settings/...` + `extensions/molecule/ip_settings/...`

- [ ] **Step 1: Write `roles/ip_settings/defaults/main.yml`**

```yaml
---
# /ip/settings is a singleton path. Single-element list of global IP settings,
# e.g. [{ip-forward: true}]. Empty -> no change.
routeros_ip_settings: []
```

- [ ] **Step 2: Write `roles/ip_settings/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/settings (singleton).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_settings/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/settings declaratively (singleton).
    options:
      routeros_ip_settings:
        type: list
        elements: dict
        default: []
        description: Single-element list of global IP settings (ip-forward, ...).
```

- [ ] **Step 4: Write `roles/ip_settings/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_settings`, `<PATH_SPACE>` = `ip settings`.

- [ ] **Step 5: Write `roles/ip_settings/README.md`** from the **README template** with `<ROLE>` = `ip_settings`, `<PATH_SLASH>` = `/ip/settings`, `<EXAMPLE>` =

```
routeros_ip_settings:
      - ip-forward: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_settings/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_settings`.

- [ ] **Step 7: Write `extensions/molecule/ip_settings/converge.yml`**

```yaml
---
- name: Converge — set a global IP setting
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_settings:
      - tcp-syncookies: true
  roles:
    - role: david_igou.routeros_configuration.ip_settings
```

- [ ] **Step 8: Write `extensions/molecule/ip_settings/verify.yml`**

```yaml
---
- name: Verify — tcp-syncookies enabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/settings over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip settings
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert tcp-syncookies is enabled
      ansible.builtin.assert:
        that:
          - q.result | selectattr('tcp-syncookies', 'equalto', true) | list | length == 1
        fail_msg: "ip settings unexpected: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_settings` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_settings extensions/molecule/ip_settings
git commit -m "feat(ip_settings): declarative /ip/settings role + molecule scenario"
```

---

## Task 9: `ip_cloud` (singleton)

> Use `update-time: false` (a safe, offline-applicable toggle). The CHR has no internet in CI; we only prove the setting is applied and read back, not live DDNS.

**Files:** `roles/ip_cloud/...` + `extensions/molecule/ip_cloud/...`

- [ ] **Step 1: Write `roles/ip_cloud/defaults/main.yml`**

```yaml
---
# /ip/cloud is a singleton path. Single-element list, e.g.
# [{ddns-update-interval: "none"}]. Empty -> no change.
routeros_ip_cloud: []
```

- [ ] **Step 2: Write `roles/ip_cloud/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/cloud (singleton).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_cloud/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/cloud declaratively (singleton).
    options:
      routeros_ip_cloud:
        type: list
        elements: dict
        default: []
        description: Single-element list of cloud/DDNS settings.
```

- [ ] **Step 4: Write `roles/ip_cloud/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_cloud`, `<PATH_SPACE>` = `ip cloud`.

- [ ] **Step 5: Write `roles/ip_cloud/README.md`** from the **README template** with `<ROLE>` = `ip_cloud`, `<PATH_SLASH>` = `/ip/cloud`, `<EXAMPLE>` =

```
routeros_ip_cloud:
      - ddns-update-interval: "none"
        update-time: false
```

- [ ] **Step 6: Write `extensions/molecule/ip_cloud/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_cloud`.

- [ ] **Step 7: Write `extensions/molecule/ip_cloud/converge.yml`**

```yaml
---
- name: Converge — set ip cloud update-time off
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_cloud:
      - update-time: false
  roles:
    - role: david_igou.routeros_configuration.ip_cloud
```

- [ ] **Step 8: Write `extensions/molecule/ip_cloud/verify.yml`**

```yaml
---
- name: Verify — ip cloud update-time off
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/cloud over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip cloud
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert update-time is false
      ansible.builtin.assert:
        that:
          - q.result | selectattr('update-time', 'equalto', false) | list | length == 1
        fail_msg: "ip cloud unexpected: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_cloud` — PASSES.

> If `idempotence` flags a change (some ROS builds normalise `update-time`), switch the converge/verify field to `ddns-update-interval: "none"` and assert that instead — both are safe offline.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_cloud extensions/molecule/ip_cloud
git commit -m "feat(ip_cloud): declarative /ip/cloud role + molecule scenario"
```

---

## Task 10: `ip_ssh` (singleton)

> Safe to change post-`prepare`: the harness uses SSH only during create/prepare; `converge`/`verify` use the binary API (8728).

**Files:** `roles/ip_ssh/...` + `extensions/molecule/ip_ssh/...`

- [ ] **Step 1: Write `roles/ip_ssh/defaults/main.yml`**

```yaml
---
# /ip/ssh is a singleton path. Single-element list, e.g.
# [{strong-crypto: true}]. Empty -> no change.
routeros_ip_ssh: []
```

- [ ] **Step 2: Write `roles/ip_ssh/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/ssh (singleton).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_ssh/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/ssh declaratively (singleton).
    options:
      routeros_ip_ssh:
        type: list
        elements: dict
        default: []
        description: Single-element list of SSH server settings.
```

- [ ] **Step 4: Write `roles/ip_ssh/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_ssh`, `<PATH_SPACE>` = `ip ssh`.

- [ ] **Step 5: Write `roles/ip_ssh/README.md`** from the **README template** with `<ROLE>` = `ip_ssh`, `<PATH_SLASH>` = `/ip/ssh`, `<EXAMPLE>` =

```
routeros_ip_ssh:
      - strong-crypto: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_ssh/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_ssh`.

- [ ] **Step 7: Write `extensions/molecule/ip_ssh/converge.yml`**

```yaml
---
- name: Converge — enable strong-crypto on the SSH server
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_ssh:
      - strong-crypto: true
  roles:
    - role: david_igou.routeros_configuration.ip_ssh
```

- [ ] **Step 8: Write `extensions/molecule/ip_ssh/verify.yml`**

```yaml
---
- name: Verify — strong-crypto enabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/ssh over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip ssh
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert strong-crypto is enabled
      ansible.builtin.assert:
        that:
          - q.result | selectattr('strong-crypto', 'equalto', true) | list | length == 1
        fail_msg: "ip ssh unexpected: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_ssh` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_ssh extensions/molecule/ip_ssh
git commit -m "feat(ip_ssh): declarative /ip/ssh role + molecule scenario"
```

---

## Task 11: `ip_neighbor_discovery_settings` (singleton)

**Files:** `roles/ip_neighbor_discovery_settings/...` + `extensions/molecule/ip_neighbor_discovery_settings/...`

- [ ] **Step 1: Write `roles/ip_neighbor_discovery_settings/defaults/main.yml`**

```yaml
---
# /ip/neighbor/discovery-settings is a singleton path. Single-element list,
# e.g. [{discover-interface-list: none}]. Empty -> no change.
routeros_ip_neighbor_discovery_settings: []
```

- [ ] **Step 2: Write `roles/ip_neighbor_discovery_settings/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/neighbor/discovery-settings (singleton).` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_neighbor_discovery_settings/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/neighbor/discovery-settings declaratively (singleton).
    options:
      routeros_ip_neighbor_discovery_settings:
        type: list
        elements: dict
        default: []
        description: Single-element list of neighbor discovery settings.
```

- [ ] **Step 4: Write `roles/ip_neighbor_discovery_settings/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_neighbor_discovery_settings`, `<PATH_SPACE>` = `ip neighbor discovery-settings`.

- [ ] **Step 5: Write `roles/ip_neighbor_discovery_settings/README.md`** from the **README template** with `<ROLE>` = `ip_neighbor_discovery_settings`, `<PATH_SLASH>` = `/ip/neighbor/discovery-settings`, `<EXAMPLE>` =

```
routeros_ip_neighbor_discovery_settings:
      - discover-interface-list: none
```

- [ ] **Step 6: Write `extensions/molecule/ip_neighbor_discovery_settings/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_neighbor_discovery_settings`.

- [ ] **Step 7: Write `extensions/molecule/ip_neighbor_discovery_settings/converge.yml`**

```yaml
---
- name: Converge — set neighbor discovery interface list to none
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_neighbor_discovery_settings:
      - discover-interface-list: none
  roles:
    - role: david_igou.routeros_configuration.ip_neighbor_discovery_settings
```

- [ ] **Step 8: Write `extensions/molecule/ip_neighbor_discovery_settings/verify.yml`**

```yaml
---
- name: Verify — discover-interface-list is none
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/neighbor/discovery-settings over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip neighbor discovery-settings
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert discover-interface-list is none
      ansible.builtin.assert:
        that:
          - q.result | selectattr('discover-interface-list', 'equalto', 'none') | list | length == 1
        fail_msg: "discovery settings unexpected: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_neighbor_discovery_settings` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_neighbor_discovery_settings extensions/molecule/ip_neighbor_discovery_settings
git commit -m "feat(ip_neighbor_discovery_settings): declarative role + molecule scenario"
```

---

## Task 12: `ip_dhcp_client` (list)

> **Prereq:** an interface to bind to — spare **ether5**. Create the client **`disabled: true`** so the CHR doesn't actually start a DHCP client (no DHCP server on the SLIRP segment; an enabled client would just sit in "searching"). The role still proves declarative apply + read-back.

**Files:** `roles/ip_dhcp_client/...` + `extensions/molecule/ip_dhcp_client/...`

- [ ] **Step 1: Write `roles/ip_dhcp_client/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-client entries, e.g.:
#   - interface: ether1
#     add-default-route: true
routeros_ip_dhcp_client: []
routeros_ip_dhcp_client_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_client/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-client entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_client/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-client declaratively.
    options:
      routeros_ip_dhcp_client:
        type: list
        elements: dict
        default: []
        description: DHCP client entries (interface, add-default-route, ...).
      routeros_ip_dhcp_client_purge:
        type: bool
        default: false
        description: Remove clients not present in routeros_ip_dhcp_client.
```

- [ ] **Step 4: Write `roles/ip_dhcp_client/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_client`, `<PATH_SPACE>` = `ip dhcp-client`.

- [ ] **Step 5: Write `roles/ip_dhcp_client/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_client`, `<PATH_SLASH>` = `/ip/dhcp-client`, `<EXAMPLE>` =

```
routeros_ip_dhcp_client:
      - interface: ether1
        add-default-route: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_client/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_client`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_client/converge.yml`**

```yaml
---
- name: Converge — add a (disabled) dhcp-client on ether5
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dhcp_client:
      - interface: ether5
        disabled: true
        add-default-route: false
  roles:
    - role: david_igou.routeros_configuration.ip_dhcp_client
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_client/verify.yml`**

```yaml
---
- name: Verify — dhcp-client present on ether5
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-client over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-client
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the dhcp-client on ether5 exists
      ansible.builtin.assert:
        that:
          - q.result | selectattr('interface', 'equalto', 'ether5') | list | length == 1
        fail_msg: "dhcp-client on ether5 not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_client` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_client extensions/molecule/ip_dhcp_client
git commit -m "feat(ip_dhcp_client): declarative /ip/dhcp-client role + molecule scenario"
```

---

## Task 13: `ip_dhcp_relay` (list)

> **Prereq:** interface (spare **ether5**) + `dhcp-server` address (required field). Create **`disabled: true`**.

**Files:** `roles/ip_dhcp_relay/...` + `extensions/molecule/ip_dhcp_relay/...`

- [ ] **Step 1: Write `roles/ip_dhcp_relay/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-relay entries, e.g.:
#   - name: relay1
#     interface: ether2
#     dhcp-server: "192.168.88.1"
routeros_ip_dhcp_relay: []
routeros_ip_dhcp_relay_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_relay/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-relay entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_relay/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-relay declaratively.
    options:
      routeros_ip_dhcp_relay:
        type: list
        elements: dict
        default: []
        description: DHCP relay entries (name, interface, dhcp-server, ...).
      routeros_ip_dhcp_relay_purge:
        type: bool
        default: false
        description: Remove relays not present in routeros_ip_dhcp_relay.
```

- [ ] **Step 4: Write `roles/ip_dhcp_relay/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_relay`, `<PATH_SPACE>` = `ip dhcp-relay`.

- [ ] **Step 5: Write `roles/ip_dhcp_relay/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_relay`, `<PATH_SLASH>` = `/ip/dhcp-relay`, `<EXAMPLE>` =

```
routeros_ip_dhcp_relay:
      - name: relay1
        interface: ether2
        dhcp-server: "192.168.88.1"
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_relay/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_relay`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_relay/converge.yml`**

```yaml
---
- name: Converge — add a (disabled) dhcp-relay on ether5
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dhcp_relay:
      - name: relay-test
        interface: ether5
        dhcp-server: "192.168.60.1"
        disabled: true
  roles:
    - role: david_igou.routeros_configuration.ip_dhcp_relay
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_relay/verify.yml`**

```yaml
---
- name: Verify — dhcp-relay present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-relay over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-relay
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the relay was created
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'relay-test') | list | length == 1
        fail_msg: "relay-test not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_relay` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_relay extensions/molecule/ip_dhcp_relay
git commit -m "feat(ip_dhcp_relay): declarative /ip/dhcp-relay role + molecule scenario"
```

---

## Task 14: `ip_dhcp_server` (list)

> **Prereq:** an `address-pool` and an `interface`. The `converge` first creates a pool (`pool-dhcp`) via an `api_modify` prereq task, then applies the server on **ether3** referencing it. Created **`disabled: true`**.

**Files:** `roles/ip_dhcp_server/...` + `extensions/molecule/ip_dhcp_server/...`

- [ ] **Step 1: Write `roles/ip_dhcp_server/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-server entries, e.g.:
#   - name: dhcp1
#     interface: ether2
#     address-pool: lan-pool
routeros_ip_dhcp_server: []
routeros_ip_dhcp_server_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_server/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-server instances.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_server/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-server declaratively.
    options:
      routeros_ip_dhcp_server:
        type: list
        elements: dict
        default: []
        description: DHCP server instances (name, interface, address-pool, ...).
      routeros_ip_dhcp_server_purge:
        type: bool
        default: false
        description: Remove servers not present in routeros_ip_dhcp_server.
```

- [ ] **Step 4: Write `roles/ip_dhcp_server/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_server`, `<PATH_SPACE>` = `ip dhcp-server`.

- [ ] **Step 5: Write `roles/ip_dhcp_server/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_server`, `<PATH_SLASH>` = `/ip/dhcp-server`, `<EXAMPLE>` =

```
routeros_ip_dhcp_server:
      - name: dhcp1
        interface: ether2
        address-pool: lan-pool
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_server/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_server`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_server/converge.yml`** (pool prereq, then the server)

```yaml
---
- name: Converge — pool prereq, then a (disabled) dhcp-server on ether3
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create the address pool
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip pool
        handle_absent_entries: ignore
        data:
          - name: pool-dhcp
            ranges: "192.168.60.10-192.168.60.50"
      delegate_to: localhost
      connection: local

    - name: Apply the dhcp-server
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ip_dhcp_server
      vars:
        routeros_ip_dhcp_server:
          - name: dhcp-test
            interface: ether3
            address-pool: pool-dhcp
            disabled: true
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_server/verify.yml`**

```yaml
---
- name: Verify — dhcp-server present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-server over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-server
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the dhcp-server was created on ether3
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'dhcp-test') | selectattr('interface', 'equalto', 'ether3') | list | length == 1
        fail_msg: "dhcp-test not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_server` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_server extensions/molecule/ip_dhcp_server
git commit -m "feat(ip_dhcp_server): declarative /ip/dhcp-server role + molecule scenario"
```

---

## Task 15: `ip_dhcp_server_network` (list)

> Primary key is `address`. No prereq — a dhcp-server-network entry is independent config (the gateway/dns served to a subnet).

**Files:** `roles/ip_dhcp_server_network/...` + `extensions/molecule/ip_dhcp_server_network/...`

- [ ] **Step 1: Write `roles/ip_dhcp_server_network/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-server/network entries, e.g.:
#   - address: "192.168.88.0/24"
#     gateway: "192.168.88.1"
#     dns-server: "192.168.88.1"
routeros_ip_dhcp_server_network: []
routeros_ip_dhcp_server_network_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_server_network/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-server/network entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_server_network/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-server/network declaratively.
    options:
      routeros_ip_dhcp_server_network:
        type: list
        elements: dict
        default: []
        description: DHCP network entries (address, gateway, dns-server, ...).
      routeros_ip_dhcp_server_network_purge:
        type: bool
        default: false
        description: Remove networks not present in the list.
```

- [ ] **Step 4: Write `roles/ip_dhcp_server_network/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_server_network`, `<PATH_SPACE>` = `ip dhcp-server network`.

- [ ] **Step 5: Write `roles/ip_dhcp_server_network/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_server_network`, `<PATH_SLASH>` = `/ip/dhcp-server/network`, `<EXAMPLE>` =

```
routeros_ip_dhcp_server_network:
      - address: "192.168.88.0/24"
        gateway: "192.168.88.1"
        dns-server: "192.168.88.1"
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_server_network/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_server_network`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_server_network/converge.yml`**

```yaml
---
- name: Converge — add a dhcp-server network
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dhcp_server_network:
      - address: "192.168.60.0/24"
        gateway: "192.168.60.1"
        dns-server: "192.168.60.1"
  roles:
    - role: david_igou.routeros_configuration.ip_dhcp_server_network
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_server_network/verify.yml`**

```yaml
---
- name: Verify — dhcp-server network present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-server/network over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-server network
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the network entry was added
      ansible.builtin.assert:
        that:
          - q.result | selectattr('address', 'equalto', '192.168.60.0/24') | list | length == 1
        fail_msg: "network entry not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_server_network` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_server_network extensions/molecule/ip_dhcp_server_network
git commit -m "feat(ip_dhcp_server_network): declarative role + molecule scenario"
```

---

## Task 16: `ip_dhcp_server_option` (list)

> Primary key is `name`; `code` is required. No prereq.

**Files:** `roles/ip_dhcp_server_option/...` + `extensions/molecule/ip_dhcp_server_option/...`

- [ ] **Step 1: Write `roles/ip_dhcp_server_option/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-server/option entries, e.g.:
#   - name: tftp
#     code: 66
#     value: "'192.168.88.1'"
routeros_ip_dhcp_server_option: []
routeros_ip_dhcp_server_option_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_server_option/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-server/option entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_server_option/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-server/option declaratively.
    options:
      routeros_ip_dhcp_server_option:
        type: list
        elements: dict
        default: []
        description: DHCP options (name, code, value, ...).
      routeros_ip_dhcp_server_option_purge:
        type: bool
        default: false
        description: Remove options not present in the list.
```

- [ ] **Step 4: Write `roles/ip_dhcp_server_option/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_server_option`, `<PATH_SPACE>` = `ip dhcp-server option`.

- [ ] **Step 5: Write `roles/ip_dhcp_server_option/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_server_option`, `<PATH_SLASH>` = `/ip/dhcp-server/option`, `<EXAMPLE>` =

```
routeros_ip_dhcp_server_option:
      - name: tftp
        code: 66
        value: "'192.168.88.1'"
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_server_option/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_server_option`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_server_option/converge.yml`**

```yaml
---
- name: Converge — add a dhcp-server option
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_dhcp_server_option:
      - name: opt-tftp
        code: 66
        value: "'192.168.60.1'"
  roles:
    - role: david_igou.routeros_configuration.ip_dhcp_server_option
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_server_option/verify.yml`**

```yaml
---
- name: Verify — dhcp-server option present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-server/option over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-server option
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the option was added
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name', 'equalto', 'opt-tftp') | list | length == 1
        fail_msg: "opt-tftp not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_server_option` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_server_option extensions/molecule/ip_dhcp_server_option
git commit -m "feat(ip_dhcp_server_option): declarative role + molecule scenario"
```

---

## Task 17: `ip_dhcp_server_lease` (list)

> **Prereq:** a static lease's `server` must exist. The `converge` first creates a pool + a (disabled) dhcp-server (`lease-srv`) on ether3 via `api_modify` prereqs, then applies the lease. Primary key is `(server, address)`.

**Files:** `roles/ip_dhcp_server_lease/...` + `extensions/molecule/ip_dhcp_server_lease/...`

- [ ] **Step 1: Write `roles/ip_dhcp_server_lease/defaults/main.yml`**

```yaml
---
# List of /ip/dhcp-server/lease entries, e.g.:
#   - server: dhcp1
#     address: "192.168.88.100"
#     mac-address: "00:11:22:33:44:55"
routeros_ip_dhcp_server_lease: []
routeros_ip_dhcp_server_lease_purge: false
```

- [ ] **Step 2: Write `roles/ip_dhcp_server_lease/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/dhcp-server/lease entries.` and `<TAG3>` = `networking`.

- [ ] **Step 3: Write `roles/ip_dhcp_server_lease/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/dhcp-server/lease declaratively.
    options:
      routeros_ip_dhcp_server_lease:
        type: list
        elements: dict
        default: []
        description: Static DHCP leases (server, address, mac-address, ...).
      routeros_ip_dhcp_server_lease_purge:
        type: bool
        default: false
        description: Remove leases not present in the list.
```

- [ ] **Step 4: Write `roles/ip_dhcp_server_lease/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_dhcp_server_lease`, `<PATH_SPACE>` = `ip dhcp-server lease`.

- [ ] **Step 5: Write `roles/ip_dhcp_server_lease/README.md`** from the **README template** with `<ROLE>` = `ip_dhcp_server_lease`, `<PATH_SLASH>` = `/ip/dhcp-server/lease`, `<EXAMPLE>` =

```
routeros_ip_dhcp_server_lease:
      - server: dhcp1
        address: "192.168.88.100"
        mac-address: "00:11:22:33:44:55"
```

- [ ] **Step 6: Write `extensions/molecule/ip_dhcp_server_lease/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_dhcp_server_lease`.

- [ ] **Step 7: Write `extensions/molecule/ip_dhcp_server_lease/converge.yml`** (pool + server prereqs, then the lease)

```yaml
---
- name: Converge — server prereqs, then a static lease
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create the address pool
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip pool
        handle_absent_entries: ignore
        data:
          - name: pool-lease
            ranges: "192.168.60.10-192.168.60.50"
      delegate_to: localhost
      connection: local

    - name: Prereq — create a (disabled) dhcp-server on ether3
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-server
        handle_absent_entries: ignore
        data:
          - name: lease-srv
            interface: ether3
            address-pool: pool-lease
            disabled: true
      delegate_to: localhost
      connection: local

    - name: Apply the static lease
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ip_dhcp_server_lease
      vars:
        routeros_ip_dhcp_server_lease:
          - server: lease-srv
            address: "192.168.60.100"
            mac-address: "00:11:22:33:44:66"
```

- [ ] **Step 8: Write `extensions/molecule/ip_dhcp_server_lease/verify.yml`**

```yaml
---
- name: Verify — static lease present
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/dhcp-server/lease over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip dhcp-server lease
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert the static lease was added
      ansible.builtin.assert:
        that:
          - q.result | selectattr('address', 'equalto', '192.168.60.100') | list | length == 1
        fail_msg: "static lease not found: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_dhcp_server_lease` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_dhcp_server_lease extensions/molecule/ip_dhcp_server_lease
git commit -m "feat(ip_dhcp_server_lease): declarative role + molecule scenario"
```

---

## Task 18: CI matrix + documentation + changelog

**Files:**
- Modify: `.github/workflows/tests.yml` (the `molecule-qemu` matrix `scenario:` list)
- Modify: `README.md` (Roles table)
- Modify: `extensions/molecule/README.md` (scenarios prose/table)
- Create: `changelogs/fragments/ip-core-roles.yml`

- [ ] **Step 1: Extend the CI matrix**

In `.github/workflows/tests.yml`, under `jobs.molecule-qemu.strategy.matrix.scenario`, add these 17 entries to the existing list (after the interface entries):

```yaml
          - ip_pool
          - ip_dns
          - ip_dns_static
          - ip_dhcp_server
          - ip_dhcp_server_network
          - ip_dhcp_server_lease
          - ip_dhcp_server_option
          - ip_dhcp_client
          - ip_dhcp_relay
          - ip_route
          - ip_service
          - ip_arp
          - ip_neighbor_discovery_settings
          - ip_settings
          - ip_cloud
          - ip_vrf
          - ip_ssh
```

- [ ] **Step 2: Add the roles to the top-level README Roles table**

In `README.md`, under the `## Roles` table, add one row per role (mirror the existing one-line style, e.g. `` | `ip_pool` | `/ip/pool`. | ``). Mark `ip_service` as modify-only and `ip_dns`/`ip_settings`/`ip_cloud`/`ip_ssh`/`ip_neighbor_discovery_settings` as singletons:

```markdown
| `ip_pool` | `/ip/pool`. |
| `ip_dns` | `/ip/dns` (singleton). |
| `ip_dns_static` | `/ip/dns/static` records. |
| `ip_dhcp_server` | `/ip/dhcp-server` instances. |
| `ip_dhcp_server_network` | `/ip/dhcp-server/network`. |
| `ip_dhcp_server_lease` | `/ip/dhcp-server/lease` static leases. |
| `ip_dhcp_server_option` | `/ip/dhcp-server/option`. |
| `ip_dhcp_client` | `/ip/dhcp-client`. |
| `ip_dhcp_relay` | `/ip/dhcp-relay`. |
| `ip_route` | `/ip/route` static routes. |
| `ip_service` | `/ip/service` (modify-only). |
| `ip_arp` | `/ip/arp` static entries. |
| `ip_neighbor_discovery_settings` | `/ip/neighbor/discovery-settings` (singleton). |
| `ip_settings` | `/ip/settings` (singleton). |
| `ip_cloud` | `/ip/cloud` (singleton). |
| `ip_vrf` | `/ip/vrf` instances. |
| `ip_ssh` | `/ip/ssh` (singleton). |
```

- [ ] **Step 3: Note the new scenarios in the molecule README**

In `extensions/molecule/README.md`, extend the scenarios prose to mention the IP-core group (17 scenarios under `extensions/molecule/ip_*`), noting that dhcp-server/lease/network/option chains create their prerequisites in `converge` and that dhcp client/relay/server are created `disabled` for the offline CHR.

- [ ] **Step 4: Write the changelog fragment**

`changelogs/fragments/ip-core-roles.yml`:
```yaml
---
minor_changes:
  - >-
    Add the IP-core subsystem roles ``ip_pool``, ``ip_dns``, ``ip_dns_static``,
    ``ip_dhcp_server`` (plus ``_network``/``_lease``/``_option``),
    ``ip_dhcp_client``, ``ip_dhcp_relay``, ``ip_route``, ``ip_service``,
    ``ip_arp``, ``ip_neighbor_discovery_settings``, ``ip_settings``,
    ``ip_cloud``, ``ip_vrf``, and ``ip_ssh`` — each managing one RouterOS path
    via ``community.routeros.api_modify`` with a per-role molecule scenario.
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/tests.yml README.md extensions/molecule/README.md changelogs/fragments/ip-core-roles.yml
git commit -m "ci+docs: run the IP-core scenarios; document the roles"
```

---

## Task 19: Full-suite verification

- [ ] **Step 1: Build the collection (metadata is valid)**

Run: `ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz`
Expected: builds with no error (all new `meta`/`argument_specs` parse).

- [ ] **Step 2: Run every new scenario end-to-end**

Run each: `make molecule SCENARIO=<role>` for all 17 roles in this plan (or `make molecule` to run `--all --continue-on-failure`).
Expected: every scenario PASSES — converge applies, idempotence is clean, verify asserts state via `api_info`, destroy tears down.

- [ ] **Step 3: Confirm a clean tree**

Run: `git status`
Expected: working tree clean. If any scenario failed, debug with `superpowers:systematic-debugging` before claiming completion.

- [ ] **Step 4: Push and open a PR; confirm CI is green**

```bash
git push -u origin feat/ip-core-roles
gh pr create --base master --title "feat: IP core roles (Plan 2 of 3)" --fill
```
Then watch the run (`gh run watch` / `gh run list`) until the `all_green` gate and all `molecule-qemu (ip_*)` jobs pass.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** all 17 rows of the spec's "Plan 2 — IP core" table have a task (Tasks 1–17); molecule scenario per role (each task Step 6–9) ✓; CI matrix entries (Task 18) ✓; docs + changelog (Task 18) ✓; reuse of the shared `utils/` bootstrap + centralised `config.yml` (every molecule.yml is name-only) ✓.
- **Count reconciliation:** the spec prose says "16 new roles" but its table lists 17; this plan implements the 17 table rows (the authoritative source). Flag to the reviewer at PR time.
- **Type coverage:** list (pool, dns_static, dhcp_*, route, arp, vrf), singleton (dns, neighbor_discovery_settings, settings, cloud, ssh), modify-only (service). No ordered paths — deferred to Plan 3 (firewall).
- **Prerequisite chains** handled inside `converge` via `api_modify` prereq tasks: dhcp-server → pool (Task 14); dhcp-server lease → pool + server (Task 17). dhcp-server-network/option are independent. arp/vrf/dhcp-client/dhcp-relay bind to existing spare ethers (ether3/5/6).
- **Offline-safety:** dhcp client/relay/server created `disabled: true`; `ip_route` uses a `disabled` route with an explicit gateway (no reachability needed, and idempotent — unlike a `blackhole` route); `ip_service` touches only `telnet`; singletons (`ip_ssh`, `ip_settings`, `ip_cloud`) use fields that don't disrupt the API/SSH the harness depends on.
- **Fixture:** unchanged — the 8-NIC CHR from Plan 1 already provides ether3–8 spare ports.
- **Idempotence risk:** `ip_cloud` flagged with a documented fallback field (Task 9 Step 9) if a ROS build normalises `update-time`.
```