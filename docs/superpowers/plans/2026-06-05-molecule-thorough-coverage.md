# Thorough RouterOS-Meaningful Molecule Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the molecule suite thoroughly and meaningfully test all 13 roles — adding check-mode coverage, negative/failure-path tests, the missing read-back assertions, untested role branches, `/ip/route` + NTP realism, and a dedicated throwaway-CHR `lifecycle` scenario for the destructive backup→restore→reset chain — plus a README explaining the architecture.

**Architecture:** Two tiers. **Tier 1** hardens the existing scenarios on the shared CHR (`shared_state: true`, owned by the `default` scenario), so extra scenarios are nearly free (no new VM boots). **Tier 2** adds one dedicated opt-out `lifecycle` scenario that boots its own throwaway CHR (reusing the `utils/` create/prepare/destroy + apinet inventory) to exercise the genuinely destructive paths that would sever the shared device's management plane.

**Tech Stack:** molecule 26.x (`ansible.executor.args` schema, `verifier: ansible`, `shared_state`), `community.routeros` (`api_modify`/`api_info`/`api`/`command`), a real MikroTik CHR 7.21.4 over qemu (`david_igou.molecule_provisioners`), libssh network_cli.

## Conventions used throughout (read once)

- **Read-back helpers:** `community.routeros.api_info` returns `.result` (list of dicts); `community.routeros.api` returns `.msg`. Both run `delegate_to: localhost` + `connection: local` and reach the shared CHR at `127.0.0.1:8728`.
- **Connection vars** come from `utils/inventory/group_vars/molecule.yml` (`routeros_api_hostname=127.0.0.1`, `routeros_api_port=8728`, `routeros_api_username=admin`, `routeros_api_password=molecule`, `routeros_api_tls=false`). Verifies set them via `module_defaults` (see existing `configure_lists/verify.yml`).
- **network_cli** (for `/export`, `/file`, `/import`, `/system backup`) is reached at `127.0.0.1:2223` as `admin+cet1024w` (see `backup/converge.yml` play vars).
- **Run a single scenario (shared tier):** under `shared_state` the role scenarios have **no `create` step** — only `default` boots the CHR — so a lone scenario has no instance to converge against. The always-correct validation command pairs the scenario with `default` (which creates + prepares + destroys the CHR around it):

  ```bash
  MOLECULE_GLOB="extensions/molecule/*/molecule.yml" molecule test -s default -s <name>
  ```

  Task 0 teaches the Makefile to do this automatically, so after Task 0 you can use `make molecule SCENARIO=<name>` for shared scenarios too. The self-owning dedicated scenarios (`chr`, `lifecycle`) run standalone: `make molecule SCENARIO=chr`. The very first molecule run of a session downloads the CHR image (slow, once).
- **Validation rule for every task:** the molecule run must end green (`make molecule SCENARIO=<name>` exits 0). For negative scenarios "green" means the asserts-on-failure passed.
- **Commit after each task.** Branch is `test/molecule-thorough-coverage` (already created).

---

## Task 0: Makefile — single-scenario support, scenario wiring, stale-ref fixes (do first)

Make `make molecule SCENARIO=<name>` correct for shared scenarios (prepend `default`), wire the three new scenarios into the full shared pass, and remove stale references. Doing this first means every later task's `make molecule SCENARIO=<name>` validation works. Referencing not-yet-created scenarios in the shared-pass list is harmless — that list only runs in Task 12.

**Files:**
- Modify: `Makefile`
- Modify: `README.md` (root — its "Scenarios" text references phantom scenarios)

- [ ] **Step 1: Teach the `SCENARIO=` path to prepend `default` for shared scenarios.** Replace the `else` branch of the `molecule:` target's `ifeq ($(SCENARIO),)` with a self-owning check:

```make
# Scenarios that own their own CHR lifecycle (create/prepare/destroy in their
# test_sequence) run standalone; every other (shared-state) scenario needs the
# `default` scenario to boot the CHR, so prepend it.
SELF_OWNING := chr lifecycle default integration_hello_world

# ... inside the molecule target:
ifeq ($(SCENARIO),)
	molecule test -s default -s ping -s fetch -s configure_lists -s configure_singletons \
		-s configure_ordered -s configure_modify_only \
		-s configure_dependency_chain -s configure_full -s configure_check_mode \
		-s certificate -s upgrade -s export_vars \
		-s command -s user_password -s reset \
		-s backup -s restore -s reboot -s negative
	molecule test -s chr
	molecule test -s lifecycle
else ifeq ($(filter $(SCENARIO),$(SELF_OWNING)),$(SCENARIO))
	molecule test -s $(SCENARIO)
else
	molecule test -s default -s $(SCENARIO)
endif
```

(Prepending `default` is safe even if a future molecule version auto-creates the shared instance — `default`'s create is idempotent and its converge is a no-op.)

- [ ] **Step 2: Drop the stale `MOLECULE_SCENARIOS` variable.** It lists `system_identity ip_address ip_firewall_filter`, none of which exist, and nothing references it. Confirm and delete:

Run: `grep -n MOLECULE_SCENARIOS Makefile` (only the definition should match) → remove that line.

- [ ] **Step 3: Fix the root `README.md` stale scenario references.** Replace any mention of `ip_dns` / `system_identity` / `ip_address` / `ip_firewall_filter` with the real set, or point readers to `extensions/molecule/README.md` as the source of truth.

Run: `grep -nE 'ip_dns|system_identity|ip_address|ip_firewall_filter' README.md` and fix each hit.

- [ ] **Step 4: Dry-run the Makefile logic** (no boot):

Run: `make -n molecule SCENARIO=configure_singletons`
Expected: prints `... molecule test -s default -s configure_singletons`.
Run: `make -n molecule SCENARIO=chr`
Expected: prints `... molecule test -s chr` (no `default`).

- [ ] **Step 5: Commit**

```bash
git add Makefile README.md
git commit -m "build(molecule): single-scenario runs prepend default; wire new scenarios; drop stale refs"
```

---

## Task 1: configure_singletons — assert the unasserted singleton fields

Today `converge.yml` applies `/ip/settings tcp-syncookies` and `/ip/dns allow-remote-requests` but `verify.yml` never reads them back.

**Files:**
- Modify: `extensions/molecule/configure_singletons/verify.yml`

- [ ] **Step 1: Add `/ip/settings` read + extend the assertions**

In `verify.yml`, after the existing "Read /ip/dns" task (before the assert), add:

```yaml
    - name: Read /ip/settings
      community.routeros.api_info:
        path: ip settings
      delegate_to: localhost
      connection: local
      register: ipsettings
```

Then replace the existing "Assert identity + dns applied" task with:

```yaml
    - name: Assert identity, dns servers, allow-remote-requests, and tcp-syncookies applied
      ansible.builtin.assert:
        that:
          - ident.result | selectattr('name', 'equalto', 'configure-chr') | list | length == 1
          - dns.result | selectattr('servers', 'search', '1.1.1.1') | list | length == 1
          - (dns.result | first)['allow-remote-requests'] | string | lower == 'false'
          - (ipsettings.result | first)['tcp-syncookies'] | string | lower == 'true'
        fail_msg: "identity={{ ident.result }} dns={{ dns.result }} ipsettings={{ ipsettings.result }}"
```

- [ ] **Step 2: Run the scenario**

Run: `make molecule SCENARIO=configure_singletons`
Expected: PASS. (If a boolean reads back as the string `"yes"`/`"no"` instead of `true`/`false`, adjust the comparison to `in ['false','no']` / `in ['true','yes']` — `api_info` normalises most booleans to `true`/`false`, but confirm against the live read in the play output.)

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/configure_singletons/verify.yml
git commit -m "test(configure_singletons): assert tcp-syncookies + allow-remote-requests read-back"
```

---

## Task 2: configure_lists — assert the `/ip/dns/static` record

`converge.yml` applies a `/ip/dns/static` record (`router.lan` → `192.168.88.1`) that `verify.yml` never checks.

**Files:**
- Modify: `extensions/molecule/configure_lists/verify.yml`

- [ ] **Step 1: Add a static-DNS read-back near the top of `tasks:`** (after the first "Read /ip/pool after converge" + its assert, before the update/purge re-apply):

```yaml
    - name: Read /ip/dns/static after converge
      community.routeros.api_info:
        path: ip dns static
      delegate_to: localhost
      connection: local
      register: dnsstatic
    - name: Assert the static DNS record was applied
      ansible.builtin.assert:
        that:
          - dnsstatic.result | selectattr('name', 'equalto', 'router.lan') | selectattr('address', 'equalto', '192.168.88.1') | list | length == 1
        fail_msg: "static dns missing: {{ dnsstatic.result }}"
```

- [ ] **Step 2: Run the scenario**

Run: `make molecule SCENARIO=configure_lists`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/configure_lists/verify.yml
git commit -m "test(configure_lists): assert /ip/dns/static record read-back"
```

---

## Task 3: export_vars — assert the `/system/identity` capture too

`converge.yml` requests capture of `/ip/address` **and** `/system/identity`; `verify.yml` only checks `/ip/address`.

**Files:**
- Modify: `extensions/molecule/export_vars/converge.yml` (seed a known identity so the capture has a value to assert)
- Modify: `extensions/molecule/export_vars/verify.yml`

- [ ] **Step 1: Seed a known identity in `converge.yml`** — add this task before the "Capture the device configuration" task:

```yaml
    - name: Ensure a known /system/identity exists
      community.routeros.api_modify:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port }}"
        path: system identity
        data:
          - name: export-vars-id
      delegate_to: localhost
      connection: local
```

- [ ] **Step 2: Assert the identity capture in `verify.yml`** — extend the existing assert's `that:` list with:

```yaml
          - "'/system/identity' in captured.routeros_config"
          - >-
            captured.routeros_config['/system/identity'].data
            | selectattr('name', 'equalto', 'export-vars-id') | list | length == 1
```

- [ ] **Step 3: Run the scenario**

Run: `make molecule SCENARIO=export_vars`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add extensions/molecule/export_vars/converge.yml extensions/molecule/export_vars/verify.yml
git commit -m "test(export_vars): seed + assert /system/identity capture (singleton shape)"
```

---

## Task 4: certificate — assert the trust chain (issuer), not just a fingerprint

Today the verify proves both certs are *signed* (non-empty fingerprint) but not that `mol-host` was signed *by* `mol-ca`.

**Files:**
- Modify: `extensions/molecule/certificate/verify.yml`

- [ ] **Step 1: Add a trust-chain assertion.** Append to the existing "Assert certs are signed…" task's `that:` list:

```yaml
          - (certs.msg | selectattr('name', 'equalto', 'mol-host') | first)['ca'] | default('') == 'mol-ca'
```

Note: RouterOS exposes the signing CA of a signed certificate in the `ca` field (the CA certificate's name). If the live read shows the issuer under a different field name (e.g. `ca` empty but `issuer` populated), switch the key accordingly based on the `certs.msg` dump in the failure output.

- [ ] **Step 2: Run the scenario**

Run: `make molecule SCENARIO=certificate`
Expected: PASS. If `ca` is empty on read-back, dump `certs.msg` (the `fail_msg` already prints names; temporarily add `- debug: var=certs.msg`) to find the correct issuer field, set it, re-run.

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/certificate/verify.yml
git commit -m "test(certificate): assert mol-host trust chain (signed by mol-ca)"
```

---

## Task 5: New `configure_check_mode` scenario — prove `--check` does not mutate

`api_modify` (the engine behind `configure`/`_reconcile`) supports check mode; nothing tests it. A check-mode task always reports `changed`, so this scenario **drops the idempotence step**.

**Files:**
- Create: `extensions/molecule/configure_check_mode/molecule.yml`
- Create: `extensions/molecule/configure_check_mode/converge.yml`
- Create: `extensions/molecule/configure_check_mode/verify.yml`

- [ ] **Step 1: Write `molecule.yml`**

```yaml
---
# Check-mode proof. A check_mode task always reports `changed`, so the idempotence
# step is dropped (it would re-run the check-mode apply and never settle).
scenario:
  name: configure_check_mode
  test_sequence:
    - dependency
    - converge
    - verify
```

- [ ] **Step 2: Write `converge.yml`** — check-mode apply must NOT mutate; then a real apply does.

```yaml
---
- name: Converge — check-mode apply must not touch the device, then a real apply does
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_modify: &conn
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
    community.routeros.api_info: *conn
  tasks:
    - name: Apply a brand-new pool IN CHECK MODE (predicts a change, writes nothing)
      community.routeros.api_modify:
        path: ip pool
        data:
          - name: checkmode-pool
            ranges: "192.168.222.10-192.168.222.50"
        handle_absent_entries: ignore
      delegate_to: localhost
      connection: local
      check_mode: true
      register: cm

    - name: Assert check mode predicted a change
      ansible.builtin.assert:
        that:
          - cm is changed
        fail_msg: "check mode did not predict a change: {{ cm }}"

    - name: Read /ip/pool — checkmode-pool must NOT exist (check mode wrote nothing)
      community.routeros.api_info:
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pools_after_check
    - name: Assert check mode did not mutate the device
      ansible.builtin.assert:
        that:
          - pools_after_check.result | selectattr('name', 'equalto', 'checkmode-pool') | list | length == 0
        fail_msg: "check mode LEAKED a write: {{ pools_after_check.result }}"

    - name: Apply the same pool FOR REAL
      community.routeros.api_modify:
        path: ip pool
        data:
          - name: checkmode-pool
            ranges: "192.168.222.10-192.168.222.50"
        handle_absent_entries: ignore
      delegate_to: localhost
      connection: local
```

- [ ] **Step 3: Write `verify.yml`** — the real apply landed.

```yaml
---
- name: Verify — the real apply created checkmode-pool
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
  tasks:
    - name: Read /ip/pool
      community.routeros.api_info:
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pools
    - name: Assert checkmode-pool exists after the real apply
      ansible.builtin.assert:
        that:
          - pools.result | selectattr('name', 'equalto', 'checkmode-pool') | map(attribute='ranges') | first == '192.168.222.10-192.168.222.50'
        success_msg: "check mode wrote nothing; real apply created checkmode-pool"
        fail_msg: "real apply missing: {{ pools.result }}"
```

- [ ] **Step 4: Run the scenario**

Run: `make molecule SCENARIO=configure_check_mode`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extensions/molecule/configure_check_mode/
git commit -m "test: add configure_check_mode scenario (--check writes nothing, real apply does)"
```

---

## Task 6: New `negative` scenario — roles fail as designed

Exercises the explicit validation/error logic in `command`, `user_password`, `_reconcile`, and `ping`. All four are safe on the shared device: each fails at validation *before* any mutation, or is read-only. Uses `block`/`rescue`; no idempotence/verify step.

**Files:**
- Create: `extensions/molecule/negative/molecule.yml`
- Create: `extensions/molecule/negative/converge.yml`

- [ ] **Step 1: Write `molecule.yml`**

```yaml
---
# Negative / failure-path scenario: assert roles FAIL as designed. All checks
# fail at validation before any device mutation (or are read-only), so they are
# safe on the shared CHR. block/rescue captures the expected failure; no
# idempotence or verify step.
scenario:
  name: negative
  test_sequence:
    - dependency
    - converge
```

- [ ] **Step 2: Write `converge.yml`**

```yaml
---
- name: Negative — roles fail as designed (validation fires before any mutation)
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api: &conn
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
  tasks:
    # 1. command: an item with TWO op keys must trip the _cmd_bad assert.
    - name: command role rejects a malformed item (two op keys)
      block:
        - name: Run command with an invalid item
          ansible.builtin.include_role:
            name: david_igou.routeros_configuration.command
          vars:
            routeros_command:
              - path: "system note"
                cmd: "set note=x"
                add: "name=y"
        - name: Should not reach here
          ansible.builtin.fail:
            msg: "command role accepted a two-op item"
      rescue:
        - name: Expected — command validation failed
          ansible.builtin.debug:
            msg: "command role correctly rejected the malformed item"

    # 2. user_password: a user that does not exist must trip the missing-user assert.
    - name: user_password role rejects an unknown user
      block:
        - name: Rotate a non-existent user's password
          ansible.builtin.include_role:
            name: david_igou.routeros_configuration.user_password
          vars:
            routeros_user_passwords:
              - name: this-user-does-not-exist
                password: irrelevant
        - name: Should not reach here
          ansible.builtin.fail:
            msg: "user_password accepted a missing user"
      rescue:
        - name: Expected — user_password validation failed
          ansible.builtin.debug:
            msg: "user_password correctly rejected the missing user"

    # 3. _reconcile/configure: order:true without purge:true must trip the assert.
    - name: configure rejects order without purge
      block:
        - name: Apply an ordered path without purge
          ansible.builtin.include_role:
            name: david_igou.routeros_configuration.configure
          vars:
            routeros_config:
              /ip/firewall/filter:
                order: true
                data:
                  - chain: input
                    action: accept
                    comment: neg-rule
        - name: Should not reach here
          ansible.builtin.fail:
            msg: "configure accepted order without purge"
      rescue:
        - name: Expected — order-without-purge assert failed
          ansible.builtin.debug:
            msg: "configure correctly rejected order:true with purge:false"

    # 4. ping: an unreachable target returns received=0 (read-only; no failure).
    - name: ping an unreachable address
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.ping
      vars:
        routeros_ping:
          - address: "192.0.2.1"   # TEST-NET-1, not globally routed
            count: 2
    - name: Assert the unreachable ping received nothing
      ansible.builtin.assert:
        that:
          - (_routeros_ping.results[0].msg | last).received | int == 0
        success_msg: "unreachable ping correctly reported 0 received"
        fail_msg: "unexpected ping result: {{ _routeros_ping.results[0].msg }}"
```

- [ ] **Step 3: Run the scenario**

Run: `make molecule SCENARIO=negative`
Expected: PASS (every rescue fired; the ping assert held).
Note: if `_routeros_ping` is not the register name the `ping` role uses, check `roles/ping/tasks/main.yml` for the actual `register:` and match it. If `192.0.2.1` unexpectedly answers via SLIRP, switch to `240.0.0.1` (reserved, guaranteed unreachable) and re-run.

- [ ] **Step 4: Commit**

```bash
git add extensions/molecule/negative/
git commit -m "test: add negative scenario (command/user_password/configure/ping failure paths)"
```

---

## Task 7: fetch — exercise the remove branch

`routeros_fetch_remove` (delete a file by name) is never tested. Extend the scenario to fetch two files and remove one, then verify one present + one gone. (Add a comment noting the idempotence step is vacuous for the `cmd`-based fetch op — `community.routeros.api` returns `changed=False` for arbitrary ops — so the real proof is the read-back here.)

**Files:**
- Modify: `extensions/molecule/fetch/converge.yml`
- Modify: `extensions/molecule/fetch/verify.yml`

- [ ] **Step 1: Replace `converge.yml`**

```yaml
---
- name: Converge — fetch two files, then remove one
  hosts: molecule
  gather_facts: false
  vars:
    # The device's own web service is always reachable from itself.
    # NOTE: /tool fetch is a `cmd` op; community.routeros.api returns
    # changed=False for cmd ops, so molecule's idempotence step is vacuous for
    # this role — the verify read-back below is the real proof.
    routeros_fetch:
      - url: "http://127.0.0.1/"
        dst_path: fetch-keep.html
        mode: http
      - url: "http://127.0.0.1/"
        dst_path: fetch-remove.html
        mode: http
    routeros_fetch_remove:
      - fetch-remove.html
  roles:
    - role: david_igou.routeros_configuration.fetch
```

- [ ] **Step 2: Replace the assert in `verify.yml`** with:

```yaml
    - name: Assert the kept file is present and the removed file is gone
      ansible.builtin.assert:
        that:
          - files.msg | selectattr('name', 'equalto', 'fetch-keep.html') | list | length == 1
          - files.msg | selectattr('name', 'equalto', 'fetch-remove.html') | list | length == 0
        success_msg: "fetch created fetch-keep.html; fetch_remove deleted fetch-remove.html"
        fail_msg: "unexpected files: {{ files.msg | map(attribute='name') | list }}"
```

- [ ] **Step 3: Run the scenario**

Run: `make molecule SCENARIO=fetch`
Expected: PASS.
Note on ordering: the `fetch` role fetches before it removes (confirm in `roles/fetch/tasks/main.yml`). If removal runs before fetch, split into two role invocations in converge (fetch first, then a second invocation with only `routeros_fetch_remove`).

- [ ] **Step 4: Commit**

```bash
git add extensions/molecule/fetch/converge.yml extensions/molecule/fetch/verify.yml
git commit -m "test(fetch): exercise the remove branch (keep one file, delete another)"
```

---

## Task 8: command — exercise the `add` and `remove` ops

The scenario only tests the `cmd` op. Add an `/ip/firewall/address-list` entry via `add` (returns real `changed=True`), then `remove` it — covering the two ops that actually mutate.

**Files:**
- Modify: `extensions/molecule/command/converge.yml`
- Modify: `extensions/molecule/command/verify.yml`
- Modify: `extensions/molecule/command/molecule.yml` (drop idempotence — an `add` op is not idempotent)

- [ ] **Step 1: Update `molecule.yml`** to drop the (now non-idempotent) idempotence step:

```yaml
---
# The cmd-op set-note is idempotent-safe (api returns changed=False for cmd), but
# this scenario also exercises add/remove ops, which are NOT idempotent — so the
# idempotence step is dropped.
scenario:
  name: command
  test_sequence:
    - dependency
    - converge
    - verify
```

- [ ] **Step 2: Append to `converge.yml`** — after the existing `set system note` item is applied, add `add` then `remove` via two more role invocations:

Replace the whole `converge.yml` with:

```yaml
---
- name: Converge — cmd (set note), then add + remove an address-list entry
  hosts: molecule
  gather_facts: false
  tasks:
    - name: cmd op — set system note
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.command
      vars:
        routeros_command:
          - path: "system note"
            cmd: "set note=cmd-role-marker"

    - name: add op — create an address-list entry
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.command
      vars:
        routeros_command:
          - path: "ip firewall address-list"
            add: "list=cmd-list address=198.51.100.7"

    - name: Read the address-list id (for the remove op)
      community.routeros.api:
        hostname: "{{ routeros_api_hostname }}"
        username: "{{ routeros_api_username }}"
        password: "{{ routeros_api_password }}"
        tls: "{{ routeros_api_tls }}"
        validate_certs: "{{ routeros_api_validate_certs }}"
        port: "{{ routeros_api_port | default(omit, true) }}"
        path: ip firewall address-list
      delegate_to: localhost
      connection: local
      register: _al

    - name: remove op — delete that address-list entry by id
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.command
      vars:
        routeros_command:
          - path: "ip firewall address-list"
            remove: "{{ (_al.msg | selectattr('list', 'equalto', 'cmd-list') | first)['.id'] }}"
```

- [ ] **Step 3: Replace `verify.yml`** to assert both the note (cmd) and that the address-list entry is gone (add+remove round-trip):

```yaml
---
- name: Verify — cmd set the note; add+remove left no address-list entry
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
  tasks:
    - name: Read system note
      community.routeros.api:
        path: "system note"
      delegate_to: localhost
      connection: local
      register: note
    - name: Read address-list
      community.routeros.api:
        path: ip firewall address-list
      delegate_to: localhost
      connection: local
      register: al
    - name: Assert cmd set the note and the add/remove round-trip cleaned up
      ansible.builtin.assert:
        that:
          - (note.msg | first).note == 'cmd-role-marker'
          - al.msg | selectattr('list', 'equalto', 'cmd-list') | list | length == 0
        success_msg: "cmd set note; add+remove round-trip left no cmd-list entry"
        fail_msg: "note={{ note.msg }} address_list={{ al.msg }}"
```

- [ ] **Step 4: Run the scenario**

Run: `make molecule SCENARIO=command`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add extensions/molecule/command/
git commit -m "test(command): exercise add + remove ops (address-list round-trip), drop idempotence"
```

---

## Task 9: configure_full — add `/ip/route` + NTP realism and broaden verify

Add the two most-common real-world objects that were absent, and widen the read-back spot-check.

**Files:**
- Modify: `extensions/molecule/configure_full/converge.yml`
- Modify: `extensions/molecule/configure_full/verify.yml`
- Modify: `extensions/molecule/configure_full/EXCLUSIONS.md` (update the exercised count + remove `system ntp client` from the not-exercised table)

- [ ] **Step 1: Add the two paths to `converge.yml`.** In the `# --- singletons / settings ---` block, add:

```yaml
      /system/ntp/client:
        data:
          - enabled: false
```

And in the `# --- interfaces / addressing ---` block (routes depend on addresses being present; a blackhole route needs no gateway/interface so ordering is not critical, but keep it after `/ip/address`), add:

```yaml
      /ip/route:
        data:
          - dst-address: "192.0.2.0/24"
            blackhole: true
            comment: full-route
```

Note: `/ip/route` is a keyless path in `api_modify` (like `/ip/firewall/nat`), matched by content. A `blackhole` route needs no gateway and stays `active`, so it reconciles idempotently. If `api_modify` rejects `blackhole: true` on this ROS version, use `type: blackhole` instead (RouterOS 7 exposes both historically; confirm against the converge error and pick the accepted one). Do NOT use a `gateway:` route — gateway routes can become inactive/dynamic and break idempotence.

- [ ] **Step 2: Broaden `verify.yml`.** Add these reads after the existing `Read /system/identity` task:

```yaml
    - name: Read /ip/firewall/nat
      community.routeros.api_info:
        path: ip firewall nat
      delegate_to: localhost
      connection: local
      register: nat
    - name: Read /ip/firewall/address-list
      community.routeros.api_info:
        path: ip firewall address-list
      delegate_to: localhost
      connection: local
      register: alist
    - name: Read /interface/bridge/vlan
      community.routeros.api_info:
        path: interface bridge vlan
      delegate_to: localhost
      connection: local
      register: brvlan
    - name: Read /ip/route
      community.routeros.api_info:
        path: ip route
      delegate_to: localhost
      connection: local
      register: routes
```

And extend the final assert's `that:` list with:

```yaml
          - nat.result | selectattr('comment', 'equalto', 'n-a') | list | length == 1
          - alist.result | selectattr('list', 'equalto', 'full-block') | list | length == 1
          - brvlan.result | selectattr('bridge', 'equalto', 'full-br') | list | length == 1
          - routes.result | selectattr('comment', 'equalto', 'full-route') | list | length == 1
```

- [ ] **Step 3: Update `EXCLUSIONS.md`.** Change the exercised count from **74** to **76** (and the configurable line accordingly: "of which **76 are exercised**"). Remove the `system ntp client` row from the "Configurable but NOT exercised" table (leave `system ntp client servers` — its keyless servers submenu is still not authored). Add a one-line note under the table that `/ip/route` is a keyless path the probe's `writable()` heuristic under-counts as read-only, but is configurable like `/ip/firewall/nat`.

- [ ] **Step 4: Run the scenario** (this is the slow one — full apply + idempotence)

Run: `make molecule SCENARIO=configure_full`
Expected: PASS, including the idempotence step (second converge = `changed=0`). If `/ip/route` breaks idempotence (a second-run change), inspect the `api_info ip route` output for a computed field that differs; if unavoidable, move the route to its own tiny non-idempotence-checked scenario and note it in EXCLUSIONS.md instead. (Blackhole routes normally reconcile cleanly.)

- [ ] **Step 5: Commit**

```bash
git add extensions/molecule/configure_full/
git commit -m "test(configure_full): add /ip/route + ntp client, broaden verify read-back"
```

---

## Task 10: New `lifecycle` scenario — destructive backup→restore→reset on a throwaway CHR

One dedicated opt-out CHR runs the full ordered lifecycle. It reuses the `utils/` create/prepare/destroy and apinet inventory inherited from `config.yml`, so only three files are new. It runs as its **own** `molecule test -s lifecycle` invocation (Task 12 wires the Makefile) — after the shared pass tears its CHR down, so `8728/2223` are free.

**Files:**
- Create: `extensions/molecule/lifecycle/molecule.yml`
- Create: `extensions/molecule/lifecycle/converge.yml`
- Create: `extensions/molecule/lifecycle/verify.yml`

- [ ] **Step 1: Write `molecule.yml`** — opt out of shared state, own the full lifecycle. Everything else (inventory → `utils/`, create/prepare/destroy → `utils/playbooks/`) is inherited from `config.yml`.

```yaml
---
# Dedicated throwaway CHR for the destructive end-to-end: configure -> backup ->
# restore round-trip (real reboot) -> /import branch -> reset wipe (real
# reset-configuration with run-after-reset restoring API reachability). Opts out
# of shared state — a reset would sever the shared device's management plane — so
# it boots and destroys its OWN CHR. Inventory + create/prepare/destroy are
# inherited from extensions/molecule/config.yml (the utils/ playbooks). Runs as a
# separate `molecule test -s lifecycle` invocation (see the Makefile), so its
# 8728/2223 hostfwd does not collide with the shared pass.
shared_state: false
scenario:
  name: lifecycle
  test_sequence:
    - dependency
    - create
    - prepare
    - converge
    - verify
    - destroy
```

- [ ] **Step 2: Write `converge.yml`** — the ordered flow with inline checkpoint asserts (intermediate evidence must be asserted before the reset wipes it). API tasks delegate to localhost; `/export`, `/file`, `/import` go over network_cli (play vars, like the backup scenario).

```yaml
---
- name: Lifecycle — configure, backup/restore round-trip, import, reset wipe
  hosts: molecule
  gather_facts: false
  # network_cli at play level for /export, /file, /import over SSH (port 2223);
  # API tasks below delegate_to localhost (overriding this) for 127.0.0.1:8728.
  vars:
    ansible_host: "127.0.0.1"
    ansible_port: 2223
    ansible_connection: ansible.netcommon.network_cli
    ansible_network_os: community.routeros.routeros
    ansible_network_cli_ssh_type: libssh
    ansible_user: "admin+cet1024w"
    ansible_password: "{{ hostvars[inventory_hostname]['chr_admin_password'] }}"
    ansible_ssh_common_args: >-
      -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
    _recover_local: "{{ lookup('ansible.builtin.env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}/recover.rsc"
  module_defaults:
    community.routeros.api: &conn
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
    community.routeros.api_modify: *conn
  tasks:
    # --- Phase 1: configure a distinctive baseline via the configure role ---
    - name: Configure a distinctive baseline
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.configure
      vars:
        routeros_config:
          /system/identity:
            data:
              - name: lc-baseline
          /ip/pool:
            data:
              - name: lc-pool
                ranges: "192.168.123.10-192.168.123.50"

    - name: Save a binary backup of the baseline
      community.routeros.api:
        path: system backup
        cmd: "save name=lc-test password=lc-pw-123"
      delegate_to: localhost
      connection: local

    # --- Phase 2: wrong-password restore must fail without harming the device ---
    - name: Restore with the WRONG password must fail
      block:
        - name: Attempt restore with a bad password
          ansible.builtin.include_role:
            name: david_igou.routeros_configuration.restore
          vars:
            routeros_restore_backup_name: lc-test
            routeros_restore_backup_password: wrong-pw
        - name: Should not reach here
          ansible.builtin.fail:
            msg: "restore accepted a wrong backup password"
      rescue:
        - name: Expected — wrong-password restore failed, device intact
          ansible.builtin.debug:
            msg: "restore correctly rejected the wrong backup password"

    - name: Confirm the device is still up and still lc-baseline after the failed restore
      community.routeros.api:
        path: system identity
      delegate_to: localhost
      connection: local
      register: _id_after_badpw
    - name: Assert the failed restore did not reboot/alter the device
      ansible.builtin.assert:
        that:
          - (_id_after_badpw.msg | first).name == 'lc-baseline'
        fail_msg: "device altered by a wrong-password restore: {{ _id_after_badpw.msg }}"

    # --- Phase 3: restore round-trip (real reboot) ---
    - name: Change the identity so the restore is observable
      community.routeros.api_modify:
        path: system identity
        data:
          - name: lc-changed
      delegate_to: localhost
      connection: local

    - name: Restore the baseline backup (reboots, role reconnects)
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.restore
      vars:
        routeros_restore_backup_name: lc-test
        routeros_restore_backup_password: lc-pw-123

    - name: Read identity after restore
      community.routeros.api:
        path: system identity
      delegate_to: localhost
      connection: local
      register: _id_after_restore
    - name: Assert the binary restore reverted the identity across a real reboot
      ansible.builtin.assert:
        that:
          - (_id_after_restore.msg | first).name == 'lc-baseline'
        fail_msg: "binary restore did not revert: {{ _id_after_restore.msg }}"

    # --- Phase 4: /import branch (no reboot) ---
    - name: Export current config to an on-device .rsc (deterministic name)
      community.routeros.command:
        commands:
          - "/export file=lc-export"
      register: _exp
      changed_when: false

    - name: Change the identity again (so the import is observable)
      community.routeros.api_modify:
        path: system identity
        data:
          - name: lc-import-changed
      delegate_to: localhost
      connection: local

    - name: Import the exported script (re-applies identity=lc-baseline; no reboot)
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.restore
      vars:
        routeros_restore_import_file: lc-export.rsc

    - name: Read identity after import
      community.routeros.api:
        path: system identity
      delegate_to: localhost
      connection: local
      register: _id_after_import
    - name: Assert /import re-applied the exported identity
      ansible.builtin.assert:
        that:
          - (_id_after_import.msg | first).name == 'lc-baseline'
        fail_msg: "import did not re-apply baseline identity: {{ _id_after_import.msg }}"

    # --- Phase 5: real reset wipe, with run-after-reset restoring API reach ---
    # run-after-reset makes no-defaults irrelevant: the device boots BLANK and
    # runs ONLY recover.rsc, which re-enables the api service + ether2 dhcp-client
    # so the role's reconnect (and the verify) can reach 127.0.0.1:8728 again.
    - name: Author the minimal recovery script on the controller
      ansible.builtin.copy:
        dest: "{{ _recover_local }}"
        mode: "0644"
        content: |
          :delay 15s
          /ip service set [find name=api] disabled=no
          /ip dhcp-client add interface=ether2 disabled=no
      delegate_to: localhost
      connection: local

    - name: Push recover.rsc to the device via SFTP
      ansible.builtin.command:
        argv:
          - sshpass
          - -p
          - "{{ hostvars[inventory_hostname]['chr_admin_password'] }}"
          - sftp
          - -P
          - "2223"
          - -o
          - StrictHostKeyChecking=no
          - -o
          - UserKnownHostsFile=/dev/null
          - -o
          - PreferredAuthentications=password
          - -o
          - PubkeyAuthentication=no
          - -b
          - "-"
          - "admin@127.0.0.1"
        stdin: "put {{ _recover_local }} recover.rsc"
      delegate_to: localhost
      connection: local
      register: _sftp
      changed_when: _sftp.rc == 0

    - name: Reset the configuration FOR REAL (run-after-reset restores reachability)
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.reset
      vars:
        routeros_reset_confirm: true
        routeros_reset_keep_users: true
        routeros_reset_run_after_reset: recover.rsc
```

- [ ] **Step 3: Write `verify.yml`** — after the reset, the device is back (run-after-reset) but WIPED: default identity, no `lc-pool`.

```yaml
---
- name: Verify — the real reset wiped the config (device recovered via run-after-reset)
  hosts: molecule
  gather_facts: false
  module_defaults:
    community.routeros.api_info: &conn
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls }}"
      validate_certs: "{{ routeros_api_validate_certs }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
    community.routeros.api: *conn
  tasks:
    - name: Read identity (should be the factory default, not lc-baseline)
      community.routeros.api:
        path: system identity
      delegate_to: localhost
      connection: local
      register: ident
    - name: Read /ip/pool (lc-pool must be gone)
      community.routeros.api_info:
        path: ip pool
      delegate_to: localhost
      connection: local
      register: pools
    - name: Assert the reset wiped the configured state
      ansible.builtin.assert:
        that:
          - (ident.msg | first).name == 'MikroTik'
          - pools.result | selectattr('name', 'equalto', 'lc-pool') | list | length == 0
        success_msg: "reset wiped config (identity back to MikroTik, lc-pool gone); device recovered via run-after-reset"
        fail_msg: "reset did not wipe as expected: identity={{ ident.msg }} pools={{ pools.result }}"
```

- [ ] **Step 4: Run the scenario** (boots its own CHR; slow)

Run: `make molecule SCENARIO=lifecycle`
Expected: PASS through all five phases.
Validation contingencies (this is the highest-risk task — run it and watch the output):
- If the **SFTP push** fails (RouterOS sftp subsystem quirk), confirm sftp connectivity manually (`sshpass -p molecule sftp -P 2223 admin@127.0.0.1`); if unusable, stage `recover.rsc` instead via `community.routeros.command` `/file add name=recover.rsc` + `/file set [find name=recover.rsc] contents="..."`, reading back the real file name with `/file print` (handle a possible `.txt` suffix) and passing that to `routeros_reset_run_after_reset`.
- If **run-after-reset reconnect** does not come back within the role's timeout, the reset role will fail on reconnect. First raise `routeros_reset_reboot_timeout`. If still flaky, simplify Phase 5 to assert the wipe via post-reset *unreachability*: drop `run_after_reset`, wrap the reset role in `block`/`rescue` with a low `routeros_reset_reboot_timeout`, and assert the reconnect failed (device blank ⇒ API gone ⇒ wipe proven) — then report the simplification.
- If the **wrong-password restore** (Phase 2) actually reboots or hangs the device, move Phase 2 to the very end (after the wipe) or drop it and note it.

- [ ] **Step 5: Commit**

```bash
git add extensions/molecule/lifecycle/
git commit -m "test: add lifecycle scenario (backup/restore round-trip, import, real reset wipe)"
```

---

## Task 11: Rewrite `extensions/molecule/README.md` for readers

Explain the two-tier architecture, the full scenario catalogue (including the new `configure_check_mode`, `negative`, `lifecycle`), how to run them, and the boot budget. (User requirement.)

**Files:**
- Modify: `extensions/molecule/README.md`

- [ ] **Step 1: Rewrite the README** with these sections (keep the existing accurate "Shared state", "Deterministic collection resolution", and `MOLECULE_GLOB` explanations; update the "Scenarios" content):

  1. **Overview / two tiers** — Tier 1: shared CHR (the `default` scenario owns create/prepare/destroy; role scenarios reuse it over `127.0.0.1:8728`). Tier 2: dedicated opt-out CHRs (`chr`, `lifecycle`) that boot and destroy their own VM and run as separate `molecule test -s <name>` invocations.
  2. **Scenario catalogue** — a table of every scenario grouped by what it proves:
     - configure family: `default` (shared owner, no-op converge), `configure_lists`, `configure_singletons`, `configure_ordered`, `configure_modify_only`, `configure_dependency_chain`, `configure_full`, `configure_check_mode`.
     - operational roles: `backup`, `certificate`, `command`, `export_vars`, `fetch`, `ping`, `reboot`, `reset`, `restore`, `upgrade`, `user_password`.
     - cross-cutting: `negative` (failure paths), `integration_hello_world` (localhost smoke).
     - dedicated CHRs: `chr` (boot feasibility, network_cli), `lifecycle` (destructive end-to-end).
  3. **What is and isn't covered** — note the intentional exclusions: actual `upgrade` install (non-deterministic) and that the idempotence step is *vacuous* for `cmd`-based roles (`command`/`fetch`/`user_password`) because `community.routeros.api` returns `changed=False` for arbitrary ops — the verify read-backs are the real proof there. Point at `configure_full/EXCLUSIONS.md` for path coverage.
  4. **How to run** — `make molecule` (shared pass + `chr` + `lifecycle`), `make molecule SCENARIO=<name>`, and the boot budget: shared (1) + `chr` (1) + `lifecycle` (1) = **3 CHR boots**.

- [ ] **Step 2: Sanity-check the doc** renders (no broken tables) and every scenario directory under `extensions/molecule/` appears in the catalogue.

Run: `ls -1 extensions/molecule | grep -vE 'README|config.yml|requirements|utils'` and confirm each listed dir is in the README table.

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/README.md
git commit -m "docs(molecule): rewrite README — two-tier architecture + full scenario catalogue"
```

---

## Task 12: Final full-suite validation

**Files:** none (validation only)

- [ ] **Step 1: Run the entire suite** (the order matters — shared pass, then the two dedicated CHRs):

Run: `make molecule`
Expected: every scenario green, ending with the `chr` then `lifecycle` invocations passing.

- [ ] **Step 2: If any scenario fails**, fix it per its task's contingency notes, re-run that scenario alone, then re-run `make molecule` to confirm the whole suite is green. Do not mark complete until `make molecule` exits 0.

- [ ] **Step 3: Commit any fixes** with a clear message, then the work is ready for review/PR.

---

## Self-review notes (author)

- **Spec coverage:** T1.1→Tasks 1–4; T1.2→Task 5; T1.3→Task 6; T1.4→Tasks 7–8; T1.5→Task 9; T1.6→comments in Tasks 7/8 + README (Task 11); T1.7→Task 0; T2.1→Task 10; README requirement→Task 11; validation→Task 0 (harness) + Tasks 1–10 each run + Task 12. All spec items mapped.
- **Idempotence honesty:** scenarios whose mutating op is non-idempotent drop the idempotence step explicitly (Task 5 check-mode, Task 6 negative, Task 8 command); the vacuous-idempotence note is documented in code comments (Task 7) and the README (Task 11).
- **Risk concentration:** Task 10 Phase 5 (reset + run-after-reset + SFTP) is the one empirically-risky piece; it carries explicit, concrete fallbacks rather than placeholders.
- **No phantom symbols:** every register (`cm`, `_al`, `_routeros_ping`, `_id_after_*`, `_sftp`) is defined in the same task list before use; `_routeros_ping` is flagged to confirm against `roles/ping`.
