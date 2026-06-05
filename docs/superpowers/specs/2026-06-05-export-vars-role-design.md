# `export_vars` role — design

Date: 2026-06-05

## Problem

`configure` applies a `routeros_config` dict to a device. There is no reverse:
capturing a running device's current configuration into the equivalent Ansible
vars, so an existing device can be brought under declarative management
(capture → version-control → re-apply via `configure`).

## Approach

A role that reads the device over the binary API (`community.routeros.api_info`,
`delegate_to: localhost`, reusing the `routeros_api_*` contract via a
`module_defaults` block) and writes a per-host `routeros_config` vars file to the
Ansible controller.

### Flow

1. Ensure `routeros_export_vars_dir` exists (controller, `connection: local`).
2. Load the canonical path list (see below).
3. Loop `api_info` over the paths with `hide_defaults: true`,
   `include_dynamic: false`, `include_read_only: false` (persistent config only),
   `changed_when: false`.
4. Assemble the `routeros_config` dict with the
   `to_routeros_config` filter (below).
5. Write `{{ routeros_export_vars_dir }}/{{ inventory_hostname }}.yml` (containing
   a top-level `routeros_config:` key) via `ansible.builtin.copy` — idempotent
   write-if-changed.

### Filter plugin

`plugins/filter/to_routeros_config.py` — exposes
`david_igou.routeros_configuration.to_routeros_config`. Shaping the captured data
is awkward in pure Jinja, so it lives in a tested, documented filter (modeled on
the existing `plugins/filter/sample_filter.py`, with a unit test).

- Signature: `to_routeros_config(results, redact=False, sensitive_fields=DEFAULT)`.
  - `results`: the registered `api_info` loop results (`_captured.results`), each
    item exposing `.item` (slash path) and `.result` (list of entry dicts).
  - Returns `{slash_path: {data: [entries]}}` for every path whose `result` is
    non-empty.
  - Each entry has `.id` removed. When `redact`, any key in `sensitive_fields`
    has its value replaced with `REDACTED`.
- `DEFAULT` sensitive fields: `private-key`, `preshared-key`, `secret`,
  `password`, `authentication-password`, `encryption-password`, `passphrase`,
  `passphrase-...` variants — the readable secret fields verified earlier.

### Path list

Default `routeros_export_vars_paths` is the configure role's canonical
`rcfg_path_order` (all 508 configurable paths), sourced via `include_vars` of the
sibling role's vars file:

```yaml
- name: Load the canonical path order from the configure role
  ansible.builtin.include_vars:
    file: "{{ role_path }}/../configure/vars/main.yml"
  when: routeros_export_vars_paths is not defined
```

This avoids duplicating the 508-entry list (one canonical source). The coupling
is intentional and within the same collection. Users may override
`routeros_export_vars_paths` with any subset (faster). Paths with no entries are
omitted from the output.

## Variables

| Var | Default | Meaning |
| --- | --- | --- |
| `routeros_export_vars_dir` | `./routeros-vars` | controller output directory |
| `routeros_export_vars_paths` | `rcfg_path_order` (508) | slash paths to capture |
| `routeros_export_vars_redact` | `false` | replace sensitive field values with `REDACTED` |
| plus the shared `routeros_api_*` connection block | | |

## Secrets

`api_info` returns service secrets (WireGuard keys, IPsec PSKs, PPP/SNMP/WiFi
secrets — verified readable; only `/user` passwords are write-only). They are
**included by default** so the file round-trips; the README warns the output
contains secrets and should be `ansible-vault` encrypted. `routeros_export_vars_redact:
true` replaces them with `REDACTED` (safe to commit, but not directly
re-appliable).

## Idempotency

Only the `copy` reports `changed`, and only when the captured config differs; the
`api_info` reads are `changed_when: false`. Relies on RouterOS's stable entry
ordering and `to_nice_yaml`'s sorted keys for a deterministic file.

## Fidelity caveat (documented)

`api_info` fields do not always map 1:1 to `api_modify` input (some
computed/normalized values, boolean spellings). The captured vars are a
**best-effort equivalent** that may need light review before re-applying — not a
guaranteed byte-perfect round-trip.

## Molecule (`extensions/molecule/export_vars/`)

Shared-CHR API scenario (like `configure_*`), keeping the default
`converge → idempotence → verify` sequence.

- `converge`: ensure a known entry (e.g. an `/ip/address` on a spare interface)
  via `api_modify` (idempotent), then run `export_vars` with a small
  `routeros_export_vars_paths` override (a handful of paths, for speed) writing
  into `MOLECULE_EPHEMERAL_DIRECTORY`.
- `verify`: load the output YAML; assert it has `routeros_config` containing the
  expected path with the known entry, and that `.id` is absent from the entries.
- Idempotence: a second capture of unchanged config yields the same file.

Developed and run green locally (`molecule test -s default -s export_vars`,
QEMU CHR), including the `changed=0` idempotence run, before pushing.

## Out of scope

Capturing `/user` passwords (write-only — impossible), perfect round-trip
fidelity, and per-path `purge`/`order`/`content` inference (the output uses plain
`data:` lists; users add purge/order as desired). Tracked in the backlog.

## Changelog

One `minor_changes` fragment for the role + filter.
