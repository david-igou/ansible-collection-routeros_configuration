# `backup` role — design

Date: 2026-06-05

> Scope was narrowed from four Tier 2 roles to **`backup` only**, and the
> approach changed to mirror the official RouterOS backup/restore procedure
> while staying idempotent. Earlier drafts (four roles; an `api_info` structured
> snapshot) are superseded by this document.

## Problem

`configure`/`_reconcile` reconcile declarative *desired state*; they don't
capture a device's current configuration for safekeeping. We want a role that
takes a backup, **follows the official RouterOS backup/restore docs**, and is
**idempotent** (safe to run every play; only changes when the config changed).

## What the official docs say

From MikroTik's
[Backup](https://help.mikrotik.com/docs/spaces/ROS/pages/40992852/Backup) and
[Configuration Management](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management):

- **Binary backup** — `/system backup save name=<> password=<>` writes a file in
  `/file`; restore with `/system backup load name=<> password=<>` (reboots).
  Full fidelity (user passwords, MAC addresses), but same-device / same-version
  only, and sensitive — encrypt it.
- **Config export** — `/export` produces portable plain-text `.rsc`; restore via
  `/import`. Officially **omits** system user passwords, installed certificates,
  SSH keys, Dude, and the User-manager database.

Verified independently against `community.routeros` v3.20.0 field metadata: every
service secret (WireGuard private-key, IPsec PSK, PPP/PPPoE secret, SNMP
community, WiFi passphrase) is readable; the only write-only secret field is
`/user password`. So an export "with secrets" (`show-sensitive`) carries the
service secrets and, like every export, cannot carry user passwords.

## Approach

Two artifacts, mirroring the two official mechanisms. The **export** is the
idempotent primary; the **binary backup** is opt-in full-fidelity.

### Primary (idempotent): config export to the controller

- `community.routeros.command` (network_cli) runs `/export` (with
  `show-sensitive` when `routeros_backup_show_sensitive`), capturing stdout — no
  on-device file, no transfer.
- Strip the volatile leading header comment block (the `# <date> by RouterOS …`
  lines) so output is content-stable.
- Write to `{{ routeros_backup_dir }}/{{ inventory_hostname }}.rsc` with
  `ansible.builtin.copy` (`delegate_to: localhost`). `copy` only reports
  *changed* when content differs → **idempotent**.
- Restore is `/import file=<>` (documented in the README, not performed here).

### Optional (full fidelity, opt-in): binary backup

- `routeros_backup_binary: true` → `community.routeros.command` runs
  `/system backup save name=<name> password=<password>` (encrypted when a
  password is given). Stays on the device per the official workflow.
- Not idempotent (a binary backup is a point-in-time artifact); the README
  documents `/system backup load` restore and the encrypt/store-safely warning.
- Off-box fetch of the binary file is **out of scope** (needs SFTP/SCP; official
  docs treat the binary as on-device + manual copy).

## Connection

network_cli, like the existing `chr` scenario: `ansible_connection=network_cli`,
`ansible_network_os=community.routeros.routeros`, libssh transport (paramiko
fails RouterOS SSH negotiation — see `test-requirements.txt`). `/export` is
console-only, so the binary API is not an option here. The collection already
ships this path (`chr` scenario, `ansible.netcommon` dependency).

## Variables

| Var | Default | Meaning |
| --- | --- | --- |
| `routeros_backup_dir` | `./routeros-backups` | controller dir for `.rsc` files |
| `routeros_backup_show_sensitive` | `true` | `/export show-sensitive` (include service secrets) |
| `routeros_backup_export_options` | `""` | extra `/export` args (e.g. a menu path, `terse`) |
| `routeros_backup_binary` | `false` | also `/system backup save` on the device |
| `routeros_backup_name` | `ansible` | binary backup file name |
| `routeros_backup_password` | `""` (omit) | binary backup encryption password |

No `routeros_api_*` block — this role is network_cli, configured via the
inventory's connection vars, not the API contract.

## Role files

`roles/backup/`: `defaults/main.yml`, `meta/main.yml`,
`meta/argument_specs.yml`, `tasks/main.yml`, `README.md` (usage + an
"Idempotency & restore" section quoting the official `/import` and
`/system backup load` procedures and the export-omits caveats).

`tasks/main.yml` outline:
1. `ansible.builtin.file` (delegate localhost) — ensure `routeros_backup_dir`.
2. `community.routeros.command` — `/export {{ show-sensitive }} {{ options }}`,
   register stdout, `changed_when: false` (reading config is not a change).
3. Strip the header comment block from the captured lines.
4. `ansible.builtin.copy` (delegate localhost) — write `<host>.rsc` from the
   stripped content; this task carries the real idempotency.
5. When `routeros_backup_binary`: `community.routeros.command` —
   `/system backup save name=<> [password=<>]`.

## Molecule (`extensions/molecule/backup/`, network_cli)

Modeled on the `chr` scenario (its own CHR VM, libssh, opts out of
`shared_state`), because the role needs SSH/network_cli, not the API hostfwd the
shared scenarios use.

- `converge.yml`: first set a recognizable secret (a WireGuard interface with a
  known private-key, or an IPsec identity PSK) via the API, then run the
  `backup` role with `routeros_backup_dir` pointed at the scenario's ephemeral
  dir and `routeros_backup_binary: true`.
- `verify.yml`: assert (a) the `.rsc` exists and contains the WireGuard
  interface/secret (proves "export with secrets" on a real CHR), (b) it contains
  no `set password=` for `/user` (documents the known gap), and (c) the binary
  `<name>.backup` file is present in `/file` via `api_info`/command.
- Idempotence: the scenario keeps the default `converge → idempotence → verify`
  sequence. Only the controller `copy` reports *changed* (and only when the
  config changed); both `command` tasks are `changed_when: false` — reading the
  export is not a change, and a backup-save is treated as a non-reporting action
  (the standard backup-role idiom). So a second run of unchanged config is green
  even with `routeros_backup_binary: true`. The README notes the binary file is
  rewritten each run (a fresh point-in-time artifact) though the task reports
  `ok`.

Wire the scenario into the CI `molecule-qemu` matrix (its own leg, like `chr`,
since it needs its own network_cli VM) and the `Makefile`.

## Error handling

- argument_specs validate types (`routeros_backup_dir` str, booleans typed,
  `routeros_backup_password` str with `no_log`).
- `command` failures fail the task.
- Header-strip is defensive: if the expected header is absent, write the full
  output rather than dropping lines.

## Out of scope

Off-box transfer of the binary backup, `/import`-based restore automation, and
any non-backup Tier 2 role (command/certificate/upgrade) — tracked in the
enhancement backlog.

## Changelog

One `minor_changes` fragment announcing the `backup` role.
