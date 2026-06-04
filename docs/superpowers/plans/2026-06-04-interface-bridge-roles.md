# Interface + Bridge Roles — Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 15 declarative `/interface` (incl. bridge) roles, each a thin `_reconcile` wrapper with its own CHR molecule scenario, plus the shared 8-NIC CHR fixture and CI matrix entries.

**Architecture:** Identical to the merged `system_identity`/`ip_address`/`ip_firewall_filter` roles — each role maps `routeros_<role>` to the internal `_reconcile` engine which calls `community.routeros.api_modify`. Roles are `list`, `singleton`, or `modify-only` typed (no ordered paths in this plan). Each molecule scenario boots a fresh CHR (shared `extensions/molecule/utils/` bootstrap), creates any prerequisites in `converge`, and verifies via `api_info`.

**Tech Stack:** Ansible roles, `community.routeros` (api_modify/api_info + librouteros), molecule + `david_igou.molecule_provisioners` qemu, MikroTik CHR 7.21.4.

**Reference spec:** `docs/superpowers/specs/2026-06-04-interface-ip-bridge-roles-design.md`

---

## Templates (used by every role task below)

Each role lives in `roles/<role>/`. Three files are boilerplate produced from a template with substitutions; the per-role tasks below give the *distinguishing* files (`defaults`, `argument_specs`, `converge`, `verify`) in full.

### Template `meta/main.yml` (substitute `<DESC>` and `<TAG3>`)

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

### Template `README.md` (substitute `<ROLE>`, `<PATH>`, `<EXAMPLE>`)

```markdown
# <ROLE>

Declaratively manage `<PATH>` over the RouterOS API.

    <EXAMPLE>

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
```

### Template `tasks/main.yml` — **list** and **singleton** types (substitute `<ROLE>`, `<PATH>`)

```yaml
---
# tasks file for david_igou.routeros_configuration.<ROLE>
- name: "Reconcile <PATH>"
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: <PATH>
    rcfg_data: "{{ routeros_<ROLE> }}"
    rcfg_purge: "{{ routeros_<ROLE>_purge | default(false) }}"
    rcfg_order: false
```

> For **singleton** and **modify-only** roles `routeros_<ROLE>_purge` is not defined in defaults, so the `| default(false)` keeps purge off. For **list** roles it is defined and user-settable.

### Template `molecule/<role>/molecule.yml` (substitute `<ROLE>`)

```yaml
---
ansible:
  executor:
    args:
      ansible_playbook:
        - --inventory=../utils/inventory/
        - --inventory=${MOLECULE_EPHEMERAL_DIRECTORY}/inventory/
  playbooks:
    create: ../utils/playbooks/create.yml
    destroy: ../utils/playbooks/destroy.yml
    prepare: ../utils/playbooks/prepare.yml
    converge: converge.yml
    verify: verify.yml

scenario:
  name: <ROLE>
  test_sequence:
    - dependency
    - create
    - prepare
    - converge
    - idempotence
    - verify
    - destroy

verifier:
  name: ansible
```

### Verify helper pattern

Every `verify.yml` reads the path with this task (substitute `<PATH>`), then asserts on `q.result`:

```yaml
    - name: Read <PATH> over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: <PATH>
      delegate_to: localhost
      connection: local
      register: q
```

A converge that creates prerequisites does so with `community.routeros.api_modify`
tasks (same connection block, `path:` + `data:` + `handle_absent_entries: ignore`)
*before* the `include_role` of the role under test, OR by `include_role`ing the
relevant already-built role. Prereqs use api_modify directly to avoid coupling
scenarios to other roles.

---

## Task 1: Bump the shared CHR fixture to 8 ether NICs

**Files:**
- Modify: `extensions/molecule/utils/inventory/hosts.yml`

- [ ] **Step 1: Replace the `extra_args` block with 7 extra NICs (apinet=ether2, ether3–8)**

Replace the entire `extra_args:` list in `extensions/molecule/utils/inventory/hosts.yml` with:

```yaml
              extra_args:
                # apinet (ether2): own SLIRP subnet so its DHCP address differs
                # from ether1's 10.0.2.15 (shared subnet breaks API SYN-ACK
                # routing). hostfwd exposes the binary API to the controller.
                - -netdev
                - "user,id=apinet,net=10.0.3.0/24,hostfwd=tcp::8728-10.0.3.15:8728"
                - -device
                - "virtio-net-pci,netdev=apinet,mac=52:54:00:00:01:02"
                # ether3..ether8: spare SLIRP NICs for interface/bridge/bonding/
                # vlan scenarios to bind to. No host L2 reachability needed.
                - -netdev
                - "user,id=net2"
                - -device
                - "virtio-net-pci,netdev=net2,mac=52:54:00:00:01:03"
                - -netdev
                - "user,id=net3"
                - -device
                - "virtio-net-pci,netdev=net3,mac=52:54:00:00:01:04"
                - -netdev
                - "user,id=net4"
                - -device
                - "virtio-net-pci,netdev=net4,mac=52:54:00:00:01:05"
                - -netdev
                - "user,id=net5"
                - -device
                - "virtio-net-pci,netdev=net5,mac=52:54:00:00:01:06"
                - -netdev
                - "user,id=net6"
                - -device
                - "virtio-net-pci,netdev=net6,mac=52:54:00:00:01:07"
                - -netdev
                - "user,id=net7"
                - -device
                - "virtio-net-pci,netdev=net7,mac=52:54:00:00:01:08"
```

- [ ] **Step 2: Sanity-check an existing scenario still boots with 8 NICs**

Run: `make molecule SCENARIO=ip_address`
Expected: PASS (ether3/ether4 still exist; the extra NICs are additive).

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/utils/inventory/hosts.yml
git commit -m "test(molecule): expand shared CHR fixture to 8 ether NICs"
```

---

## Role tasks

Each role task creates 7 files (`defaults/main.yml`, `meta/main.yml`,
`meta/argument_specs.yml`, `tasks/main.yml`, `README.md`,
`extensions/molecule/<role>/{molecule,converge,verify}.yml`), runs
`make molecule SCENARIO=<role>`, and commits. `meta/main.yml`, `README.md`,
`tasks/main.yml`, and `molecule.yml` come from the Templates section with the
substitutions named in each task. Below, only the genuinely-varying files are
shown in full.

> **YAML caution (learned in Plan 0):** never put an unquoted `key: value` colon
> inside an argument_specs `description:` (quote the whole string), and keep
> molecule test data free of the admin password substring `molecule`.

### Task 2: `interface_ethernet` (modify-only list)

Sets fields on existing physical ports; never adds/removes. No `_purge`.

**Template subs:** `<ROLE>=interface_ethernet`, `<PATH>=interface ethernet`,
`<DESC>=Declaratively set fields on /interface/ethernet ports.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_ethernet:\n      - {name: ether3, comment: uplink, mtu: 1500}`.

**Files:**
- Create: `roles/interface_ethernet/{defaults,meta,tasks,README.md}` + `meta/argument_specs.yml`
- Create: `extensions/molecule/interface_ethernet/{molecule,converge,verify}.yml`

- [ ] **Step 1: `roles/interface_ethernet/defaults/main.yml`**

```yaml
---
# Field updates to existing /interface/ethernet ports (modify-only — you cannot
# add or remove physical ports). Match by name.
#   - {name: ether3, comment: "uplink", mtu: 1500}
routeros_interface_ethernet: []
```

- [ ] **Step 2: `roles/interface_ethernet/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Set fields on /interface/ethernet ports.
    options:
      routeros_interface_ethernet:
        type: list
        elements: dict
        default: []
        description: Ethernet port field updates, matched by name.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — from Templates with the subs above.

- [ ] **Step 4: `extensions/molecule/interface_ethernet/converge.yml`**

```yaml
---
- name: Converge — set a comment + mtu on ether3
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_ethernet:
      - {name: ether3, comment: "managed-by-ansible", mtu: 1400}
  roles:
    - role: david_igou.routeros_configuration.interface_ethernet
```

- [ ] **Step 5: `extensions/molecule/interface_ethernet/verify.yml`**

```yaml
---
- name: Verify — ether3 has the managed comment and mtu
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface ethernet over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface ethernet
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert ether3 was updated
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','ether3') | selectattr('comment','equalto','managed-by-ansible') | list | length == 1
        fail_msg: "ether3 not updated: {{ q.result | selectattr('name','equalto','ether3') | list }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_ethernet` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_ethernet extensions/molecule/interface_ethernet && git commit -m "feat(interface_ethernet): set fields on ethernet ports + scenario"`

### Task 3: `interface_bridge` (list)

**Template subs:** `<ROLE>=interface_bridge`, `<PATH>=interface bridge`,
`<DESC>=Declaratively manage /interface/bridge.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_bridge:\n      - {name: bridge1, comment: lan}`.

- [ ] **Step 1: `roles/interface_bridge/defaults/main.yml`**

```yaml
---
# /interface/bridge entries.
#   - {name: bridge1, comment: "lan", vlan-filtering: false}
routeros_interface_bridge: []
routeros_interface_bridge_purge: false
```

- [ ] **Step 2: `roles/interface_bridge/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/bridge declaratively.
    options:
      routeros_interface_bridge:
        type: list
        elements: dict
        default: []
        description: Bridge interfaces.
      routeros_interface_bridge_purge:
        type: bool
        default: false
        description: Remove bridges not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_bridge/converge.yml`**

```yaml
---
- name: Converge — create two bridges
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_bridge:
      - {name: br-lan, comment: "lan"}
      - {name: br-dmz, comment: "dmz"}
  roles:
    - role: david_igou.routeros_configuration.interface_bridge
```

- [ ] **Step 5: `extensions/molecule/interface_bridge/verify.yml`**

```yaml
---
- name: Verify — both bridges exist
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface bridge over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert both bridges present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','br-lan') | list | length == 1
          - q.result | selectattr('name','equalto','br-dmz') | list | length == 1
        fail_msg: "bridges missing: {{ q.result | map(attribute='name') | list }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_bridge` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_bridge extensions/molecule/interface_bridge && git commit -m "feat(interface_bridge): declarative bridges + scenario"`

### Task 4: `interface_bridge_port` (list; prereq: a bridge)

**Template subs:** `<ROLE>=interface_bridge_port`, `<PATH>=interface bridge port`,
`<DESC>=Declaratively manage /interface/bridge/port membership.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_bridge_port:\n      - {bridge: bridge1, interface: ether3}`.

- [ ] **Step 1: `roles/interface_bridge_port/defaults/main.yml`**

```yaml
---
# Bridge port membership.
#   - {bridge: bridge1, interface: ether3, pvid: 10}
routeros_interface_bridge_port: []
routeros_interface_bridge_port_purge: false
```

- [ ] **Step 2: `roles/interface_bridge_port/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/bridge/port declaratively.
    options:
      routeros_interface_bridge_port:
        type: list
        elements: dict
        default: []
        description: Bridge port memberships.
      routeros_interface_bridge_port_purge:
        type: bool
        default: false
        description: Remove port memberships not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_bridge_port/converge.yml`** (creates a bridge first via api_modify)

```yaml
---
- name: Converge — bridge prereq, then add ether3/ether4 as ports
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create br-test
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge
        handle_absent_entries: ignore
        data:
          - {name: br-test}
      delegate_to: localhost
      connection: local

    - name: Apply bridge ports
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.interface_bridge_port
      vars:
        routeros_interface_bridge_port:
          - {bridge: br-test, interface: ether3}
          - {bridge: br-test, interface: ether4}
```

- [ ] **Step 5: `extensions/molecule/interface_bridge_port/verify.yml`**

```yaml
---
- name: Verify — ether3 and ether4 are ports of br-test
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface bridge port over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge port
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert both ports present on br-test
      ansible.builtin.assert:
        that:
          - q.result | selectattr('bridge','equalto','br-test') | selectattr('interface','equalto','ether3') | list | length == 1
          - q.result | selectattr('bridge','equalto','br-test') | selectattr('interface','equalto','ether4') | list | length == 1
        fail_msg: "ports missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_bridge_port` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_bridge_port extensions/molecule/interface_bridge_port && git commit -m "feat(interface_bridge_port): bridge port membership + scenario"`

### Task 5: `interface_bridge_vlan` (list; prereq: a bridge)

**Template subs:** `<ROLE>=interface_bridge_vlan`, `<PATH>=interface bridge vlan`,
`<DESC>=Declaratively manage /interface/bridge/vlan.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_bridge_vlan:\n      - {bridge: bridge1, vlan-ids: 10, tagged: bridge1}`.

- [ ] **Step 1: `roles/interface_bridge_vlan/defaults/main.yml`**

```yaml
---
# Bridge VLAN table entries.
#   - {bridge: bridge1, vlan-ids: 10, tagged: "bridge1,ether3", untagged: ether4}
routeros_interface_bridge_vlan: []
routeros_interface_bridge_vlan_purge: false
```

- [ ] **Step 2: `roles/interface_bridge_vlan/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/bridge/vlan declaratively.
    options:
      routeros_interface_bridge_vlan:
        type: list
        elements: dict
        default: []
        description: Bridge VLAN table entries.
      routeros_interface_bridge_vlan_purge:
        type: bool
        default: false
        description: Remove bridge VLAN entries not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_bridge_vlan/converge.yml`**

```yaml
---
- name: Converge — bridge prereq, then add a bridge VLAN entry
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create br-test
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge
        handle_absent_entries: ignore
        data:
          - {name: br-test}
      delegate_to: localhost
      connection: local

    - name: Apply bridge VLAN
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.interface_bridge_vlan
      vars:
        routeros_interface_bridge_vlan:
          - {bridge: br-test, vlan-ids: "20", tagged: "br-test"}
```

- [ ] **Step 5: `extensions/molecule/interface_bridge_vlan/verify.yml`**

```yaml
---
- name: Verify — bridge VLAN 20 present on br-test
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface bridge vlan over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge vlan
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert VLAN 20 present on br-test
      ansible.builtin.assert:
        that:
          - q.result | selectattr('bridge','equalto','br-test') | selectattr('vlan-ids','equalto','20') | list | length == 1
        fail_msg: "bridge vlan missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_bridge_vlan` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_bridge_vlan extensions/molecule/interface_bridge_vlan && git commit -m "feat(interface_bridge_vlan): bridge VLAN table + scenario"`

### Task 6: `interface_bridge_settings` (singleton)

**Template subs:** `<ROLE>=interface_bridge_settings`, `<PATH>=interface bridge settings`,
`<DESC>=Declaratively manage /interface/bridge/settings.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_bridge_settings:\n      - {use-ip-firewall: true}`.

- [ ] **Step 1: `roles/interface_bridge_settings/defaults/main.yml`**

```yaml
---
# Singleton /interface/bridge/settings. Single-element list of fields.
#   - {use-ip-firewall: true}
routeros_interface_bridge_settings: []
```

- [ ] **Step 2: `roles/interface_bridge_settings/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/bridge/settings declaratively.
    options:
      routeros_interface_bridge_settings:
        type: list
        elements: dict
        default: []
        description: Single-element list of bridge global settings fields.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_bridge_settings/converge.yml`**

```yaml
---
- name: Converge — enable use-ip-firewall
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_bridge_settings:
      - {use-ip-firewall: true}
  roles:
    - role: david_igou.routeros_configuration.interface_bridge_settings
```

- [ ] **Step 5: `extensions/molecule/interface_bridge_settings/verify.yml`**

```yaml
---
- name: Verify — use-ip-firewall is enabled
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface bridge settings over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bridge settings
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert use-ip-firewall true
      ansible.builtin.assert:
        that:
          - q.result | selectattr('use-ip-firewall','equalto','true') | list | length == 1
        fail_msg: "settings unexpected: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_bridge_settings` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_bridge_settings extensions/molecule/interface_bridge_settings && git commit -m "feat(interface_bridge_settings): bridge global settings + scenario"`

### Task 7: `interface_vlan` (list; prereq: parent ether)

**Template subs:** `<ROLE>=interface_vlan`, `<PATH>=interface vlan`,
`<DESC>=Declaratively manage /interface/vlan.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_vlan:\n      - {name: vlan10, vlan-id: 10, interface: ether3}`.

- [ ] **Step 1: `roles/interface_vlan/defaults/main.yml`**

```yaml
---
# /interface/vlan entries.
#   - {name: vlan10, vlan-id: 10, interface: ether3}
routeros_interface_vlan: []
routeros_interface_vlan_purge: false
```

- [ ] **Step 2: `roles/interface_vlan/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/vlan declaratively.
    options:
      routeros_interface_vlan:
        type: list
        elements: dict
        default: []
        description: 802.1Q VLAN interfaces.
      routeros_interface_vlan_purge:
        type: bool
        default: false
        description: Remove VLAN interfaces not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_vlan/converge.yml`** (parent ether3 already exists)

```yaml
---
- name: Converge — VLAN 30 on ether3
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_vlan:
      - {name: vlan30, vlan-id: 30, interface: ether3}
  roles:
    - role: david_igou.routeros_configuration.interface_vlan
```

- [ ] **Step 5: `extensions/molecule/interface_vlan/verify.yml`**

```yaml
---
- name: Verify — vlan30 exists on ether3
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface vlan over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface vlan
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert vlan30 present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','vlan30') | selectattr('vlan-id','equalto','30') | list | length == 1
        fail_msg: "vlan missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_vlan` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_vlan extensions/molecule/interface_vlan && git commit -m "feat(interface_vlan): VLAN interfaces + scenario"`

### Task 8: `interface_bonding` (list; prereq: 2 free ethers)

**Template subs:** `<ROLE>=interface_bonding`, `<PATH>=interface bonding`,
`<DESC>=Declaratively manage /interface/bonding.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_bonding:\n      - {name: bond1, slaves: "ether5,ether6"}`.

- [ ] **Step 1: `roles/interface_bonding/defaults/main.yml`**

```yaml
---
# /interface/bonding entries.
#   - {name: bond1, slaves: "ether5,ether6", mode: 802.3ad}
routeros_interface_bonding: []
routeros_interface_bonding_purge: false
```

- [ ] **Step 2: `roles/interface_bonding/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/bonding declaratively.
    options:
      routeros_interface_bonding:
        type: list
        elements: dict
        default: []
        description: Bonding (link aggregation) interfaces.
      routeros_interface_bonding_purge:
        type: bool
        default: false
        description: Remove bonds not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_bonding/converge.yml`** (ether5/ether6 are free spares)

```yaml
---
- name: Converge — bond ether5+ether6
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_bonding:
      - {name: bond-test, slaves: "ether5,ether6", mode: balance-rr}
  roles:
    - role: david_igou.routeros_configuration.interface_bonding
```

- [ ] **Step 5: `extensions/molecule/interface_bonding/verify.yml`**

```yaml
---
- name: Verify — bond-test exists with both slaves
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface bonding over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface bonding
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert bond-test present with slaves
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','bond-test') | selectattr('slaves','equalto','ether5,ether6') | list | length == 1
        fail_msg: "bond missing/wrong: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_bonding` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_bonding extensions/molecule/interface_bonding && git commit -m "feat(interface_bonding): bonding interfaces + scenario"`

### Task 9: `interface_list` (list)

**Template subs:** `<ROLE>=interface_list`, `<PATH>=interface list`,
`<DESC>=Declaratively manage /interface/list.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_list:\n      - {name: WAN}`.

- [ ] **Step 1: `roles/interface_list/defaults/main.yml`**

```yaml
---
# /interface/list groupings.
#   - {name: WAN, comment: "uplinks"}
routeros_interface_list: []
routeros_interface_list_purge: false
```

- [ ] **Step 2: `roles/interface_list/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/list declaratively.
    options:
      routeros_interface_list:
        type: list
        elements: dict
        default: []
        description: Interface lists (logical groupings).
      routeros_interface_list_purge:
        type: bool
        default: false
        description: Remove lists not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_list/converge.yml`**

```yaml
---
- name: Converge — create WAN and LAN lists
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_list:
      - {name: WAN}
      - {name: LAN}
  roles:
    - role: david_igou.routeros_configuration.interface_list
```

- [ ] **Step 5: `extensions/molecule/interface_list/verify.yml`**

```yaml
---
- name: Verify — WAN and LAN lists exist
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface list over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface list
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert WAN and LAN present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','WAN') | list | length == 1
          - q.result | selectattr('name','equalto','LAN') | list | length == 1
        fail_msg: "lists missing: {{ q.result | map(attribute='name') | list }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_list` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_list extensions/molecule/interface_list && git commit -m "feat(interface_list): interface lists + scenario"`

### Task 10: `interface_list_member` (list; prereq: a list)

**Template subs:** `<ROLE>=interface_list_member`, `<PATH>=interface list member`,
`<DESC>=Declaratively manage /interface/list/member.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_list_member:\n      - {list: WAN, interface: ether3}`.

- [ ] **Step 1: `roles/interface_list_member/defaults/main.yml`**

```yaml
---
# /interface/list/member entries.
#   - {list: WAN, interface: ether3}
routeros_interface_list_member: []
routeros_interface_list_member_purge: false
```

- [ ] **Step 2: `roles/interface_list_member/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/list/member declaratively.
    options:
      routeros_interface_list_member:
        type: list
        elements: dict
        default: []
        description: Interface list memberships.
      routeros_interface_list_member_purge:
        type: bool
        default: false
        description: Remove memberships not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_list_member/converge.yml`**

```yaml
---
- name: Converge — list prereq, then add ether3 to WAN
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create WAN list
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface list
        handle_absent_entries: ignore
        data:
          - {name: WAN}
      delegate_to: localhost
      connection: local

    - name: Apply membership
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.interface_list_member
      vars:
        routeros_interface_list_member:
          - {list: WAN, interface: ether3}
```

- [ ] **Step 5: `extensions/molecule/interface_list_member/verify.yml`**

```yaml
---
- name: Verify — ether3 is a member of WAN
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface list member over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface list member
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert ether3 in WAN
      ansible.builtin.assert:
        that:
          - q.result | selectattr('list','equalto','WAN') | selectattr('interface','equalto','ether3') | list | length == 1
        fail_msg: "membership missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_list_member` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_list_member extensions/molecule/interface_list_member && git commit -m "feat(interface_list_member): interface list membership + scenario"`

### Task 11: `interface_vrrp` (list; prereq: parent ether)

**Template subs:** `<ROLE>=interface_vrrp`, `<PATH>=interface vrrp`,
`<DESC>=Declaratively manage /interface/vrrp.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_vrrp:\n      - {name: vrrp1, interface: ether3, vrid: 1}`.

- [ ] **Step 1: `roles/interface_vrrp/defaults/main.yml`**

```yaml
---
# /interface/vrrp entries.
#   - {name: vrrp1, interface: ether3, vrid: 1, priority: 100}
routeros_interface_vrrp: []
routeros_interface_vrrp_purge: false
```

- [ ] **Step 2: `roles/interface_vrrp/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/vrrp declaratively.
    options:
      routeros_interface_vrrp:
        type: list
        elements: dict
        default: []
        description: VRRP virtual-router interfaces.
      routeros_interface_vrrp_purge:
        type: bool
        default: false
        description: Remove VRRP interfaces not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_vrrp/converge.yml`**

```yaml
---
- name: Converge — VRRP vrid 7 on ether3
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_vrrp:
      - {name: vrrp-test, interface: ether3, vrid: 7}
  roles:
    - role: david_igou.routeros_configuration.interface_vrrp
```

- [ ] **Step 5: `extensions/molecule/interface_vrrp/verify.yml`**

```yaml
---
- name: Verify — vrrp-test exists
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface vrrp over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface vrrp
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert vrrp-test present with vrid 7
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','vrrp-test') | selectattr('vrid','equalto','7') | list | length == 1
        fail_msg: "vrrp missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_vrrp` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_vrrp extensions/molecule/interface_vrrp && git commit -m "feat(interface_vrrp): VRRP interfaces + scenario"`

### Task 12: `interface_vxlan` (list)

**Template subs:** `<ROLE>=interface_vxlan`, `<PATH>=interface vxlan`,
`<DESC>=Declaratively manage /interface/vxlan.`, `<TAG3>=networking`,
`<EXAMPLE>=routeros_interface_vxlan:\n      - {name: vxlan1, vni: 100}`.

- [ ] **Step 1: `roles/interface_vxlan/defaults/main.yml`**

```yaml
---
# /interface/vxlan entries.
#   - {name: vxlan1, vni: 100, port: 4789}
routeros_interface_vxlan: []
routeros_interface_vxlan_purge: false
```

- [ ] **Step 2: `roles/interface_vxlan/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/vxlan declaratively.
    options:
      routeros_interface_vxlan:
        type: list
        elements: dict
        default: []
        description: VXLAN tunnel interfaces.
      routeros_interface_vxlan_purge:
        type: bool
        default: false
        description: Remove VXLAN interfaces not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_vxlan/converge.yml`**

```yaml
---
- name: Converge — VXLAN vni 100
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_vxlan:
      - {name: vxlan-test, vni: 100}
  roles:
    - role: david_igou.routeros_configuration.interface_vxlan
```

- [ ] **Step 5: `extensions/molecule/interface_vxlan/verify.yml`**

```yaml
---
- name: Verify — vxlan-test exists with vni 100
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface vxlan over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface vxlan
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert vxlan-test present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','vxlan-test') | selectattr('vni','equalto','100') | list | length == 1
        fail_msg: "vxlan missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_vxlan` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_vxlan extensions/molecule/interface_vxlan && git commit -m "feat(interface_vxlan): VXLAN interfaces + scenario"`

### Task 13: `interface_wireguard` (list)

**Template subs:** `<ROLE>=interface_wireguard`, `<PATH>=interface wireguard`,
`<DESC>=Declaratively manage /interface/wireguard.`, `<TAG3>=vpn`,
`<EXAMPLE>=routeros_interface_wireguard:\n      - {name: wg0, listen-port: 13231}`.

- [ ] **Step 1: `roles/interface_wireguard/defaults/main.yml`**

```yaml
---
# /interface/wireguard entries. RouterOS auto-generates keys if omitted.
#   - {name: wg0, listen-port: 13231}
routeros_interface_wireguard: []
routeros_interface_wireguard_purge: false
```

- [ ] **Step 2: `roles/interface_wireguard/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/wireguard declaratively.
    options:
      routeros_interface_wireguard:
        type: list
        elements: dict
        default: []
        description: WireGuard interfaces.
      routeros_interface_wireguard_purge:
        type: bool
        default: false
        description: Remove WireGuard interfaces not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_wireguard/converge.yml`**

```yaml
---
- name: Converge — wg-test interface
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_wireguard:
      - {name: wg-test, listen-port: 13231}
  roles:
    - role: david_igou.routeros_configuration.interface_wireguard
```

- [ ] **Step 5: `extensions/molecule/interface_wireguard/verify.yml`**

```yaml
---
- name: Verify — wg-test exists
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface wireguard over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface wireguard
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert wg-test present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','wg-test') | list | length == 1
        fail_msg: "wireguard missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_wireguard` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_wireguard extensions/molecule/interface_wireguard && git commit -m "feat(interface_wireguard): WireGuard interfaces + scenario"`

### Task 14: `interface_wireguard_peers` (list; prereq: a wireguard interface)

**Template subs:** `<ROLE>=interface_wireguard_peers`, `<PATH>=interface wireguard peers`,
`<DESC>=Declaratively manage /interface/wireguard/peers.`, `<TAG3>=vpn`,
`<EXAMPLE>=routeros_interface_wireguard_peers:\n      - {interface: wg0, public-key: "...", allowed-address: "10.0.0.2/32"}`.

- [ ] **Step 1: `roles/interface_wireguard_peers/defaults/main.yml`**

```yaml
---
# /interface/wireguard/peers entries.
#   - {interface: wg0, public-key: "<base64>", allowed-address: "10.0.0.2/32"}
routeros_interface_wireguard_peers: []
routeros_interface_wireguard_peers_purge: false
```

- [ ] **Step 2: `roles/interface_wireguard_peers/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/wireguard/peers declaratively.
    options:
      routeros_interface_wireguard_peers:
        type: list
        elements: dict
        default: []
        description: WireGuard peers.
      routeros_interface_wireguard_peers_purge:
        type: bool
        default: false
        description: Remove peers not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_wireguard_peers/converge.yml`** (creates a wg interface, uses a fixed test public key)

```yaml
---
- name: Converge — wireguard interface prereq, then a peer
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Prereq — create wg-test interface
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface wireguard
        handle_absent_entries: ignore
        data:
          - {name: wg-test, listen-port: 13231}
      delegate_to: localhost
      connection: local

    - name: Apply a peer
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.interface_wireguard_peers
      vars:
        routeros_interface_wireguard_peers:
          - interface: wg-test
            public-key: "JRI5Acni4bnH0+L0wA0sFV0iHs3J0jVnp3hQ8j0wYy0="
            allowed-address: "10.10.10.2/32"
```

- [ ] **Step 5: `extensions/molecule/interface_wireguard_peers/verify.yml`**

```yaml
---
- name: Verify — the peer exists on wg-test
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface wireguard peers over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface wireguard peers
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert the peer is present on wg-test
      ansible.builtin.assert:
        that:
          - q.result | selectattr('interface','equalto','wg-test') | selectattr('allowed-address','equalto','10.10.10.2/32') | list | length == 1
        fail_msg: "peer missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_wireguard_peers` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_wireguard_peers extensions/molecule/interface_wireguard_peers && git commit -m "feat(interface_wireguard_peers): WireGuard peers + scenario"`

### Task 15: `interface_gre` (list)

**Template subs:** `<ROLE>=interface_gre`, `<PATH>=interface gre`,
`<DESC>=Declaratively manage /interface/gre.`, `<TAG3>=vpn`,
`<EXAMPLE>=routeros_interface_gre:\n      - {name: gre1, remote-address: 203.0.113.5}`.

- [ ] **Step 1: `roles/interface_gre/defaults/main.yml`**

```yaml
---
# /interface/gre tunnels.
#   - {name: gre1, remote-address: 203.0.113.5, local-address: 192.0.2.1}
routeros_interface_gre: []
routeros_interface_gre_purge: false
```

- [ ] **Step 2: `roles/interface_gre/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/gre declaratively.
    options:
      routeros_interface_gre:
        type: list
        elements: dict
        default: []
        description: GRE tunnel interfaces.
      routeros_interface_gre_purge:
        type: bool
        default: false
        description: Remove GRE tunnels not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_gre/converge.yml`**

```yaml
---
- name: Converge — gre-test tunnel
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_gre:
      - {name: gre-test, remote-address: "203.0.113.5"}
  roles:
    - role: david_igou.routeros_configuration.interface_gre
```

- [ ] **Step 5: `extensions/molecule/interface_gre/verify.yml`**

```yaml
---
- name: Verify — gre-test exists
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface gre over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface gre
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert gre-test present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','gre-test') | selectattr('remote-address','equalto','203.0.113.5') | list | length == 1
        fail_msg: "gre missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_gre` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_gre extensions/molecule/interface_gre && git commit -m "feat(interface_gre): GRE tunnels + scenario"`

### Task 16: `interface_eoip` (list)

**Template subs:** `<ROLE>=interface_eoip`, `<PATH>=interface eoip`,
`<DESC>=Declaratively manage /interface/eoip.`, `<TAG3>=vpn`,
`<EXAMPLE>=routeros_interface_eoip:\n      - {name: eoip1, remote-address: 203.0.113.5, tunnel-id: 1}`.

- [ ] **Step 1: `roles/interface_eoip/defaults/main.yml`**

```yaml
---
# /interface/eoip tunnels.
#   - {name: eoip1, remote-address: 203.0.113.5, tunnel-id: 1}
routeros_interface_eoip: []
routeros_interface_eoip_purge: false
```

- [ ] **Step 2: `roles/interface_eoip/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /interface/eoip declaratively.
    options:
      routeros_interface_eoip:
        type: list
        elements: dict
        default: []
        description: EoIP tunnel interfaces.
      routeros_interface_eoip_purge:
        type: bool
        default: false
        description: Remove EoIP tunnels not present in the list.
```

- [ ] **Step 3: meta/main.yml, README.md, tasks/main.yml, molecule.yml** — Templates + subs.
- [ ] **Step 4: `extensions/molecule/interface_eoip/converge.yml`**

```yaml
---
- name: Converge — eoip-test tunnel
  hosts: molecule
  gather_facts: false
  vars:
    routeros_interface_eoip:
      - {name: eoip-test, remote-address: "203.0.113.5", tunnel-id: 1}
  roles:
    - role: david_igou.routeros_configuration.interface_eoip
```

- [ ] **Step 5: `extensions/molecule/interface_eoip/verify.yml`**

```yaml
---
- name: Verify — eoip-test exists
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read interface eoip over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: interface eoip
      delegate_to: localhost
      connection: local
      register: q
    - name: Assert eoip-test present
      ansible.builtin.assert:
        that:
          - q.result | selectattr('name','equalto','eoip-test') | selectattr('tunnel-id','equalto','1') | list | length == 1
        fail_msg: "eoip missing: {{ q.result }}"
```

- [ ] **Step 6: Run** `make molecule SCENARIO=interface_eoip` → PASS.
- [ ] **Step 7: Commit** `git add roles/interface_eoip extensions/molecule/interface_eoip && git commit -m "feat(interface_eoip): EoIP tunnels + scenario"`

---

## Task 17: CI matrix + docs

**Files:**
- Modify: `.github/workflows/tests.yml`
- Modify: `README.md`, `extensions/molecule/README.md`
- Create: `changelogs/fragments/interface-bridge-roles.yml`

- [ ] **Step 1: Add the 15 scenarios to the molecule-qemu matrix**

In `.github/workflows/tests.yml`, under `matrix: scenario:`, append (after the existing four):

```yaml
          - interface_ethernet
          - interface_bridge
          - interface_bridge_port
          - interface_bridge_vlan
          - interface_bridge_settings
          - interface_vlan
          - interface_bonding
          - interface_list
          - interface_list_member
          - interface_vrrp
          - interface_vxlan
          - interface_wireguard
          - interface_wireguard_peers
          - interface_gre
          - interface_eoip
```

- [ ] **Step 2: Add the roles to the top-level README "Roles" table**

In `README.md`, add a row per interface role under the existing Roles table (role | path | one-line note). Group them after the IP rows or in an "Interface" subsection.

- [ ] **Step 3: Add a scenarios note to `extensions/molecule/README.md`**

Add a line under `## Scenarios` noting the 15 interface scenarios share the `utils/` bootstrap and the 8-NIC CHR fixture.

- [ ] **Step 4: Changelog fragment** `changelogs/fragments/interface-bridge-roles.yml`

```yaml
---
minor_changes:
  - >-
    Add declarative roles for the /interface and /interface/bridge subsystems:
    interface_ethernet, interface_bridge(+port/vlan/settings), interface_vlan,
    interface_bonding, interface_list(+member), interface_vrrp, interface_vxlan,
    interface_wireguard(+peers), interface_gre, and interface_eoip — each with a
    CHR molecule scenario.
```

- [ ] **Step 5: Validate workflow YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/tests.yml README.md extensions/molecule/README.md changelogs/fragments/interface-bridge-roles.yml
git commit -m "ci+docs: run the interface/bridge scenarios; document the roles"
```

---

## Task 18: Full local verification of the new scenarios

- [ ] **Step 1: Run each new scenario once** (already done per-role, but confirm none regressed after the NIC bump)

Run, expecting PASS for each:
```bash
for s in interface_ethernet interface_bridge interface_bridge_port interface_bridge_vlan \
         interface_bridge_settings interface_vlan interface_bonding interface_list \
         interface_list_member interface_vrrp interface_vxlan interface_wireguard \
         interface_wireguard_peers interface_gre interface_eoip; do
  echo "=== $s ==="; make molecule SCENARIO=$s || echo "FAILED: $s"; done
```
Expected: every scenario reports `failed=0`. Debug any failure with `superpowers:systematic-debugging` before proceeding.

- [ ] **Step 2: Push and open a PR to master; ensure CI is green** (per the merged Plan-0 workflow). Fix any CI-only ansible-lint/sanity issues, then the branch is ready to merge.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** all 15 Plan-1 roles present (Tasks 2–16) with correct types (interface_ethernet modify-only; interface_bridge_settings singleton; rest lists) ✓; 8-NIC fixture (Task 1) ✓; one scenario per role ✓; prerequisite chains handled in converge (bridge_port/bridge_vlan create a bridge; list_member creates a list; wireguard_peers creates a wg interface; vlan/vrrp/bonding use spare ethers) ✓; CI matrix + docs (Task 17) ✓.
- **Field-name caution:** RouterOS fields use hyphens (`vlan-id`, `remote-address`, `allowed-address`, `use-ip-firewall`); pass them as quoted YAML keys inside the dicts. api_info returns values as strings, so asserts compare against strings (`'30'`, `'100'`, `'1'`).
- **No password substring:** no test datum contains `molecule`.
- **Idempotence:** every scenario includes the `idempotence` step; api_modify is idempotent, and the converge prereq tasks use `handle_absent_entries: ignore` so they don't thrash.
- **interface_ethernet mtu note:** if setting `mtu: 1400` reports unsupported on the CHR virtio NIC, fall back to asserting only `comment` (drop `mtu` from converge+verify).
