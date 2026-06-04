# IP Firewall Roles — Implementation Plan (Plan 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final 6 declarative `/ip/firewall` roles — three ordered paths (`nat`, `mangle`, `raw`), one keyed list (`address_list`), one singleton (`connection_tracking`), and one modify-only path (`service_port`) — each a thin `_reconcile` wrapper with its own CHR molecule scenario.

**Architecture:** Identical to the merged `ip_firewall_filter` (ordered) and IP-core roles — each role maps a `routeros_<role>` var to the internal `_reconcile` engine which calls `community.routeros.api_modify`. The three ordered roles mirror `ip_firewall_filter` exactly: `_purge` + `_order` + `_content` toggles, where `_order: true` requires `_purge: true` (the engine asserts this). Provisioner wiring / `test_sequence` / `verifier` are centralised in `extensions/molecule/config.yml`, so each scenario's `molecule.yml` is name-only. Each scenario boots a fresh CHR (shared `extensions/molecule/utils/` bootstrap) and verifies via `api_info`.

**Tech Stack:** Ansible roles, `community.routeros` 3.20.0 (`api_modify`/`api_info` + `librouteros`), molecule + `david_igou.molecule_provisioners` qemu, MikroTik CHR 7.21.4.

**Reference spec:** `docs/superpowers/specs/2026-06-04-interface-ip-bridge-roles-design.md` (§ "Plan 3 — IP firewall").

> **Roles (6):** `ip_firewall_nat` (ordered), `ip_firewall_mangle` (ordered), `ip_firewall_raw` (ordered), `ip_firewall_address_list` (list), `ip_firewall_connection_tracking` (singleton), `ip_firewall_service_port` (modify-only). (`ip_firewall_filter` already exists from Plan 1's slice.)

> **Path support pre-verified:** all 6 `api_modify` paths exist in the installed `community.routeros` 3.20.0 registry (`_api_data.py`). Field names, primary keys, required fields, and the singleton/fixed flags used below come from that registry. Note the path strings: `ip firewall nat`, `ip firewall mangle`, `ip firewall raw`, `ip firewall address-list`, `ip firewall connection tracking` (four words), `ip firewall service-port`.

---

## Conventions (apply to every task)

- **No flow-style YAML.** Block form only (`- key: val` on their own lines), never `- {key: val}` in data.
- **Each role** lives in `roles/<role>/` with five files: `defaults/main.yml`, `meta/main.yml`, `meta/argument_specs.yml`, `tasks/main.yml`, `README.md`.
- **Each scenario** lives in `extensions/molecule/<role>/` with three files: `molecule.yml` (name-only), `converge.yml`, `verify.yml`.
- **Run a scenario:** `make molecule SCENARIO=<role>`. Expected for every scenario: CHR boots → `prepare` opens the API → `converge` applies → `idempotence` reports **no changes** → `verify` asserts via `api_info` → `destroy`. Whole run PASSES.
- **Lockout-safety (critical for the ordered paths).** The molecule harness reaches the device over SSH (during `prepare` only) and the binary API on TCP 8728 (during `converge`/`idempotence`/`verify`). The ordered NAT/mangle/raw scenarios apply with **purge + order**, which clears and rewrites the whole chain set — so they MUST NOT add any rule that drops, rejects, or NATs management traffic. Use only `accept`, `masquerade` (srcnat, out a spare ether), and a narrowly-scoped `notrack` (raw, on a TEST-NET dst). Never `action: drop`/`reject`, never touch port 22 or 8728.
- **`address-list`/`service-port` keep the device usable too:** address-list entries use TEST-NET-1 (`192.0.2.0/24`) addresses; `service_port` modifies only the built-in **`ftp`** helper (NOT the management services).

---

## Templates (used by every role task below)

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

```markdown
# <ROLE>

Declaratively manage `<PATH_SLASH>` over the RouterOS API.

    <EXAMPLE>

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
```

### Template `tasks/main.yml` — **ordered** type (substitute `<ROLE>`, `<PATH_SPACE>`)

Mirrors the merged `ip_firewall_filter` role exactly.

```yaml
---
# tasks file for david_igou.routeros_configuration.<ROLE>
- name: "Reconcile <PATH_SPACE>"
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: <PATH_SPACE>
    rcfg_data: "{{ routeros_<ROLE> }}"
    rcfg_purge: "{{ routeros_<ROLE>_purge }}"
    rcfg_order: "{{ routeros_<ROLE>_order }}"
    rcfg_content: "{{ routeros_<ROLE>_content }}"
```

### Template `tasks/main.yml` — **list** type (substitute `<ROLE>`, `<PATH_SPACE>`)

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

```yaml
---
# Provisioner wiring, test_sequence, and verifier are centralised in
# extensions/molecule/config.yml and merged in by molecule. This file declares
# only the scenario name.
scenario:
  name: <ROLE>
```

---

## Task 1: `ip_firewall_nat` (ordered)

**Files:** `roles/ip_firewall_nat/...` + `extensions/molecule/ip_firewall_nat/...`

- [ ] **Step 1: Write `roles/ip_firewall_nat/defaults/main.yml`**

```yaml
---
# Ordered list of /ip/firewall/nat rules. Order matters; set _order: true
# (which also requires _purge: true) to enforce it exactly.
routeros_ip_firewall_nat: []
routeros_ip_firewall_nat_purge: false
routeros_ip_firewall_nat_order: false
# How to treat fields not present in a matched rule. ORDERED path: api_modify
# requires _purge while this stays "ignore"; the default resets unspecified
# fields, making rules fully declarative.
routeros_ip_firewall_nat_content: remove_as_much_as_possible
```

- [ ] **Step 2: Write `roles/ip_firewall_nat/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/nat rules (ordered).` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_nat/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/nat declaratively (ordered).
    options:
      routeros_ip_firewall_nat:
        type: list
        elements: dict
        default: []
        description: Ordered NAT rules (chain, action, ...).
      routeros_ip_firewall_nat_purge:
        type: bool
        default: false
        description: Remove rules not present in the list.
      routeros_ip_firewall_nat_order:
        type: bool
        default: false
        description: Enforce rule order. Requires _purge true.
      routeros_ip_firewall_nat_content:
        type: str
        default: remove_as_much_as_possible
        choices: [ignore, remove, remove_as_much_as_possible]
        description: How to treat fields not present in a matched rule.
```

- [ ] **Step 4: Write `roles/ip_firewall_nat/tasks/main.yml`** from the **ordered tasks template** with `<ROLE>` = `ip_firewall_nat`, `<PATH_SPACE>` = `ip firewall nat`.

- [ ] **Step 5: Write `roles/ip_firewall_nat/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_nat`, `<PATH_SLASH>` = `/ip/firewall/nat`, `<EXAMPLE>` =

```
routeros_ip_firewall_nat:
      - chain: srcnat
        action: masquerade
        out-interface: ether1
    routeros_ip_firewall_nat_purge: true
    routeros_ip_firewall_nat_order: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_nat/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_nat`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_nat/converge.yml`**

```yaml
---
# Lockout-safe: only accept/masquerade rules (no drop/reject, no management
# NAT), so purge+order can rewrite the chain set without cutting the API/SSH.
- name: Converge — apply ordered NAT rules
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_nat:
      - chain: srcnat
        action: accept
        comment: "nat-a"
      - chain: srcnat
        action: masquerade
        out-interface: ether3
        comment: "nat-b"
      - chain: dstnat
        action: accept
        comment: "nat-c"
    routeros_ip_firewall_nat_purge: true
    routeros_ip_firewall_nat_order: true
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_nat
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_nat/verify.yml`**

```yaml
---
- name: Verify — NAT rules present in declared order
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/nat over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall nat
      delegate_to: localhost
      connection: local
      register: fw

    - name: Collect the comments in device order
      ansible.builtin.set_fact:
        fw_comments: "{{ fw.result | map(attribute='comment') | list }}"

    - name: Assert all three rules exist in the declared order
      ansible.builtin.assert:
        that:
          - "'nat-a' in fw_comments"
          - "'nat-b' in fw_comments"
          - "'nat-c' in fw_comments"
          - fw_comments.index('nat-a') < fw_comments.index('nat-b')
          - fw_comments.index('nat-b') < fw_comments.index('nat-c')
        success_msg: "nat rules present in order a<b<c: {{ fw_comments }}"
        fail_msg: "unexpected nat order/content: {{ fw_comments }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_nat` — PASSES (converge applies, idempotence clean, verify confirms order).

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_nat extensions/molecule/ip_firewall_nat
git commit -m "feat(ip_firewall_nat): declarative ordered /ip/firewall/nat role + scenario"
```

---

## Task 2: `ip_firewall_mangle` (ordered)

**Files:** `roles/ip_firewall_mangle/...` + `extensions/molecule/ip_firewall_mangle/...`

- [ ] **Step 1: Write `roles/ip_firewall_mangle/defaults/main.yml`**

```yaml
---
# Ordered list of /ip/firewall/mangle rules. Order matters; set _order: true
# (which also requires _purge: true) to enforce it exactly.
routeros_ip_firewall_mangle: []
routeros_ip_firewall_mangle_purge: false
routeros_ip_firewall_mangle_order: false
routeros_ip_firewall_mangle_content: remove_as_much_as_possible
```

- [ ] **Step 2: Write `roles/ip_firewall_mangle/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/mangle rules (ordered).` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_mangle/meta/argument_specs.yml`** (same shape as Task 1 Step 3, substituting `mangle` for `nat` in every var name and the short_description)

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/mangle declaratively (ordered).
    options:
      routeros_ip_firewall_mangle:
        type: list
        elements: dict
        default: []
        description: Ordered mangle rules (chain, action, ...).
      routeros_ip_firewall_mangle_purge:
        type: bool
        default: false
        description: Remove rules not present in the list.
      routeros_ip_firewall_mangle_order:
        type: bool
        default: false
        description: Enforce rule order. Requires _purge true.
      routeros_ip_firewall_mangle_content:
        type: str
        default: remove_as_much_as_possible
        choices: [ignore, remove, remove_as_much_as_possible]
        description: How to treat fields not present in a matched rule.
```

- [ ] **Step 4: Write `roles/ip_firewall_mangle/tasks/main.yml`** from the **ordered tasks template** with `<ROLE>` = `ip_firewall_mangle`, `<PATH_SPACE>` = `ip firewall mangle`.

- [ ] **Step 5: Write `roles/ip_firewall_mangle/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_mangle`, `<PATH_SLASH>` = `/ip/firewall/mangle`, `<EXAMPLE>` =

```
routeros_ip_firewall_mangle:
      - chain: prerouting
        action: accept
    routeros_ip_firewall_mangle_purge: true
    routeros_ip_firewall_mangle_order: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_mangle/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_mangle`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_mangle/converge.yml`**

```yaml
---
# Lockout-safe: only accept rules across chains; purge+order rewrites the chain
# set without affecting management traffic.
- name: Converge — apply ordered mangle rules
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_mangle:
      - chain: prerouting
        action: accept
        comment: "mangle-a"
      - chain: forward
        action: accept
        comment: "mangle-b"
      - chain: postrouting
        action: accept
        comment: "mangle-c"
    routeros_ip_firewall_mangle_purge: true
    routeros_ip_firewall_mangle_order: true
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_mangle
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_mangle/verify.yml`** — same as Task 1 Step 8 but `path: ip firewall mangle` and assert comments `mangle-a`/`mangle-b`/`mangle-c` in order:

```yaml
---
- name: Verify — mangle rules present in declared order
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/mangle over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall mangle
      delegate_to: localhost
      connection: local
      register: fw

    - name: Collect the comments in device order
      ansible.builtin.set_fact:
        fw_comments: "{{ fw.result | map(attribute='comment') | list }}"

    - name: Assert all three rules exist in the declared order
      ansible.builtin.assert:
        that:
          - "'mangle-a' in fw_comments"
          - "'mangle-b' in fw_comments"
          - "'mangle-c' in fw_comments"
          - fw_comments.index('mangle-a') < fw_comments.index('mangle-b')
          - fw_comments.index('mangle-b') < fw_comments.index('mangle-c')
        success_msg: "mangle rules present in order a<b<c: {{ fw_comments }}"
        fail_msg: "unexpected mangle order/content: {{ fw_comments }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_mangle` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_mangle extensions/molecule/ip_firewall_mangle
git commit -m "feat(ip_firewall_mangle): declarative ordered /ip/firewall/mangle role + scenario"
```

---

## Task 3: `ip_firewall_raw` (ordered)

**Files:** `roles/ip_firewall_raw/...` + `extensions/molecule/ip_firewall_raw/...`

- [ ] **Step 1: Write `roles/ip_firewall_raw/defaults/main.yml`**

```yaml
---
# Ordered list of /ip/firewall/raw rules. Order matters; set _order: true
# (which also requires _purge: true) to enforce it exactly.
routeros_ip_firewall_raw: []
routeros_ip_firewall_raw_purge: false
routeros_ip_firewall_raw_order: false
routeros_ip_firewall_raw_content: remove_as_much_as_possible
```

- [ ] **Step 2: Write `roles/ip_firewall_raw/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/raw rules (ordered).` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_raw/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/raw declaratively (ordered).
    options:
      routeros_ip_firewall_raw:
        type: list
        elements: dict
        default: []
        description: Ordered raw rules (chain, action, ...).
      routeros_ip_firewall_raw_purge:
        type: bool
        default: false
        description: Remove rules not present in the list.
      routeros_ip_firewall_raw_order:
        type: bool
        default: false
        description: Enforce rule order. Requires _purge true.
      routeros_ip_firewall_raw_content:
        type: str
        default: remove_as_much_as_possible
        choices: [ignore, remove, remove_as_much_as_possible]
        description: How to treat fields not present in a matched rule.
```

- [ ] **Step 4: Write `roles/ip_firewall_raw/tasks/main.yml`** from the **ordered tasks template** with `<ROLE>` = `ip_firewall_raw`, `<PATH_SPACE>` = `ip firewall raw`.

- [ ] **Step 5: Write `roles/ip_firewall_raw/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_raw`, `<PATH_SLASH>` = `/ip/firewall/raw`, `<EXAMPLE>` =

```
routeros_ip_firewall_raw:
      - chain: prerouting
        action: accept
    routeros_ip_firewall_raw_purge: true
    routeros_ip_firewall_raw_order: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_raw/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_raw`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_raw/converge.yml`**

```yaml
---
# Lockout-safe: accept rules plus a notrack scoped to TEST-NET-1 (192.0.2.0/24),
# so management traffic on 22/8728 is never untracked or dropped.
- name: Converge — apply ordered raw rules
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_raw:
      - chain: prerouting
        action: accept
        comment: "raw-a"
      - chain: prerouting
        action: notrack
        dst-address: "192.0.2.0/24"
        comment: "raw-b"
      - chain: output
        action: accept
        comment: "raw-c"
    routeros_ip_firewall_raw_purge: true
    routeros_ip_firewall_raw_order: true
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_raw
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_raw/verify.yml`** — same shape, `path: ip firewall raw`, assert `raw-a`/`raw-b`/`raw-c` in order:

```yaml
---
- name: Verify — raw rules present in declared order
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/raw over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall raw
      delegate_to: localhost
      connection: local
      register: fw

    - name: Collect the comments in device order
      ansible.builtin.set_fact:
        fw_comments: "{{ fw.result | map(attribute='comment') | list }}"

    - name: Assert all three rules exist in the declared order
      ansible.builtin.assert:
        that:
          - "'raw-a' in fw_comments"
          - "'raw-b' in fw_comments"
          - "'raw-c' in fw_comments"
          - fw_comments.index('raw-a') < fw_comments.index('raw-b')
          - fw_comments.index('raw-b') < fw_comments.index('raw-c')
        success_msg: "raw rules present in order a<b<c: {{ fw_comments }}"
        fail_msg: "unexpected raw order/content: {{ fw_comments }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_raw` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_raw extensions/molecule/ip_firewall_raw
git commit -m "feat(ip_firewall_raw): declarative ordered /ip/firewall/raw role + scenario"
```

---

## Task 4: `ip_firewall_address_list` (list)

> Primary key is `(address, list)`. No prereq.

**Files:** `roles/ip_firewall_address_list/...` + `extensions/molecule/ip_firewall_address_list/...`

- [ ] **Step 1: Write `roles/ip_firewall_address_list/defaults/main.yml`**

```yaml
---
# List of /ip/firewall/address-list entries, e.g.:
#   - list: blocked
#     address: "203.0.113.0/24"
routeros_ip_firewall_address_list: []
routeros_ip_firewall_address_list_purge: false
```

- [ ] **Step 2: Write `roles/ip_firewall_address_list/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/address-list entries.` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_address_list/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/address-list declaratively.
    options:
      routeros_ip_firewall_address_list:
        type: list
        elements: dict
        default: []
        description: Address-list entries (list, address, ...).
      routeros_ip_firewall_address_list_purge:
        type: bool
        default: false
        description: Remove entries not present in the list.
```

- [ ] **Step 4: Write `roles/ip_firewall_address_list/tasks/main.yml`** from the **list tasks template** with `<ROLE>` = `ip_firewall_address_list`, `<PATH_SPACE>` = `ip firewall address-list`.

- [ ] **Step 5: Write `roles/ip_firewall_address_list/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_address_list`, `<PATH_SLASH>` = `/ip/firewall/address-list`, `<EXAMPLE>` =

```
routeros_ip_firewall_address_list:
      - list: blocked
        address: "203.0.113.0/24"
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_address_list/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_address_list`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_address_list/converge.yml`**

```yaml
---
- name: Converge — add address-list entries
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_address_list:
      - list: test-block
        address: "192.0.2.10"
      - list: test-block
        address: "192.0.2.11"
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_address_list
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_address_list/verify.yml`** (additive read-back, then purge round-trip)

```yaml
---
- name: Verify — address-list apply + purge semantics
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/address-list after additive converge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall address-list
      delegate_to: localhost
      connection: local
      register: al_before

    - name: Assert both declared addresses are present
      ansible.builtin.assert:
        that:
          - >-
            al_before.result | selectattr('address', 'equalto', '192.0.2.10')
            | list | length == 1
          - >-
            al_before.result | selectattr('address', 'equalto', '192.0.2.11')
            | list | length == 1

    - name: Re-apply with a reduced list and purge enabled
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ip_firewall_address_list
      vars:
        routeros_ip_firewall_address_list:
          - list: test-block
            address: "192.0.2.10"
        routeros_ip_firewall_address_list_purge: true

    - name: Read /ip/firewall/address-list after purge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall address-list
      delegate_to: localhost
      connection: local
      register: al_after

    - name: Assert .11 was purged and .10 remains
      ansible.builtin.assert:
        that:
          - >-
            al_after.result | selectattr('address', 'equalto', '192.0.2.10')
            | list | length == 1
          - >-
            al_after.result | selectattr('address', 'equalto', '192.0.2.11')
            | list | length == 0
        success_msg: "purge removed 192.0.2.11, kept 192.0.2.10"
        fail_msg: "purge did not behave as expected: {{ al_after.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_address_list` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_address_list extensions/molecule/ip_firewall_address_list
git commit -m "feat(ip_firewall_address_list): declarative role + molecule scenario (purge)"
```

---

## Task 5: `ip_firewall_connection_tracking` (singleton)

> Singleton (`single_value=True`). Toggle the `loose-tcp-tracking` boolean (a clean round-trip, unlike timeout strings RouterOS may normalise). Safe on the ephemeral CHR.

**Files:** `roles/ip_firewall_connection_tracking/...` + `extensions/molecule/ip_firewall_connection_tracking/...`

- [ ] **Step 1: Write `roles/ip_firewall_connection_tracking/defaults/main.yml`**

```yaml
---
# /ip/firewall/connection/tracking is a singleton path. Single-element list of
# connection-tracking settings, e.g. [{loose-tcp-tracking: false}].
# Empty -> no change.
routeros_ip_firewall_connection_tracking: []
```

- [ ] **Step 2: Write `roles/ip_firewall_connection_tracking/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/connection/tracking (singleton).` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_connection_tracking/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage connection tracking declaratively (singleton).
    options:
      routeros_ip_firewall_connection_tracking:
        type: list
        elements: dict
        default: []
        description: Single-element list of connection-tracking settings.
```

- [ ] **Step 4: Write `roles/ip_firewall_connection_tracking/tasks/main.yml`** from the **singleton tasks template** with `<ROLE>` = `ip_firewall_connection_tracking`, `<PATH_SPACE>` = `ip firewall connection tracking`.

- [ ] **Step 5: Write `roles/ip_firewall_connection_tracking/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_connection_tracking`, `<PATH_SLASH>` = `/ip/firewall/connection/tracking`, `<EXAMPLE>` =

```
routeros_ip_firewall_connection_tracking:
      - loose-tcp-tracking: false
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_connection_tracking/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_connection_tracking`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_connection_tracking/converge.yml`**

```yaml
---
- name: Converge — set a connection-tracking setting
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_connection_tracking:
      - loose-tcp-tracking: false
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_connection_tracking
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_connection_tracking/verify.yml`**

```yaml
---
- name: Verify — loose-tcp-tracking disabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/connection/tracking over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall connection tracking
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert loose-tcp-tracking is false
      ansible.builtin.assert:
        that:
          - >-
            q.result | selectattr('loose-tcp-tracking', 'equalto', false)
            | list | length == 1
        fail_msg: "connection tracking unexpected: {{ q.result }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_connection_tracking` — PASSES.

> If `idempotence` flags a change (some ROS builds report `loose-tcp-tracking` only when tracking is `enabled`/`auto`), set `enabled: "yes"` alongside it in both converge and the role default and assert on `enabled` instead.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_connection_tracking extensions/molecule/ip_firewall_connection_tracking
git commit -m "feat(ip_firewall_connection_tracking): declarative singleton role + scenario"
```

---

## Task 6: `ip_firewall_service_port` (modify-only)

> Modify-only (`fixed_entries=True`, pk=`name`). Built-in helpers (ftp, tftp, irc, sip, ...) can only be modified, not added/removed. `converge` disables the **`ftp`** helper (safe — the harness never uses FTP). Purge is off.

**Files:** `roles/ip_firewall_service_port/...` + `extensions/molecule/ip_firewall_service_port/...`

- [ ] **Step 1: Write `roles/ip_firewall_service_port/defaults/main.yml`**

```yaml
---
# Modify-only list of /ip/firewall/service-port helpers (keyed by name).
# Cannot add/remove; only change fields like disabled/ports, e.g.:
#   - name: ftp
#     disabled: true
routeros_ip_firewall_service_port: []
```

- [ ] **Step 2: Write `roles/ip_firewall_service_port/meta/main.yml`** from the **meta template** with `<DESC>` = `Declaratively manage /ip/firewall/service-port (modify-only).` and `<TAG3>` = `firewall`.

- [ ] **Step 3: Write `roles/ip_firewall_service_port/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/service-port declaratively (modify-only).
    options:
      routeros_ip_firewall_service_port:
        type: list
        elements: dict
        default: []
        description: Built-in service-port helpers to modify (name, disabled, ports).
```

- [ ] **Step 4: Write `roles/ip_firewall_service_port/tasks/main.yml`** from the **singleton/modify-only tasks template** with `<ROLE>` = `ip_firewall_service_port`, `<PATH_SPACE>` = `ip firewall service-port`.

- [ ] **Step 5: Write `roles/ip_firewall_service_port/README.md`** from the **README template** with `<ROLE>` = `ip_firewall_service_port`, `<PATH_SLASH>` = `/ip/firewall/service-port`, `<EXAMPLE>` =

```
routeros_ip_firewall_service_port:
      - name: ftp
        disabled: true
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_service_port/molecule.yml`** from the **molecule.yml template** with `<ROLE>` = `ip_firewall_service_port`.

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_service_port/converge.yml`**

```yaml
---
- name: Converge — disable the built-in ftp service-port helper
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_service_port:
      - name: ftp
        disabled: true
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_service_port
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_service_port/verify.yml`**

```yaml
---
- name: Verify — ftp service-port helper disabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/service-port over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall service-port
      delegate_to: localhost
      connection: local
      register: q

    - name: Assert ftp helper is disabled
      ansible.builtin.assert:
        that:
          - >-
            q.result | selectattr('name', 'equalto', 'ftp')
            | selectattr('disabled', 'equalto', true) | list | length == 1
        fail_msg: "ftp helper not disabled: {{ q.result | selectattr('name','equalto','ftp') | list }}"
```

- [ ] **Step 9: Run** `make molecule SCENARIO=ip_firewall_service_port` — PASSES.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_service_port extensions/molecule/ip_firewall_service_port
git commit -m "feat(ip_firewall_service_port): declarative modify-only role + scenario"
```

---

## Task 7: CI matrix + documentation + changelog

**Files:**
- Modify: `.github/workflows/tests.yml` (the `molecule-qemu` matrix `scenario:` list)
- Modify: `README.md` (Roles table)
- Modify: `extensions/molecule/README.md` (scenarios prose)
- Create: `changelogs/fragments/ip-firewall-roles.yml`

- [ ] **Step 1: Extend the CI matrix**

In `.github/workflows/tests.yml`, append to `jobs.molecule-qemu.strategy.matrix.scenario` (after the `ip_*` IP-core entries):

```yaml
          - ip_firewall_nat
          - ip_firewall_mangle
          - ip_firewall_raw
          - ip_firewall_address_list
          - ip_firewall_connection_tracking
          - ip_firewall_service_port
```

- [ ] **Step 2: Add the roles to the top-level README**

In `README.md`, add an `### IP firewall` subsection (mirroring the existing `### IP core` table style):

```markdown
### IP firewall

| Role | Manages |
| --- | --- |
| `ip_firewall_nat` | `/ip/firewall/nat` (ordered). |
| `ip_firewall_mangle` | `/ip/firewall/mangle` (ordered). |
| `ip_firewall_raw` | `/ip/firewall/raw` (ordered). |
| `ip_firewall_address_list` | `/ip/firewall/address-list`. |
| `ip_firewall_connection_tracking` | `/ip/firewall/connection/tracking` (singleton). |
| `ip_firewall_service_port` | `/ip/firewall/service-port` (modify-only). |
```

(The existing `ip_firewall_filter` row stays in the top "Roles" table.)

- [ ] **Step 3: Note the new scenarios in the molecule README**

In `extensions/molecule/README.md`, extend the scenarios prose to mention the 6 firewall scenarios, noting the ordered nat/mangle/raw use purge+order with only accept/masquerade/notrack rules (never dropping management traffic), address-list does an additive+purge round-trip, and service-port modifies only the built-in `ftp` helper.

- [ ] **Step 4: Write the changelog fragment**

`changelogs/fragments/ip-firewall-roles.yml`:
```yaml
---
minor_changes:
  - >-
    Add the IP-firewall subsystem roles ``ip_firewall_nat``,
    ``ip_firewall_mangle``, and ``ip_firewall_raw`` (ordered),
    ``ip_firewall_address_list`` (list), ``ip_firewall_connection_tracking``
    (singleton), and ``ip_firewall_service_port`` (modify-only) — each managing
    one RouterOS path via ``community.routeros.api_modify`` with a per-role
    molecule scenario.
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/tests.yml README.md extensions/molecule/README.md changelogs/fragments/ip-firewall-roles.yml
git commit -m "ci+docs: run the IP-firewall scenarios; document the roles"
```

---

## Task 8: Full-suite verification + PR

- [ ] **Step 1: Build the collection (metadata is valid)**

Run: `ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz`
Expected: builds with no error.

- [ ] **Step 2: Static checks**

Run: `yamllint roles/ip_firewall_* extensions/molecule/ip_firewall_*` (no errors) and `ansible-lint roles/ip_firewall_nat roles/ip_firewall_mangle roles/ip_firewall_raw roles/ip_firewall_address_list roles/ip_firewall_connection_tracking roles/ip_firewall_service_port` (0 failures, after `ansible-galaxy collection install . --force`).

- [ ] **Step 3: Run every new scenario end-to-end**

Run each: `make molecule SCENARIO=<role>` for the 6 roles (or `make molecule` for `--all`).
Expected: every scenario PASSES — converge applies, idempotence clean, verify asserts via `api_info`, destroy tears down. If any fails, debug with `superpowers:systematic-debugging` before claiming completion. (The ordered paths are the highest risk: confirm the second converge reports no change.)

- [ ] **Step 4: Push and open a PR; confirm CI is green**

```bash
git push -u origin feat/ip-firewall-roles
gh pr create --base master --title "feat: IP firewall roles (Plan 3 of 3)" --fill
```
Then watch the run until the `all_green` gate and all 6 new `molecule-qemu (ip_firewall_*)` jobs pass (matrix end state ≈ 42 scenarios).

---

## Self-Review notes (for the implementer)

- **Spec coverage:** all 6 rows of the spec's "Plan 3 — IP firewall" table have a task (Tasks 1–6); molecule scenario per role ✓; CI matrix + docs + changelog (Task 7) ✓; full verification + PR (Task 8) ✓.
- **Type coverage:** ordered (nat, mangle, raw — mirror the merged `ip_firewall_filter`), list (address_list), singleton (connection_tracking), modify-only (service_port). This completes every pattern class in the collection.
- **Lockout-safety:** the ordered paths apply purge+order but use only `accept`/`masquerade`/`notrack` (the latter scoped to TEST-NET) — none drop, reject, or NAT the SSH(22)/API(8728) management traffic, so the harness never cuts its own connection. (Contrast `ip_firewall_filter`, which must explicitly accept 22/8728 because it adds a `drop`.)
- **Idempotence:** ordered firewall reconciliation is already proven by the merged `ip_firewall_filter` scenario; nat/mangle/raw use the same engine path. `connection_tracking` toggles a boolean (clean round-trip) with a documented fallback (Task 5 Step 9). `service_port` mirrors the merged `ip_service` modify-only pattern.
- **Fixture:** unchanged — uses the existing 8-NIC CHR (ether3 for the masquerade out-interface).
```