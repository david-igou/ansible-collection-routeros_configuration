# Data-Driven `configure` Role — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 41 per-path roles with a single data-driven `configure` role (over the unchanged `_reconcile` engine) that reconciles a `routeros_config` dict in a canonical dependency order, validated by focused behaviour scenarios plus one comprehensive scenario covering every CHR-applicable `api_modify` path.

**Architecture:** `configure` re-sorts the requested paths into a canonical dependency order (`rcfg_path_order`) then loops `_reconcile` over them. Input is `routeros_config`, a dict keyed by RouterOS slash path (`/ip/firewall/filter`) → `{data, purge, order, content}`. Cross-path dependency ordering is centralised in `configure`; within-path entry order and entry matching stay in `community.routeros.api_modify`.

**Tech Stack:** Ansible roles, `community.routeros` 3.20.0 (`api_modify`/`api_info`), molecule + the existing shared-state CHR (`default` scenario) on `david_igou.molecule_provisioners` qemu, CHR 7.21.4.

**Reference spec:** `docs/superpowers/specs/2026-06-04-data-driven-configure-design.md`

> **Branch:** `feat/data-driven-configure` (checked out; the spec is committed here).
>
> **CI note:** the molecule CI `shared` job runs `molecule test --all --exclude chr --exclude integration_hello_world` and auto-discovers scenarios, so deleting the 41 old scenarios and adding the `configure_*` ones needs **no workflow edit**. The shared-state infra (`default` scenario, `utils/`, 11-ether fixture, `config.yml`) is unchanged.

---

## Conventions

- Block-style YAML only (no flow-style `- {k: v}` in data).
- Each new molecule scenario's `molecule.yml` is **name-only** (the centralised `config.yml` supplies the trimmed `dependency → converge → idempotence → verify` sequence + provisioner wiring).
- **Connection vars in verify plays:** use `module_defaults` for `community.routeros.api_info` — Ansible's loader does NOT support YAML merge keys (`<<: *anchor`), so do not use anchors for this.
- Run one scenario against the shared CHR during development with:
  `MOLECULE_GLOB='extensions/molecule/*/molecule.yml' molecule test -s default -s <scenario>`
  (`default` boots/prepares/destroys the one CHR; `<scenario>` reuses it).

---

## Task 1: `configure` role — ordering logic + fast (no-CHR) test

The canonical-order sort is the one piece of real logic; it is testable without a device via `include_role` + `tasks_from`.

**Files:**
- Create: `roles/configure/vars/main.yml`
- Create: `roles/configure/tasks/order.yml`
- Create (test): `extensions/tests/test_configure_order.yml`

- [ ] **Step 1: Write the failing test** — `extensions/tests/test_configure_order.yml`

```yaml
---
# Fast, device-free test of configure's canonical path ordering. Runs only the
# role's order.yml (via tasks_from) and asserts rcfg_ordered_paths.
- name: Test configure path ordering
  hosts: localhost
  gather_facts: false
  vars:
    routeros_config:
      /ip/dhcp-server/lease:
        data: []
      /system/identity:
        data: []
      /ip/pool:
        data: []
      /ip/dhcp-server:
        data: []
      /interface/bridge:
        data: []
  tasks:
    - name: Compute the ordered paths
      ansible.builtin.include_role:
        name: configure
        tasks_from: order

    - name: Assert dependency order (parents before children) + unlisted last
      ansible.builtin.assert:
        that:
          - rcfg_ordered_paths == [
              '/interface/bridge', '/ip/pool',
              '/ip/dhcp-server', '/ip/dhcp-server/lease', '/system/identity']
        success_msg: "ordering correct: {{ rcfg_ordered_paths }}"
        fail_msg: "ordering wrong: {{ rcfg_ordered_paths }}"
```

- [ ] **Step 2: Run it; verify it FAILS** (role missing)

```bash
cd /workspace/ansible-collection-routeros_configuration
ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections}" \
  ansible-playbook -i localhost, extensions/tests/test_configure_order.yml
```
Expected: FAIL — `the role 'configure' was not found`.

- [ ] **Step 3: Write `roles/configure/vars/main.yml`**

```yaml
---
# Canonical apply order for routeros_config paths. Only the RELATIVE order of
# dependency-related paths matters; independent paths may sit anywhere, and any
# path NOT listed here is applied last (in declared order). Keys are slash paths
# (RouterOS notation), matching routeros_config keys.
rcfg_path_order:
  - /interface/ethernet
  - /interface/bonding
  - /interface/bridge
  - /interface/vlan
  - /interface/vxlan
  - /interface/gre
  - /interface/eoip
  - /interface/wireguard
  - /interface/bridge/settings
  - /interface/bridge/port
  - /interface/bridge/vlan
  - /interface/list
  - /interface/list/member
  - /interface/wireguard/peers
  - /interface/vrrp
  - /ip/pool
  - /ip/address
  - /ip/arp
  - /ip/vrf
  - /ip/dhcp-server
  - /ip/dhcp-server/network
  - /ip/dhcp-server/option
  - /ip/dhcp-server/lease
  - /ip/dhcp-client
  - /ip/dhcp-relay
  - /ip/dns
  - /ip/dns/static
  - /ip/route
  - /ip/service
  - /ip/ssh
  - /ip/settings
  - /ip/cloud
  - /ip/neighbor/discovery-settings
  - /ip/firewall/address-list
  - /ip/firewall/connection/tracking
  - /ip/firewall/service-port
  - /ip/firewall/filter
  - /ip/firewall/nat
  - /ip/firewall/mangle
  - /ip/firewall/raw
```

> Task 9 (comprehensive scenario) will extend this list with any additional
> CHR-applicable paths that have dependencies; entries added there follow the
> same parent-before-child rule.

- [ ] **Step 4: Write `roles/configure/tasks/order.yml`**

```yaml
---
# Sets rcfg_ordered_paths: routeros_config keys re-sorted into canonical
# dependency order. Uses select/reject (order-preserving) — NOT
# intersect/difference (set ops, order undefined).
- name: Order the requested paths by dependency
  ansible.builtin.set_fact:
    rcfg_ordered_paths: >-
      {{ (rcfg_path_order | select('in', routeros_config.keys() | list) | list)
         + (routeros_config.keys() | list | reject('in', rcfg_path_order) | list) }}
```

- [ ] **Step 5: Run the test; verify it PASSES**

```bash
ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections}" \
  ansible-playbook -i localhost, extensions/tests/test_configure_order.yml
```
Expected: PASS — `ordering correct: ['/interface/bridge', '/ip/pool', '/ip/dhcp-server', '/ip/dhcp-server/lease', '/system/identity']`.

- [ ] **Step 6: Commit**

```bash
git add roles/configure/vars/main.yml roles/configure/tasks/order.yml extensions/tests/test_configure_order.yml
git commit -m "feat(configure): canonical dependency ordering + device-free test"
```

---

## Task 2: `configure` role — main loop + metadata

**Files:**
- Create: `roles/configure/tasks/main.yml`, `roles/configure/defaults/main.yml`, `roles/configure/meta/main.yml`, `roles/configure/meta/argument_specs.yml`, `roles/configure/README.md`

- [ ] **Step 1: Write `roles/configure/defaults/main.yml`**

```yaml
---
# Desired RouterOS state, keyed by slash path (RouterOS notation). Each value:
#   data:    list of entry dicts (required)
#   purge:   bool — remove on-device entries not in data (default false)
#   order:   bool — enforce entry order (requires purge; default false)
#   content: ignore | remove | remove_as_much_as_possible (default ignore)
routeros_config: {}
```

- [ ] **Step 2: Write `roles/configure/tasks/main.yml`**

```yaml
---
# tasks file for david_igou.routeros_configuration.configure
- name: Compute the canonical apply order
  ansible.builtin.include_tasks: order.yml

- name: "Reconcile {{ rcfg_key }}"
  ansible.builtin.include_role:
    name: _reconcile
  loop: "{{ rcfg_ordered_paths }}"
  loop_control:
    loop_var: rcfg_key
  vars:
    # Slash path -> space-separated api_modify path: /ip/dhcp-server ->
    # "ip dhcp-server" (leading slash trimmed, inner slashes -> spaces).
    rcfg_path: "{{ rcfg_key | replace('/', ' ') | trim }}"
    rcfg_data: "{{ routeros_config[rcfg_key].data }}"
    rcfg_purge: "{{ routeros_config[rcfg_key].purge | default(false) }}"
    rcfg_order: "{{ routeros_config[rcfg_key].order | default(false) }}"
    rcfg_content: "{{ routeros_config[rcfg_key].content | default('ignore') }}"
```

- [ ] **Step 3: Write `roles/configure/meta/main.yml`**

```yaml
---
galaxy_info:
  author: David Igou
  description: Declaratively manage RouterOS over the API from one data structure.
  company: david_igou
  license: GPL-3.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - networking
dependencies: []
```

- [ ] **Step 4: Write `roles/configure/meta/argument_specs.yml`**

> `routeros_config` keys are arbitrary paths, so `argument_specs` validates only
> the top-level type (a dict). Per-entry structure is enforced by
> `_reconcile`/`api_modify` at apply time.

```yaml
---
argument_specs:
  main:
    short_description: Declaratively manage RouterOS paths from one data structure.
    description:
      - Reconciles each path in C(routeros_config) via the internal C(_reconcile)
        engine, in a canonical dependency order (see C(vars/main.yml)).
    options:
      routeros_config:
        type: dict
        default: {}
        description:
          - Desired state keyed by RouterOS slash path (e.g. C(/ip/pool)). Each
            value is a dict with C(data) (list, required) and optional C(purge),
            C(order) (bool), and C(content)
            (ignore/remove/remove_as_much_as_possible).
```

- [ ] **Step 5: Write `roles/configure/README.md`** — schema, ordering, and updates:

```markdown
# configure

Declaratively manage RouterOS over the binary API from a single data structure.
Replaces the per-path roles: every `community.routeros.api_modify` path is driven
by one `routeros_config` dict.

    routeros_config:
      /ip/pool:
        data:
          - name: lan
            ranges: "192.168.88.10-192.168.88.254"
      /ip/firewall/filter:
        purge: true
        order: true
        data:
          - chain: input
            action: accept
            comment: est
            connection-state: "established,related"
          - chain: input
            action: accept
            comment: mgmt
            protocol: tcp
            dst-port: "22,8728"
          - chain: input
            action: drop
            comment: drop-rest

## Per-path options

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `data` | list | required | desired entries for the path |
| `purge` | bool | `false` | remove on-device entries not in `data` |
| `order` | bool | `false` | enforce entry order (requires `purge`) |
| `content` | str | `ignore` | how to treat fields absent from a matched entry |

Keys are RouterOS **slash paths** (`/ip/firewall/filter`), mapped to the
space-separated `api_modify` path internally.

## Ordering & dependencies

`configure` applies paths in a canonical dependency order (`vars/main.yml`), so
`/ip/pool` precedes the `/ip/dhcp-server` that references it and a bridge precedes
its ports — regardless of how you write `routeros_config` or how it merges across
group_vars/host_vars. Unlisted paths apply last.

## How updates work

Reconciliation is `api_modify`'s. **Keyed paths** (e.g. `/ip/pool` by `name`)
match by primary key, so editing a non-key field updates in place. **Keyless
paths** (firewall, route, dns-static, arp) have no key — `api_modify` overwrites
the most-similar existing entry; for predictable firewall updates give each rule
a stable `comment` and use `purge: true` (+ `order: true`), since additive mode
adds an edited keyless rule as a duplicate.

Connection comes from the shared `routeros_api_*` vars (see the `_reconcile` role).
```

- [ ] **Step 6: Validate + lint**

```bash
cd /workspace/ansible-collection-routeros_configuration
ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz
ansible-galaxy collection install . --force
ansible-lint roles/configure
ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections}" \
  ansible-playbook -i localhost, extensions/tests/test_configure_order.yml
```
Expected: build OK; ansible-lint 0 failures; ordering test PASS.

- [ ] **Step 7: Commit**

```bash
git add roles/configure
git commit -m "feat(configure): data-driven entrypoint over the _reconcile engine"
```

---

## Task 3: Remove the 41 per-path roles and their molecule scenarios

- [ ] **Step 1: Delete the per-path roles**

```bash
cd /workspace/ansible-collection-routeros_configuration
for d in roles/*/; do
  name=$(basename "$d")
  [ "$name" = "_reconcile" ] || [ "$name" = "configure" ] || git rm -r "$d"
done
```

- [ ] **Step 2: Delete the per-path molecule scenarios**

```bash
for d in extensions/molecule/*/; do
  name=$(basename "$d")
  case "$name" in
    default|utils|chr|integration_hello_world) : ;;  # keep
    *) git rm -r "$d" ;;
  esac
done
```

- [ ] **Step 3: Confirm what remains**

Run: `ls roles/ && echo --- && ls extensions/molecule/`
Expected: `roles/` = `_reconcile  configure`; `extensions/molecule/` = `chr default integration_hello_world utils`.

- [ ] **Step 4: Build still succeeds**

Run: `ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz`
Expected: no error.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor!: replace the 41 per-path roles with the configure role"
```

---

## Tasks 4–8: Focused behaviour scenarios

Each scenario is `molecule.yml` (name-only) + `converge.yml` + `verify.yml`, run
with `molecule test -s default -s <scenario>`. Verify plays set the API
connection via `module_defaults` (NOT YAML anchors). The name-only `molecule.yml`
for every scenario below is:

```yaml
---
# Provisioner wiring, test_sequence, and verifier are centralised in
# extensions/molecule/config.yml. This file declares only the scenario name.
scenario:
  name: <SCENARIO_NAME>
```

### Task 4: `configure_lists` — keyed apply, in-place update, purge

**Files:** `extensions/molecule/configure_lists/{molecule,converge,verify}.yml`

- [ ] **Step 1:** Write `molecule.yml` from the template with `name: configure_lists`.

- [ ] **Step 2:** Write `converge.yml`

```yaml
---
- name: Converge — keyed list paths via configure
  hosts: molecule
  gather_facts: false
  vars:
    routeros_config:
      /ip/pool:
        data:
          - name: pool-a
            ranges: "192.168.60.10-192.168.60.50"
          - name: pool-b
            ranges: "192.168.61.10-192.168.61.50"
      /ip/dns/static:
        data:
          - name: router.lan
            address: "192.168.88.1"
  roles:
    - role: david_igou.routeros_configuration.configure
```

- [ ] **Step 3:** Write `verify.yml`

```yaml
---
- name: Verify — keyed apply, in-place update, purge
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  tasks:
    - name: Read /ip/pool after converge
      community.routeros.api_info:
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pools
    - name: Assert both pools present with ranges
      ansible.builtin.assert:
        that:
          - pools.result | selectattr('name','equalto','pool-a') | map(attribute='ranges') | first == '192.168.60.10-192.168.60.50'
          - pools.result | selectattr('name','equalto','pool-b') | list | length == 1

    - name: Update pool-a ranges (non-key field) and purge pool-b
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.configure
      vars:
        routeros_config:
          /ip/pool:
            purge: true
            data:
              - name: pool-a
                ranges: "192.168.70.10-192.168.70.50"

    - name: Read /ip/pool after update+purge
      community.routeros.api_info:
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pools2
    - name: Assert pool-a updated IN PLACE (matched by name) and pool-b purged
      ansible.builtin.assert:
        that:
          - pools2.result | selectattr('name','equalto','pool-a') | list | length == 1
          - pools2.result | selectattr('name','equalto','pool-a') | map(attribute='ranges') | first == '192.168.70.10-192.168.70.50'
          - pools2.result | selectattr('name','equalto','pool-b') | list | length == 0
        success_msg: "keyed update-in-place + purge correct"
        fail_msg: "unexpected: {{ pools2.result }}"
```

- [ ] **Step 4:** Run `molecule test -s default -s configure_lists` — PASSES.
- [ ] **Step 5:** Commit: `git add extensions/molecule/configure_lists && git commit -m "test(configure): keyed apply + in-place update + purge"`

### Task 5: `configure_singletons`

**Files:** `extensions/molecule/configure_singletons/{molecule,converge,verify}.yml`

- [ ] **Step 1:** `molecule.yml` from the template with `name: configure_singletons`.
- [ ] **Step 2:** `converge.yml`

```yaml
---
- name: Converge — singleton paths via configure
  hosts: molecule
  gather_facts: false
  vars:
    routeros_config:
      /system/identity:
        data:
          - name: configure-chr
      /ip/dns:
        data:
          - servers: "1.1.1.1,8.8.8.8"
            allow-remote-requests: false
      /ip/settings:
        data:
          - tcp-syncookies: true
  roles:
    - role: david_igou.routeros_configuration.configure
```

- [ ] **Step 3:** `verify.yml`

```yaml
---
- name: Verify — singletons applied
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  tasks:
    - name: Read /system/identity
      community.routeros.api_info:
        path: system identity
      delegate_to: localhost
      connection: local
      register: ident
    - name: Read /ip/dns
      community.routeros.api_info:
        path: ip dns
      delegate_to: localhost
      connection: local
      register: dns
    - name: Assert identity + dns applied
      ansible.builtin.assert:
        that:
          - ident.result | selectattr('name','equalto','configure-chr') | list | length == 1
          - dns.result | selectattr('servers','search','1.1.1.1') | list | length == 1
        fail_msg: "identity={{ ident.result }} dns={{ dns.result }}"
```

- [ ] **Step 4:** Run `molecule test -s default -s configure_singletons` — PASSES.
- [ ] **Step 5:** Commit: `git add extensions/molecule/configure_singletons && git commit -m "test(configure): singleton paths"`

### Task 6: `configure_ordered` — keyless firewall apply, order, in-place update

> Lockout-safe: input chain accepts `22,8728`; never drop management.

**Files:** `extensions/molecule/configure_ordered/{molecule,converge,verify}.yml`

- [ ] **Step 1:** `molecule.yml` from the template with `name: configure_ordered`.
- [ ] **Step 2:** `converge.yml`

```yaml
---
- name: Converge — ordered firewall filter via configure
  hosts: molecule
  gather_facts: false
  vars:
    routeros_config:
      /ip/firewall/filter:
        purge: true
        order: true
        content: remove_as_much_as_possible
        data:
          - chain: input
            action: accept
            connection-state: "established,related"
            comment: rule-a
          - chain: input
            action: accept
            protocol: tcp
            dst-port: "22,8728"
            comment: rule-b
          - chain: input
            action: drop
            comment: rule-c
  roles:
    - role: david_igou.routeros_configuration.configure
```

- [ ] **Step 3:** `verify.yml`

```yaml
---
- name: Verify — firewall order + keyless in-place update
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  tasks:
    - name: Read /ip/firewall/filter
      community.routeros.api_info:
        path: ip firewall filter
      delegate_to: localhost
      connection: local
      register: fw
    - name: Collect comments in device order
      ansible.builtin.set_fact:
        fw_comments: "{{ fw.result | map(attribute='comment') | list }}"
    - name: Assert rules in order a<b<c
      ansible.builtin.assert:
        that:
          - fw_comments.index('rule-a') < fw_comments.index('rule-b')
          - fw_comments.index('rule-b') < fw_comments.index('rule-c')

    - name: Update rule-a's connection-state (keyless, matched by comment)
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.configure
      vars:
        routeros_config:
          /ip/firewall/filter:
            purge: true
            order: true
            content: remove_as_much_as_possible
            data:
              - chain: input
                action: accept
                connection-state: "established"
                comment: rule-a
              - chain: input
                action: accept
                protocol: tcp
                dst-port: "22,8728"
                comment: rule-b
              - chain: input
                action: drop
                comment: rule-c

    - name: Read /ip/firewall/filter after update
      community.routeros.api_info:
        path: ip firewall filter
      delegate_to: localhost
      connection: local
      register: fw2
    - name: Assert still 3 rules; rule-a overwritten in place (not duplicated)
      ansible.builtin.assert:
        that:
          - fw2.result | selectattr('comment','defined') | selectattr('comment','equalto','rule-a') | list | length == 1
          - fw2.result | selectattr('comment','equalto','rule-a') | map(attribute='connection-state') | first == 'established'
          - (fw2.result | selectattr('comment','in',['rule-a','rule-b','rule-c']) | list | length) == 3
        success_msg: "keyless rule updated in place by comment; order preserved"
        fail_msg: "unexpected: {{ fw2.result }}"
```

- [ ] **Step 4:** Run `molecule test -s default -s configure_ordered` — PASSES.
- [ ] **Step 5:** Commit: `git add extensions/molecule/configure_ordered && git commit -m "test(configure): ordered firewall + keyless in-place update"`

### Task 7: `configure_modify_only`

**Files:** `extensions/molecule/configure_modify_only/{molecule,converge,verify}.yml`

- [ ] **Step 1:** `molecule.yml` from the template with `name: configure_modify_only`.
- [ ] **Step 2:** `converge.yml`

```yaml
---
- name: Converge — modify-only path via configure
  hosts: molecule
  gather_facts: false
  vars:
    routeros_config:
      /ip/service:
        data:
          - name: telnet
            disabled: true
  roles:
    - role: david_igou.routeros_configuration.configure
```

- [ ] **Step 3:** `verify.yml`

```yaml
---
- name: Verify — telnet service disabled
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  tasks:
    - name: Read /ip/service
      community.routeros.api_info:
        path: ip service
      delegate_to: localhost
      connection: local
      register: svc
    - name: Assert telnet disabled
      ansible.builtin.assert:
        that:
          - svc.result | selectattr('name','equalto','telnet') | selectattr('disabled','equalto',true) | list | length == 1
        fail_msg: "{{ svc.result | selectattr('name','equalto','telnet') | list }}"
```

- [ ] **Step 4:** Run `molecule test -s default -s configure_modify_only` — PASSES.
- [ ] **Step 5:** Commit: `git add extensions/molecule/configure_modify_only && git commit -m "test(configure): modify-only path"`

### Task 8: `configure_dependency_chain` — ordering guarantee on hardware

> Ports: bridge ports bind `ether7`/`ether8`; dhcp-server + list-member on `ether3` (coexist additively — same deconfliction as the shared-state work).

**Files:** `extensions/molecule/configure_dependency_chain/{molecule,converge,verify}.yml`

- [ ] **Step 1:** `molecule.yml` from the template with `name: configure_dependency_chain`.
- [ ] **Step 2:** `converge.yml` (dependencies authored OUT of order on purpose)

```yaml
---
- name: Converge — dependency chains in shuffled key order via configure
  hosts: molecule
  gather_facts: false
  vars:
    routeros_config:
      /ip/dhcp-server/lease:
        data:
          - server: dhcp-dep
            address: "192.168.62.100"
            mac-address: "00:11:22:33:44:99"
      /interface/bridge/port:
        data:
          - bridge: br-dep
            interface: ether7
          - bridge: br-dep
            interface: ether8
      /ip/dhcp-server:
        data:
          - name: dhcp-dep
            interface: ether3
            address-pool: pool-dep
            disabled: true
      /interface/list/member:
        data:
          - list: WAN-dep
            interface: ether3
      /interface/bridge:
        data:
          - name: br-dep
      /ip/pool:
        data:
          - name: pool-dep
            ranges: "192.168.62.10-192.168.62.50"
      /interface/list:
        data:
          - name: WAN-dep
  roles:
    - role: david_igou.routeros_configuration.configure
```

- [ ] **Step 3:** `verify.yml`

```yaml
---
- name: Verify — all dependent objects exist (ordering worked)
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  tasks:
    - name: Read bridge ports
      community.routeros.api_info:
        path: interface bridge port
      delegate_to: localhost
      connection: local
      register: ports
    - name: Read dhcp-server lease
      community.routeros.api_info:
        path: ip dhcp-server lease
      delegate_to: localhost
      connection: local
      register: leases
    - name: Read interface list member
      community.routeros.api_info:
        path: interface list member
      delegate_to: localhost
      connection: local
      register: members
    - name: Assert the full chains were created (so parents preceded children)
      ansible.builtin.assert:
        that:
          - ports.result | selectattr('bridge','equalto','br-dep') | list | length == 2
          - leases.result | selectattr('address','equalto','192.168.62.100') | list | length == 1
          - members.result | selectattr('list','equalto','WAN-dep') | list | length == 1
        success_msg: "ordering created bridge->ports, pool->server->lease, list->member"
        fail_msg: "ordering failed: ports={{ ports.result }} leases={{ leases.result }} members={{ members.result }}"
```

- [ ] **Step 4:** Run `molecule test -s default -s configure_dependency_chain` — PASSES.
- [ ] **Step 5:** Commit: `git add extensions/molecule/configure_dependency_chain && git commit -m "test(configure): cross-path dependency-ordering scenario"`

---

## Task 9: `configure_full` — comprehensive every-CHR-applicable-path scenario

**Goal:** one `configure` call applying **every `api_modify` path a stock CHR
accepts**, authored in shuffled order, proving reconciliation order and
idempotence at scale — and documenting (not silently skipping) the paths a CHR
can't do.

> **This task is partly empirical.** `api_modify` has 523 registry paths; a CHR
> can configure only a subset (no wifi/wireless/lte/ethernet-switch/hotspot/ipsec
> hardware, no licensed features, plus read-only/status paths). The applicable
> set is determined by probing a live CHR, then representative data is authored
> for each. Per-path data therefore emerges during execution — the steps below
> give the method and automation, not 200 literal entries.

**Files:**
- Create: `extensions/molecule/utils/scripts/probe_paths.yml` (discovery)
- Create: `extensions/molecule/configure_full/{molecule,converge,verify}.yml`
- Create: `extensions/molecule/configure_full/EXCLUSIONS.md` (documented exclusions)
- Modify: `roles/configure/vars/main.yml` (add any newly-covered dependency edges)

- [ ] **Step 1: Write the path-discovery playbook** — `extensions/molecule/utils/scripts/probe_paths.yml`

Probes every registry path with `api_info` on the live shared CHR and classifies
each as **present** (readable here) or **absent** (errors → feature/hardware not
on CHR). Writes `/tmp/chr_paths.json`.

```yaml
---
- name: Probe which api_modify paths exist on this CHR
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port }}"
  vars:
    # All 523 registry paths (space form). Generate this list once with:
    #   python3 -c "import sys;sys.path.insert(0,'$HOME/.ansible/collections'); \
    #     from ansible_collections.community.routeros.plugins.module_utils import _api_data as m; \
    #     print('\n'.join(sorted(' '.join(p) for p in m.PATHS)))"
    all_paths: "{{ lookup('file', 'all_api_modify_paths.txt').splitlines() }}"
  tasks:
    - name: Probe each path
      community.routeros.api_info:
        path: "{{ item }}"
      delegate_to: localhost
      connection: local
      loop: "{{ all_paths }}"
      loop_control:
        label: "{{ item }}"
      register: probe
      failed_when: false
    - name: Record present vs absent
      ansible.builtin.copy:
        dest: /tmp/chr_paths.json
        content: >-
          {{ {'present': probe.results | rejectattr('failed') | map(attribute='item') | list,
              'absent':  probe.results | selectattr('failed') | map(attribute='item') | list}
             | to_nice_json }}
      delegate_to: localhost
```

- [ ] **Step 2: Run discovery against the shared CHR**

```bash
cd /workspace/ansible-collection-routeros_configuration
python3 -c "import sys;sys.path.insert(0,'$HOME/.ansible/collections'); from ansible_collections.community.routeros.plugins.module_utils import _api_data as m; print('\n'.join(sorted(' '.join(p) for p in m.PATHS)))" > /tmp/all_api_modify_paths.txt
MOLECULE_GLOB='extensions/molecule/*/molecule.yml' molecule create -s default
MOLECULE_GLOB='extensions/molecule/*/molecule.yml' molecule prepare -s default
ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections}" \
  ansible-playbook -i extensions/molecule/utils/inventory/ \
  -e all_api_modify_paths.txt=/tmp/all_api_modify_paths.txt \
  extensions/molecule/utils/scripts/probe_paths.yml
cat /tmp/chr_paths.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('present:',len(d['present']),'absent:',len(d['absent']))"
```
Expected: a `present` list (the CHR-applicable candidate set) and an `absent` list.

- [ ] **Step 3: Build the applicable, writable path set**

From `present`, drop read-only/status paths (the registry marks these — a path
with no `primary_keys`/`single_value`/`fixed_entries` and no settable fields, or
names like `*active`, `*used`, `*connections`, `*stats`, `system resource*`,
`*print`). Keep the configurable ones. Record the dropped ones (with the reason)
for `EXCLUSIONS.md`.

- [ ] **Step 4: Author `extensions/molecule/configure_full/converge.yml`**

One `configure` call whose `routeros_config` contains a representative, valid
entry for **every** path from Step 3, with dependencies satisfied (reuse the
canonical chains: bridge→ports, pool→dhcp-server→lease/network/option,
list→member, wireguard→peers, address-list→firewall, etc.). Author keys in
**shuffled** order on purpose. Use the spare ethers (ether3–ether11) for any
port-binding entries, matching the fixture. Disable anything that would affect
reachability (dhcp-client/relay/server `disabled: true`; no management drops).

> Authoring guidance: for each path, take primary-key + required fields from the
> registry (`m.PATHS[(...)].unversioned.primary_keys` and the `required` fields,
> as catalogued for the earlier per-path roles), and a minimal valid value. Where
> a value normalises and breaks idempotence (the `ip_route` blackhole / `ip_cloud`
> class), pick the idempotent form found earlier. Build incrementally: add paths
> in batches and re-run Step 6 so a bad entry is easy to localise.

- [ ] **Step 5: Write `extensions/molecule/configure_full/molecule.yml`** (name-only, `name: configure_full`) **and `verify.yml`**

`verify.yml` asserts a representative sample across the pattern classes (a keyed
list entry, a singleton, an ordered chain in order, a dependency-chain object)
exists — the comprehensive guarantee is the converge succeeding (ordering) plus
the `idempotence` step passing (every entry reconciled cleanly). Use the
`module_defaults` connection pattern as in Tasks 4–8.

- [ ] **Step 6: Run it**

```bash
MOLECULE_GLOB='extensions/molecule/*/molecule.yml' molecule test -s default -s configure_full
```
Expected: converge applies every path (ordering correct ⇒ no missing-dependency
errors), `idempotence` is clean (every entry reconciled with no churn), verify
passes. Debug failures with `superpowers:systematic-debugging` — a converge
failure usually means a missing `rcfg_path_order` edge (add it) or invalid data;
an idempotence failure means a normalising value (pick the stable form).

- [ ] **Step 7: Write `extensions/molecule/configure_full/EXCLUSIONS.md`**

Table of every registry top-level group / path NOT covered, with the reason
(e.g. `interface/wifi, wireless, wifiwave2 — needs wireless hardware`;
`interface/lte — needs an LTE modem`; `interface/ethernet/switch — needs a switch
chip`; `ip/hotspot, ip/ipsec, dude, iot, lora, caps-man, user-manager — feature/
license/hardware not on a CHR`; `*active/*used/*stats/*connections — read-only
status`). This is the "no silent caps" record: a reader can see exactly what is
and isn't exercised, and why.

- [ ] **Step 8: Commit**

```bash
git add extensions/molecule/configure_full extensions/molecule/utils/scripts/probe_paths.yml roles/configure/vars/main.yml
git commit -m "test(configure): comprehensive every-CHR-applicable-path reconciliation-order scenario"
```

---

## Task 10: Documentation + changelog

**Files:** Modify `README.md`, `extensions/molecule/README.md`; create `changelogs/fragments/configure-role.yml`; delete superseded fragments.

- [ ] **Step 1: Rewrite the README Roles section** — replace the `## Roles` section and the `### Interface & bridge` / `### IP core` / `### IP firewall` tables with:

```markdown
## Roles

| Role | Purpose |
| --- | --- |
| `configure` | Declaratively manage RouterOS from one `routeros_config` data structure (the public entrypoint). |
| `_reconcile` | Internal engine — reconciles a single path via `community.routeros.api_modify`. Not called directly. |

Set `routeros_config` (keyed by RouterOS slash path) and run `configure`; state
is reconciled idempotently in a canonical dependency order. See
`roles/configure/README.md` for the schema, ordering, and how updates work. Any
path supported by `community.routeros.api_modify` is usable — no per-path role.
```

- [ ] **Step 2: Update `extensions/molecule/README.md`** — replace the per-role scenario descriptions with the `configure_*` set (`configure_lists`, `configure_singletons`, `configure_ordered`, `configure_modify_only`, `configure_dependency_chain`, `configure_full`), noting `configure_full` covers every CHR-applicable path (see its `EXCLUSIONS.md`). Keep the shared-state section.

- [ ] **Step 3: Write `changelogs/fragments/configure-role.yml`**

```yaml
---
breaking_changes:
  - >-
    The 41 per-path roles are replaced by a single ``configure`` role driven by a
    ``routeros_config`` dict keyed by RouterOS slash path. Adding a new path no
    longer requires a new role. The internal ``_reconcile`` engine is unchanged.
```

- [ ] **Step 4: Remove superseded changelog fragments** (only if not yet released)

```bash
git rm -f changelogs/fragments/routeros-config-roles.yml \
          changelogs/fragments/interface-bridge-roles.yml \
          changelogs/fragments/ip-core-roles.yml \
          changelogs/fragments/ip-firewall-roles.yml
```

- [ ] **Step 5: Commit**

```bash
git add README.md extensions/molecule/README.md changelogs/fragments/configure-role.yml
git commit -m "docs: document the configure role; changelog for the role collapse"
```

---

## Task 11: Full-suite validation + PR

- [ ] **Step 1: Build + lint**

```bash
cd /workspace/ansible-collection-routeros_configuration
ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz
ansible-galaxy collection install . --force
ansible-lint roles/configure roles/_reconcile
yamllint roles/configure extensions/molecule/configure_*
```
Expected: build OK; ansible-lint 0 failures; yamllint clean.

- [ ] **Step 2: Full shared-state pass on one CHR**

```bash
MOLECULE_GLOB='extensions/molecule/*/molecule.yml' \
  molecule test --all --exclude chr --exclude integration_hello_world
```
Expected: `default` boots one CHR; all `configure_*` scenarios (incl. `configure_full`) converge + idempotence + verify; one destroy. Debug any failure with `superpowers:systematic-debugging` before claiming completion.

- [ ] **Step 3: Clean tree** — `git status` clean.

- [ ] **Step 4: Push + PR + CI green**

```bash
git push -u origin feat/data-driven-configure
gh pr create --base master --title "refactor: replace 41 per-path roles with a data-driven configure role" --fill
```
Watch until molecule `shared` + `chr` and `all_green` pass.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** `configure` over `_reconcile` (Tasks 1–2) ✓; slash-keyed schema + per-path options (Task 2) ✓; order-preserving canonical ordering (Task 1) ✓; matching/updates delegated to `api_modify`, tested keyed (Task 4) + keyless (Task 6) ✓; remove 41 roles (Task 3) ✓; focused scenarios + dependency-chain (Tasks 4–8) ✓; comprehensive every-CHR-applicable-path scenario (Task 9) ✓; docs + breaking-change changelog (Task 10) ✓.
- **Comprehensive scenario realism:** Task 9 is discovery-driven by necessity (the CHR-applicable set of the 523 registry paths is empirical). The plan gives the probe automation, the authoring method, and a documented `EXCLUSIONS.md` (no silent caps) rather than 200 literal entries — those are produced during execution and validated by converge-succeeds (ordering) + idempotence-clean.
- **No CI matrix change:** the `shared` job already runs `--all`; scenario churn is auto-discovered.
- **No YAML merge keys** anywhere — verify plays use `module_defaults` (Ansible doesn't support `<<: *anchor`).
