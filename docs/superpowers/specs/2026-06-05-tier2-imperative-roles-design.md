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

## Molecule (`extensions/molecule/backup/`, network_cli on the shared CHR)

The shared CHR already forwards SSH on `127.0.0.1:2222` and bootstraps
`admin`/`molecule` (`utils/prepare.yml`), so the scenario **joins the shared
pass** (`shared_state`, inherits create/prepare/destroy) and connects via
network_cli at *play* level — exactly the `chr/verify.yml` pattern, but against
the shared instance. No separate VM.

- `converge.yml`: play sets the network_cli connection vars (libssh,
  `admin+cet1024w`, `chr_admin_password`). First ensure a WireGuard interface
  named `bk-wg` exists via `community.routeros.api_modify` (`delegate_to:
  localhost`, name only — RouterOS auto-generates the private-key; idempotent, no
  key-normalisation diff). Then `include_role: backup` with
  `routeros_backup_dir` under `MOLECULE_EPHEMERAL_DIRECTORY` and
  `routeros_backup_binary: true`.
- `verify.yml`: assert (a) the `.rsc` exists and contains `bk-wg` plus a
  `private-key=` line (proves "export with secrets" on a real CHR), (b) it
  contains no `/user` `set ... password=` (documents the known gap), and (c) the
  binary `ansible.backup` is present in `/file` (via a `/file print where name=…`
  command).
- Idempotence: the scenario keeps the default `converge → idempotence → verify`
  sequence. Only the controller `copy` reports *changed* (and only when the
  config changed); both `command` tasks are `changed_when: false` — reading the
  export is not a change, and a backup-save is treated as a non-reporting action
  (the standard backup-role idiom). So a second run of unchanged config is green
  even with `routeros_backup_binary: true`. The README notes the binary file is
  rewritten each run (a fresh point-in-time artifact) though the task reports
  `ok`.

Add `backup` to the shared-pass scenario list (CI `molecule-qemu` `shared` leg
and the `Makefile`), after `configure_full`.

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
