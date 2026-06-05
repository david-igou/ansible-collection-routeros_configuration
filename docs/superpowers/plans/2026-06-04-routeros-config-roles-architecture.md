# RouterOS Configuration Roles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared `_reconcile` engine role plus a 3-role vertical slice (`system_identity`, `ip_address`, `ip_firewall_filter`) that declaratively manage RouterOS over the binary API, each with its own molecule scenario on a CHR VM.

**Architecture:** Each subsystem role is a thin wrapper that `include_role`s an internal `_reconcile` engine, which calls `community.routeros.api_modify` for one config path. State is declared via `routeros_<path>` vars; additive by default, with per-role `_purge`/`_order` toggles. Molecule scenarios boot a fresh CHR, forward the API port (8728) over a SLIRP `hostfwd`, converge the role, check idempotence, and verify state via `api_info`.

**Tech Stack:** Ansible roles, `community.routeros` (`api_modify`/`api_info`, requires `librouteros` on the controller), molecule + the `david_igou.molecule_provisioners` qemu backend, MikroTik CHR 7.21.4.

**Reference spec:** `docs/superpowers/specs/2026-06-04-routeros-config-roles-architecture-design.md`

---

## File Structure

```
roles/
  _reconcile/                       # shared engine (internal)
    defaults/main.yml               # routeros_api_* conn vars + rcfg_* defaults
    meta/main.yml meta/argument_specs.yml
    tasks/main.yml                  # guard assert + single api_modify call
  system_identity/                  # singleton path
  ip_address/                       # simple list + purge
  ip_firewall_filter/               # ordered list + order/purge
    (each: defaults/ meta/ tasks/ README.md)
extensions/molecule/
  utils/
    inventory/hosts.yml             # shared CHR host def + API hostfwd netdev
    inventory/group_vars/molecule.yml  # shared routeros_api_* + chr_admin_password
    playbooks/create.yml prepare.yml destroy.yml   # shared bootstrap
  system_identity/ ip_address/ ip_firewall_filter/
    molecule.yml converge.yml verify.yml           # per-role
  chr/                              # existing spike — left untouched as reference
```

Removed: `roles/run/` (pure scaffold).

---

## Task 1: Retire the `run` scaffold role

**Files:**
- Delete: `roles/run/` (whole directory)
- Modify: `Makefile:6` (the `MOLECULE_SCENARIOS` line)

- [ ] **Step 1: Delete the scaffold role**

Run:
```bash
git rm -r roles/run
```

- [ ] **Step 2: Update the informational scenario list in the Makefile**

In `Makefile`, change line 6 from:
```make
MOLECULE_SCENARIOS := chr
```
to:
```make
MOLECULE_SCENARIOS := system_identity ip_address ip_firewall_filter
```

- [ ] **Step 3: Verify the collection still builds (structure is valid)**

Run: `ansible-galaxy collection build --force`
Expected: builds a `david_igou-routeros_configuration-*.tar.gz` with no error. Then `rm -f david_igou-routeros_configuration-*.tar.gz`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: retire placeholder run role"
```

---

## Task 2: Add the `librouteros` controller requirement

`community.routeros`'s API modules (`api_modify`/`api_info`) require the `librouteros` Python library on the Ansible controller. Molecule runs these from the controller, so it must be installed for tests and documented for consumers.

**Files:**
- Modify: `test-requirements.txt`
- Modify: `README.md` (add a requirements note)

- [ ] **Step 1: Add librouteros to test requirements**

Append this line to `test-requirements.txt`:
```
librouteros>=3.0.0
```

- [ ] **Step 2: Install it into the current environment**

Run: `pip install 'librouteros>=3.0.0'`
Expected: installs successfully (used by the API modules at test time).

- [ ] **Step 3: Document the controller requirement in the README**

In `README.md`, add a short "Requirements" note stating: these roles manage RouterOS over the binary API via `community.routeros.api_modify`, which requires the `librouteros` Python library on the Ansible controller (`pip install librouteros`), and that the device must have the `api` (8728) or `api-ssl` (8729) service enabled.

- [ ] **Step 4: Commit**

```bash
git add test-requirements.txt README.md
git commit -m "docs: require librouteros on the controller for the API modules"
```

---

## Task 3: Create the `_reconcile` engine role

The one piece of real logic. A guard assert (ensure_order implies purge) plus a single `api_modify` call wired to the shared `routeros_api_*` connection vars and the private `rcfg_*` inputs.

**Files:**
- Create: `roles/_reconcile/defaults/main.yml`
- Create: `roles/_reconcile/meta/main.yml`
- Create: `roles/_reconcile/meta/argument_specs.yml`
- Create: `roles/_reconcile/tasks/main.yml`
- Create: `roles/_reconcile/README.md`

- [ ] **Step 1: Write `roles/_reconcile/defaults/main.yml`**

```yaml
---
# Shared connection to the RouterOS binary API. Override per host/group.
# In production prefer TLS (api-ssl, port 8729) with validate_certs: true.
routeros_api_hostname: "{{ inventory_hostname }}"
routeros_api_username: admin
routeros_api_password: ""
routeros_api_tls: true
routeros_api_validate_certs: true
# Leave empty to let the module pick the port from `tls` (8728/8729).
routeros_api_port: ""

# Private engine inputs — set by the calling subsystem role, not the user.
# rcfg_path and rcfg_data have no default: callers MUST supply them.
rcfg_purge: false            # true -> handle_absent_entries: remove (exact-state)
rcfg_order: false            # true -> ensure_order: true (requires rcfg_purge)
rcfg_content: ignore         # handle_entries_content: ignore|remove|remove_as_much_as_possible
```

- [ ] **Step 2: Write `roles/_reconcile/meta/main.yml`**

```yaml
---
galaxy_info:
  author: David Igou
  description: Internal engine — reconciles one RouterOS path via api_modify.
  company: david_igou
  license: GPL-2.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - networking
dependencies: []
```

- [ ] **Step 3: Write `roles/_reconcile/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Reconcile one RouterOS config path declaratively via the API.
    description:
      - Internal engine role. Subsystem roles include it with rcfg_* set.
    options:
      rcfg_path:
        type: str
        required: true
        description: Space-separated RouterOS path, e.g. "ip firewall filter".
      rcfg_data:
        type: list
        elements: dict
        required: true
        description: Desired list of entry dicts for the path.
      rcfg_purge:
        type: bool
        default: false
        description: Remove device entries not present in rcfg_data (exact-state).
      rcfg_order:
        type: bool
        default: false
        description: Enforce entry order. Requires rcfg_purge.
      rcfg_content:
        type: str
        default: ignore
        choices:
          - ignore
          - remove
          - remove_as_much_as_possible
        description: How to treat entry fields not present in rcfg_data.
      routeros_api_hostname:
        type: str
        description: API hostname/IP of the device.
      routeros_api_username:
        type: str
      routeros_api_password:
        type: str
      routeros_api_tls:
        type: bool
      routeros_api_validate_certs:
        type: bool
      routeros_api_port:
        type: raw
        description: TCP port; empty lets the module choose from tls.
```

- [ ] **Step 4: Write `roles/_reconcile/tasks/main.yml`**

```yaml
---
# tasks file for david_igou.routeros_configuration._reconcile

- name: "Assert ensure_order implies purge for '{{ rcfg_path }}'"
  ansible.builtin.assert:
    that:
      - not (rcfg_order | bool) or (rcfg_purge | bool)
    fail_msg: >-
      rcfg_order requires rcfg_purge: api_modify's ensure_order needs
      handle_absent_entries=remove (path '{{ rcfg_path }}').
    quiet: true

- name: "Reconcile RouterOS path '{{ rcfg_path }}'"
  community.routeros.api_modify:
    hostname: "{{ routeros_api_hostname }}"
    username: "{{ routeros_api_username }}"
    password: "{{ routeros_api_password }}"
    tls: "{{ routeros_api_tls | bool }}"
    validate_certs: "{{ routeros_api_validate_certs | bool }}"
    port: "{{ routeros_api_port | default(omit, true) }}"
    path: "{{ rcfg_path }}"
    data: "{{ rcfg_data }}"
    handle_absent_entries: "{{ 'remove' if (rcfg_purge | bool) else 'ignore' }}"
    handle_entries_content: "{{ rcfg_content }}"
    ensure_order: "{{ rcfg_order | bool }}"
  delegate_to: localhost
  connection: local
```

- [ ] **Step 5: Write `roles/_reconcile/README.md`**

```markdown
# _reconcile (internal engine)

Reconciles one RouterOS config path declaratively via
`community.routeros.api_modify`. Not a user entrypoint — subsystem roles
include it:

    - ansible.builtin.include_role:
        name: _reconcile
      vars:
        rcfg_path: ip address
        rcfg_data: "{{ routeros_ip_address }}"
        rcfg_purge: "{{ routeros_ip_address_purge }}"

Connection comes from the shared `routeros_api_*` vars (see defaults).
`rcfg_order: true` requires `rcfg_purge: true`.
```

- [ ] **Step 6: Validate role metadata parses**

Run: `ansible-galaxy collection build --force && rm -f david_igou-routeros_configuration-*.tar.gz`
Expected: build succeeds (argument_specs/meta are syntactically valid).

- [ ] **Step 7: Commit**

```bash
git add roles/_reconcile
git commit -m "feat(_reconcile): shared api_modify reconciliation engine role"
```

---

## Task 4: Shared molecule bootstrap (utils)

Factor the CHR boot + API-port enablement used by every scenario into one place. This is also where the API-connectivity mechanic (the one unproven detail) lives.

**Files:**
- Create: `extensions/molecule/utils/inventory/hosts.yml`
- Create: `extensions/molecule/utils/inventory/group_vars/molecule.yml`
- Create: `extensions/molecule/utils/playbooks/create.yml`
- Create: `extensions/molecule/utils/playbooks/prepare.yml`
- Create: `extensions/molecule/utils/playbooks/destroy.yml`

> Note: `extensions/molecule/utils/playbooks/` already contains `converge.yml`/`noop.yml` and `extensions/molecule/utils/vars/`. Add the new files alongside; do not remove existing ones.

- [ ] **Step 1: Write `extensions/molecule/utils/inventory/hosts.yml`**

```yaml
---
# Shared CHR host for the api_modify role scenarios. net0 (ether1) is the
# provisioner's SSH/DHCP NIC. We add ONE extra SLIRP netdev "apinet" (ether2)
# that forwards host TCP 8728 -> guest 8728 (the RouterOS binary API). prepare
# enables a dhcp-client on ether2 so the guest holds 10.0.2.15 for the forward
# to land on, and enables the api service.
all:
  children:
    molecule:
      hosts:
        chr-1:
          mp:
            qemu:
              image: "https://download.mikrotik.com/routeros/7.21.4/chr-7.21.4.img.zip"
              ssh_user: admin
              cpus: 1
              memory: 512
              extra_args:
                - -netdev
                - "user,id=apinet,hostfwd=tcp::8728-:8728"
                - -device
                - "virtio-net-pci,netdev=apinet,mac=52:54:00:00:01:02"
```

- [ ] **Step 2: Write `extensions/molecule/utils/inventory/group_vars/molecule.yml`**

```yaml
---
# Throwaway admin password bootstrapped onto the fresh CHR by prepare.yml.
chr_admin_password: molecule

# The RouterOS binary API is reached from the CONTROLLER (api_modify runs with
# connection: local), via the SLIRP hostfwd on 127.0.0.1:8728 — NOT the device's
# own name. So override routeros_api_hostname/port here. Plaintext API (tls
# false, 8728) is fine for the ephemeral test VM; production should use TLS/8729.
routeros_api_hostname: "127.0.0.1"
routeros_api_port: 8728
routeros_api_username: admin
routeros_api_password: "{{ chr_admin_password }}"
routeros_api_tls: false
routeros_api_validate_certs: false
```

- [ ] **Step 3: Write `extensions/molecule/utils/playbooks/create.yml`**

```yaml
---
- name: Provision molecule instances
  import_playbook: david_igou.molecule_provisioners.create
```

- [ ] **Step 4: Write `extensions/molecule/utils/playbooks/destroy.yml`**

```yaml
---
- name: Destroy molecule instances
  import_playbook: david_igou.molecule_provisioners.destroy
```

- [ ] **Step 5: Write `extensions/molecule/utils/playbooks/prepare.yml`**

```yaml
---
# Bootstrap the fresh CHR so the binary API is reachable from the controller:
#   1. TCP-wait on the forwarded SSH port (CHR has no POSIX shell).
#   2. Set a known admin password over the empty-password login.
#   3. Over SSH (now authenticated), enable the api service and a dhcp-client on
#      ether2 (the apinet hostfwd NIC) so 127.0.0.1:8728 reaches a live address.
#   4. TCP-wait on the forwarded API port so converge doesn't race the boot.
- name: Prepare CHR for binary-API configuration
  hosts: molecule
  gather_facts: false
  vars:
    ansible_connection: local
  tasks:
    - name: Wait for forwarded SSH port (TCP only — CHR has no POSIX shell)
      ansible.builtin.wait_for:
        host: "{{ ansible_host | default('127.0.0.1') }}"
        port: "{{ ansible_port | default(2222) }}"
        timeout: 180
        delay: 5
        sleep: 3

    - name: Bootstrap a known admin password over the empty-password login
      ansible.builtin.command:
        argv:
          - sshpass
          - -p
          - ""
          - ssh
          - -p
          - "{{ ansible_port | default(2222) }}"
          - -o
          - StrictHostKeyChecking=no
          - -o
          - UserKnownHostsFile=/dev/null
          - -o
          - PreferredAuthentications=password
          - -o
          - PubkeyAuthentication=no
          - -o
          - ConnectTimeout=15
          - "admin@{{ ansible_host | default('127.0.0.1') }}"
          - "/user set [find name=admin] password={{ chr_admin_password }}"
      delegate_to: localhost
      register: chr_pw
      changed_when: chr_pw.rc == 0
      failed_when: false

    - name: Enable the api service and a dhcp-client on the apinet NIC (ether2)
      ansible.builtin.command:
        argv:
          - sshpass
          - -p
          - "{{ chr_admin_password }}"
          - ssh
          - -p
          - "{{ ansible_port | default(2222) }}"
          - -o
          - StrictHostKeyChecking=no
          - -o
          - UserKnownHostsFile=/dev/null
          - -o
          - PreferredAuthentications=password
          - -o
          - PubkeyAuthentication=no
          - -o
          - ConnectTimeout=15
          - "admin+cet1024w@{{ ansible_host | default('127.0.0.1') }}"
          - "{{ item }}"
      loop:
        - "/ip service set api disabled=no"
        - "/ip dhcp-client add interface=ether2 disabled=no"
      delegate_to: localhost
      register: chr_api
      changed_when: chr_api.rc == 0
      failed_when: false

    - name: Wait for the forwarded API port (8728) to accept connections
      ansible.builtin.wait_for:
        host: "127.0.0.1"
        port: 8728
        timeout: 120
        delay: 5
        sleep: 3
      delegate_to: localhost
```

- [ ] **Step 6: Commit**

```bash
git add extensions/molecule/utils/inventory extensions/molecule/utils/playbooks/create.yml extensions/molecule/utils/playbooks/prepare.yml extensions/molecule/utils/playbooks/destroy.yml
git commit -m "test(molecule): shared CHR bootstrap with binary-API port forwarding"
```

---

## Task 5: `system_identity` role + scenario (proves singleton + API connectivity)

This is the first end-to-end proof: it validates the whole API-forwarding mechanic from Task 4. If the `hostfwd`/`dhcp-client` approach is flaky, this is where it surfaces.

**Files:**
- Create: `roles/system_identity/defaults/main.yml`
- Create: `roles/system_identity/meta/main.yml`
- Create: `roles/system_identity/meta/argument_specs.yml`
- Create: `roles/system_identity/tasks/main.yml`
- Create: `roles/system_identity/README.md`
- Create: `extensions/molecule/system_identity/molecule.yml`
- Create: `extensions/molecule/system_identity/converge.yml`
- Create: `extensions/molecule/system_identity/verify.yml`

- [ ] **Step 1: Write the role `defaults/main.yml`**

```yaml
---
# /system/identity is a singleton path. Provide a single-element list with the
# desired name, e.g. [{name: "core-router"}]. Empty -> no change.
routeros_system_identity: []
```

- [ ] **Step 2: Write `roles/system_identity/meta/main.yml`**

```yaml
---
galaxy_info:
  author: David Igou
  description: Declaratively manage /system/identity (device name).
  company: david_igou
  license: GPL-2.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - networking
dependencies: []
```

- [ ] **Step 3: Write `roles/system_identity/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /system/identity declaratively.
    options:
      routeros_system_identity:
        type: list
        elements: dict
        default: []
        description: Single-element list with the device name, e.g. [{name: core}].
```

- [ ] **Step 4: Write `roles/system_identity/tasks/main.yml`**

```yaml
---
# tasks file for david_igou.routeros_configuration.system_identity
- name: Reconcile /system/identity
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: system identity
    rcfg_data: "{{ routeros_system_identity }}"
    rcfg_purge: false
    rcfg_order: false
```

- [ ] **Step 5: Write `roles/system_identity/README.md`**

```markdown
# system_identity

Declaratively manage `/system/identity` (device name) over the RouterOS API.

    routeros_system_identity:
      - name: core-router

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
```

- [ ] **Step 6: Write `extensions/molecule/system_identity/molecule.yml`**

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
  name: system_identity
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

- [ ] **Step 7: Write `extensions/molecule/system_identity/converge.yml`**

```yaml
---
- name: Converge — apply system_identity
  hosts: molecule
  gather_facts: false
  vars:
    routeros_system_identity:
      - name: molecule-chr
  roles:
    - role: david_igou.routeros_configuration.system_identity
```

- [ ] **Step 8: Write `extensions/molecule/system_identity/verify.yml`**

```yaml
---
- name: Verify — /system/identity reflects declared name
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /system/identity over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: system identity
      delegate_to: localhost
      connection: local
      register: ident

    - name: Assert the identity name was applied
      ansible.builtin.assert:
        that:
          - ident.result | selectattr('name', 'equalto', 'molecule-chr') | list | length == 1
        success_msg: "identity = molecule-chr"
        fail_msg: "unexpected identity: {{ ident.result }}"
```

- [ ] **Step 9: Run the scenario (red→green for the whole API path)**

Run: `make molecule SCENARIO=system_identity`
Expected: CHR boots, `prepare` opens 8728, `converge` applies the name, `idempotence` reports no changes on the second converge, `verify` asserts the name, `destroy` tears down. Whole run PASSES.

If `verify`/`converge` cannot reach the API (timeouts on 8728): apply the spec's fallback — in `extensions/molecule/utils/playbooks/prepare.yml` replace the `hostfwd`/`dhcp-client` approach with an `sshpass` SSH local-forward tunnel (`ssh -L 8728:127.0.0.1:8728 ... -N &`) and re-run. Keep the change in `utils` so all scenarios inherit it.

- [ ] **Step 10: Commit**

```bash
git add roles/system_identity extensions/molecule/system_identity
git commit -m "feat(system_identity): declarative /system/identity role + molecule scenario"
```

---

## Task 6: `ip_address` role + scenario (proves simple list + purge)

**Files:**
- Create: `roles/ip_address/defaults/main.yml`
- Create: `roles/ip_address/meta/main.yml`
- Create: `roles/ip_address/meta/argument_specs.yml`
- Create: `roles/ip_address/tasks/main.yml`
- Create: `roles/ip_address/README.md`
- Create: `extensions/molecule/ip_address/molecule.yml`
- Create: `extensions/molecule/ip_address/converge.yml`
- Create: `extensions/molecule/ip_address/verify.yml`

- [ ] **Step 1: Write `roles/ip_address/defaults/main.yml`**

```yaml
---
# List of /ip/address entries, e.g.:
#   - address: "192.168.88.1/24"
#     interface: "ether1"
routeros_ip_address: []
# Set true to delete device addresses not present above (exact-state).
routeros_ip_address_purge: false
```

- [ ] **Step 2: Write `roles/ip_address/meta/main.yml`**

```yaml
---
galaxy_info:
  author: David Igou
  description: Declaratively manage /ip/address entries.
  company: david_igou
  license: GPL-2.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - networking
dependencies: []
```

- [ ] **Step 3: Write `roles/ip_address/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/address declaratively.
    options:
      routeros_ip_address:
        type: list
        elements: dict
        default: []
        description: IPv4 address entries (address, interface, ...).
      routeros_ip_address_purge:
        type: bool
        default: false
        description: Remove addresses not present in routeros_ip_address.
```

- [ ] **Step 4: Write `roles/ip_address/tasks/main.yml`**

```yaml
---
# tasks file for david_igou.routeros_configuration.ip_address
- name: Reconcile /ip/address
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: ip address
    rcfg_data: "{{ routeros_ip_address }}"
    rcfg_purge: "{{ routeros_ip_address_purge }}"
    rcfg_order: false
```

- [ ] **Step 5: Write `roles/ip_address/README.md`**

```markdown
# ip_address

Declaratively manage `/ip/address` over the RouterOS API.

    routeros_ip_address:
      - address: "192.168.88.1/24"
        interface: "ether1"
      - address: "10.0.0.1/24"
        interface: "ether2"
    routeros_ip_address_purge: true   # optional: exact-state

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
```

- [ ] **Step 6: Write `extensions/molecule/ip_address/molecule.yml`**

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
  name: ip_address
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

- [ ] **Step 7: Write `extensions/molecule/ip_address/converge.yml`**

Apply two addresses on ether3/ether4 (ether1=SSH, ether2=API are in use by the harness; avoid them).

```yaml
---
- name: Converge — apply ip_address
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_address:
      - address: "192.168.50.1/24"
        interface: "ether3"
      - address: "192.168.51.1/24"
        interface: "ether4"
  roles:
    - role: david_igou.routeros_configuration.ip_address
```

> Note: the shared `utils/inventory/hosts.yml` only defines ether1 (SSH) and ether2 (API). ether3/ether4 do not exist on this CHR, and `api_modify` requires a valid interface. **Before Step 9, add two more SLIRP NICs** so ether3/ether4 exist — see Step 8.

- [ ] **Step 8: Add ether3/ether4 to the shared host (needed by this scenario)**

In `extensions/molecule/utils/inventory/hosts.yml`, extend the `extra_args` list (after the `apinet` device) with two more plain NICs:

```yaml
                - -netdev
                - "user,id=net2"
                - -device
                - "virtio-net-pci,netdev=net2,mac=52:54:00:00:01:03"
                - -netdev
                - "user,id=net3"
                - -device
                - "virtio-net-pci,netdev=net3,mac=52:54:00:00:01:04"
```

These become ether3 and ether4 (apinet is ether2). No host L2 reachability is needed — the ports just need to exist for addresses to bind.

- [ ] **Step 9: Write `extensions/molecule/ip_address/verify.yml`**

Verifies additive apply, then exercises purge by re-running the role with a reduced list and `purge: true`, asserting the dropped address is gone.

```yaml
---
- name: Verify — ip_address apply + purge semantics
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/address after additive converge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip address
      delegate_to: localhost
      connection: local
      register: addr_before

    - name: Assert both declared addresses are present
      ansible.builtin.assert:
        that:
          - addr_before.result | selectattr('address', 'equalto', '192.168.50.1/24') | list | length == 1
          - addr_before.result | selectattr('address', 'equalto', '192.168.51.1/24') | list | length == 1

    - name: Re-apply with a reduced list and purge enabled
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ip_address
      vars:
        routeros_ip_address:
          - address: "192.168.50.1/24"
            interface: "ether3"
        routeros_ip_address_purge: true

    - name: Read /ip/address after purge
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip address
      delegate_to: localhost
      connection: local
      register: addr_after

    - name: Assert the dropped address was purged and the kept one remains
      ansible.builtin.assert:
        that:
          - addr_after.result | selectattr('address', 'equalto', '192.168.50.1/24') | list | length == 1
          - addr_after.result | selectattr('address', 'equalto', '192.168.51.1/24') | list | length == 0
        success_msg: "purge removed 192.168.51.1/24, kept 192.168.50.1/24"
        fail_msg: "purge did not behave as expected: {{ addr_after.result }}"
```

- [ ] **Step 10: Run the scenario**

Run: `make molecule SCENARIO=ip_address`
Expected: PASSES — converge applies both addresses, idempotence is clean, verify confirms additive then purge behavior.

- [ ] **Step 11: Commit**

```bash
git add roles/ip_address extensions/molecule/ip_address extensions/molecule/utils/inventory/hosts.yml
git commit -m "feat(ip_address): declarative /ip/address role + molecule scenario (purge)"
```

---

## Task 7: `ip_firewall_filter` role + scenario (proves ordered list)

**Files:**
- Create: `roles/ip_firewall_filter/defaults/main.yml`
- Create: `roles/ip_firewall_filter/meta/main.yml`
- Create: `roles/ip_firewall_filter/meta/argument_specs.yml`
- Create: `roles/ip_firewall_filter/tasks/main.yml`
- Create: `roles/ip_firewall_filter/README.md`
- Create: `extensions/molecule/ip_firewall_filter/molecule.yml`
- Create: `extensions/molecule/ip_firewall_filter/converge.yml`
- Create: `extensions/molecule/ip_firewall_filter/verify.yml`

- [ ] **Step 1: Write `roles/ip_firewall_filter/defaults/main.yml`**

```yaml
---
# Ordered list of /ip/firewall/filter rules. Order matters; set _order: true
# (which also requires _purge: true) to enforce it exactly.
routeros_ip_firewall_filter: []
routeros_ip_firewall_filter_purge: false
routeros_ip_firewall_filter_order: false
```

- [ ] **Step 2: Write `roles/ip_firewall_filter/meta/main.yml`**

```yaml
---
galaxy_info:
  author: David Igou
  description: Declaratively manage /ip/firewall/filter rules (ordered).
  company: david_igou
  license: GPL-2.0-or-later
  min_ansible_version: "2.15"
  galaxy_tags:
    - routeros
    - mikrotik
    - firewall
dependencies: []
```

- [ ] **Step 3: Write `roles/ip_firewall_filter/meta/argument_specs.yml`**

```yaml
---
argument_specs:
  main:
    short_description: Manage /ip/firewall/filter declaratively (ordered).
    options:
      routeros_ip_firewall_filter:
        type: list
        elements: dict
        default: []
        description: Ordered firewall filter rules (chain, action, ...).
      routeros_ip_firewall_filter_purge:
        type: bool
        default: false
        description: Remove rules not present in the list.
      routeros_ip_firewall_filter_order:
        type: bool
        default: false
        description: Enforce rule order. Requires _purge true.
```

- [ ] **Step 4: Write `roles/ip_firewall_filter/tasks/main.yml`**

```yaml
---
# tasks file for david_igou.routeros_configuration.ip_firewall_filter
- name: Reconcile /ip/firewall/filter
  ansible.builtin.include_role:
    name: _reconcile
  vars:
    rcfg_path: ip firewall filter
    rcfg_data: "{{ routeros_ip_firewall_filter }}"
    rcfg_purge: "{{ routeros_ip_firewall_filter_purge }}"
    rcfg_order: "{{ routeros_ip_firewall_filter_order }}"
```

- [ ] **Step 5: Write `roles/ip_firewall_filter/README.md`**

```markdown
# ip_firewall_filter

Declaratively manage `/ip/firewall/filter` over the RouterOS API. Rules are
ordered; enable `_order` (which requires `_purge`) for exact ordered state.

    routeros_ip_firewall_filter:
      - chain: input
        action: accept
        connection-state: "established,related"
      - chain: input
        action: accept
        protocol: icmp
      - chain: input
        action: drop
        comment: "drop the rest"
    routeros_ip_firewall_filter_purge: true
    routeros_ip_firewall_filter_order: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
**Caution:** enabling `_purge` on an incomplete list can lock you out.
```

- [ ] **Step 6: Write `extensions/molecule/ip_firewall_filter/molecule.yml`**

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
  name: ip_firewall_filter
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

- [ ] **Step 7: Write `extensions/molecule/ip_firewall_filter/converge.yml`**

```yaml
---
- name: Converge — apply ordered firewall filter rules
  hosts: molecule
  gather_facts: false
  vars:
    routeros_ip_firewall_filter:
      - chain: input
        action: accept
        connection-state: "established,related"
        comment: "rule-a"
      - chain: input
        action: accept
        protocol: icmp
        comment: "rule-b"
      - chain: input
        action: drop
        comment: "rule-c"
    routeros_ip_firewall_filter_purge: true
    routeros_ip_firewall_filter_order: true
  roles:
    - role: david_igou.routeros_configuration.ip_firewall_filter
```

- [ ] **Step 8: Write `extensions/molecule/ip_firewall_filter/verify.yml`**

```yaml
---
- name: Verify — firewall filter rules present and in declared order
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Read /ip/firewall/filter over the API
      community.routeros.api_info:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: ip firewall filter
      delegate_to: localhost
      connection: local
      register: fw

    - name: Collect the comments in device order
      ansible.builtin.set_fact:
        fw_comments: "{{ fw.result | map(attribute='comment') | list }}"

    - name: Assert all three rules exist in the declared order
      ansible.builtin.assert:
        that:
          - "'rule-a' in fw_comments"
          - "'rule-b' in fw_comments"
          - "'rule-c' in fw_comments"
          - fw_comments.index('rule-a') < fw_comments.index('rule-b')
          - fw_comments.index('rule-b') < fw_comments.index('rule-c')
        success_msg: "rules present in order a<b<c: {{ fw_comments }}"
        fail_msg: "unexpected firewall order/content: {{ fw_comments }}"
```

- [ ] **Step 9: Run the scenario**

Run: `make molecule SCENARIO=ip_firewall_filter`
Expected: PASSES — converge applies the three ordered rules, idempotence is clean, verify confirms presence and order a<b<c.

- [ ] **Step 10: Commit**

```bash
git add roles/ip_firewall_filter extensions/molecule/ip_firewall_filter
git commit -m "feat(ip_firewall_filter): declarative ordered firewall role + molecule scenario"
```

---

## Task 8: Documentation + changelog

**Files:**
- Modify: `extensions/molecule/README.md` (scenarios table)
- Modify: `README.md` (roles list)
- Create: `changelogs/fragments/routeros-config-roles.yml`

- [ ] **Step 1: Update the molecule scenarios table**

In `extensions/molecule/README.md`, add rows to the `## Scenarios` table for `system_identity`, `ip_address`, and `ip_firewall_filter`, each describing what it proves (singleton apply; list apply + purge; ordered apply). Keep the existing `chr` row.

- [ ] **Step 2: Document the roles in the top-level README**

In `README.md`, add a "Roles" section listing `system_identity`, `ip_address`, `ip_firewall_filter` (one line each) and noting the internal `_reconcile` engine and the shared `routeros_api_*` connection variables.

- [ ] **Step 3: Write the changelog fragment**

`changelogs/fragments/routeros-config-roles.yml`:
```yaml
---
minor_changes:
  - >-
    Add the internal ``_reconcile`` engine role and the first declarative
    subsystem roles ``system_identity``, ``ip_address``, and
    ``ip_firewall_filter``, each managing one RouterOS path via
    ``community.routeros.api_modify`` with a per-role molecule scenario.
```

- [ ] **Step 4: Commit**

```bash
git add README.md extensions/molecule/README.md changelogs/fragments/routeros-config-roles.yml
git commit -m "docs: document the first subsystem roles and their molecule scenarios"
```

---

## Task 9: Full-suite verification

- [ ] **Step 1: Run all scenarios end-to-end**

Run: `make molecule` (runs `--all --continue-on-failure`)
Expected: `system_identity`, `ip_address`, and `ip_firewall_filter` all PASS. (`chr` also runs; it remains green.)

- [ ] **Step 2: Confirm a clean tree and review the log**

Run: `git status` and skim the molecule `--report` output.
Expected: working tree clean, every scenario reported as passed. If any scenario failed, debug with `superpowers:systematic-debugging` before claiming completion.

---

## Self-Review notes (for the implementer)

- **Spec coverage:** engine role (Task 3) ✓; additive-default + purge toggle (Tasks 3/6) ✓; ordered path (Task 7) ✓; one scenario per role (Tasks 5–7) ✓; API-port forwarding bootstrap (Task 4) ✓; naming = full path (`ip_firewall_filter`) ✓; retire `run` (Task 1) ✓; librouteros requirement (Task 2) ✓.
- **Interface count:** the shared host grows from 1→2 NICs in Task 4 (ether1 SSH, ether2 API), then 2→4 in Task 6 Step 8 (ether3/ether4 for addresses). The firewall scenario needs no extra NICs.
- **ensure_order guard:** the firewall converge sets both `_purge` and `_order` true, satisfying the engine's assert; `ip_address`/`system_identity` leave `_order` false.
```
