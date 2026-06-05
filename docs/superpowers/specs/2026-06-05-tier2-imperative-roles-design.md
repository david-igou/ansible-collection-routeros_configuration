# Tier 2 imperative roles — design

Date: 2026-06-05

## Problem

The `configure`/`_reconcile` roles can declaratively reconcile any path
`community.routeros.api_modify` understands, but `api_modify` only expresses
*desired state*. Several operational tasks are imperative actions it cannot
perform: creating certificates (api_modify treats `certificate` as read-only),
taking backups, upgrading packages, and running arbitrary one-off commands.
This adds four standalone **imperative** roles to cover those gaps.

## Scope (v1)

| Role | Does | Idempotent |
| --- | --- | --- |
| `command` | Run a list of arbitrary RouterOS API commands (escape hatch) | No |
| `backup` | Create on-device binary backup + optional `/export`; verify it exists | No |
| `certificate` | Create + self-sign certs, idempotent by name | Yes |
| `upgrade` | Set update channel + check for updates; gated install/reboot | Yes (safe path) |

Explicitly **deferred** (documented as follow-ups, not built here):
- `backup`: fetching the backup/export file off-box (needs SFTP/SCP, not the API).
- `certificate`: importing existing PEM cert/key files, and SCEP enrollment.
- `upgrade`: the install+reboot path exists but is gated off and not exercised
  in molecule.

## Shared conventions

All four roles are imperative and use `community.routeros.api` over the binary
API, reusing the existing `routeros_api_*` connection contract (the same block
`_reconcile` defines: hostname/username/password/tls/validate_certs/port). Each
role is self-contained and carries that connection block in its
`defaults/main.yml`.

Connection wiring is DRY via a single `block:` per role:

```yaml
- name: <role> over the RouterOS API
  delegate_to: localhost
  connection: local
  module_defaults:
    community.routeros.api:
      hostname: "{{ routeros_api_hostname }}"
      username: "{{ routeros_api_username }}"
      password: "{{ routeros_api_password }}"
      tls: "{{ routeros_api_tls | bool }}"
      validate_certs: "{{ routeros_api_validate_certs | bool }}"
      port: "{{ routeros_api_port | default(omit, true) }}"
  block:
    - ...  # role tasks; connection args inherited
```

Each role ships: `defaults/main.yml`, `meta/main.yml`, `meta/argument_specs.yml`,
`tasks/main.yml`, and `README.md` with an "Idempotency & rollback" section
(matching the repo convention from `configure`/`_reconcile`).

## Role designs

### 1. `command` (API escape hatch) — non-idempotent

Runs over the **API** (not the `community.routeros.command` CLI module); the
README states this prominently to avoid confusion.

- Input `routeros_command` (default `[]`): list of dicts, each with `path`
  (required) and exactly one action: `cmd` | `add` | `remove` | `update` |
  `query`. Passed straight through to `community.routeros.api`.
- `query` items are read-only (`changed_when: false`); action verbs report
  changed.
- argument_specs: `routeros_command` is a list/elements=dict with suboptions
  `path` (required) and the optional action keys.

Molecule: converge a `query` (e.g. `system resource`) and a benign mutating
round-trip; verify the query returned data and the mutation took effect.
test_sequence drops `idempotence`.

### 2. `backup` — non-idempotent

- Vars: `routeros_backup_name` (default `ansible`), `routeros_backup_password`
  (optional; encrypts the binary backup), `routeros_backup_export` (default
  `true`), `routeros_export_options` (default `""`, e.g. `hide-sensitive`).
- Tasks:
  1. `community.routeros.api` path `system backup`, `cmd: save name=<name>`
     (+ `password=...` when set).
  2. When `routeros_backup_export`: run `/export file=<name> <options>`. Export
     is a root-level command; whether the `api` module can invoke it (path `""`
     + `cmd: export ...`) is validated during implementation. If it cannot, v1
     ships binary-backup-only with a clear note, and export becomes a follow-up.
  3. Verify: `api_info` (or `api` query) on path `file`; assert `<name>.backup`
     is present.
- Not idempotent (a backup is point-in-time). test_sequence drops `idempotence`.

Molecule: converge with a fixed name; verify the `.backup` file exists in `file`.

### 3. `certificate` — idempotent

- Var `routeros_certificates` (default `[]`): list of dicts with `name`
  (required), `common_name` (required), and optional `key_size` (default 2048),
  `days_valid` (default 365), `key_usage`, `trusted` (default `false`), `ca`
  (name of a signing cert; omitted → self-signed).
- Per cert (idempotent):
  1. Query `certificate` by name.
  2. If absent: `add name=<> common-name=<> key-size=<> days-valid=<>` (creates
     the request/template).
  3. If present but not yet signed: `cmd: sign .id=<id> [ca=<ca>] [name=<>]`.
     Guarded on signed-state so re-runs are no-ops.
- Verify: `api_info` on `certificate`; assert each cert exists and is signed
  (e.g. has a fingerprint / `private-key` present).
- Idempotent: keeps the default `[dependency, converge, idempotence, verify]`
  sequence.

Molecule: create a self-signed CA plus a host cert (`ca:` referencing the CA);
verify both exist and are signed; the `idempotence` step proves no-op re-runs.

### 4. `upgrade` — idempotent safe path

- Vars: `routeros_update_channel` (default `stable`), `routeros_upgrade_install`
  (default `false`), `routeros_upgrade_reboot_timeout` (default 300),
  `routeros_routerboard_firmware` (default `false`).
- Tasks:
  1. Query current channel on `system package update`; set it only if different
     (idempotent).
  2. `cmd: check-for-updates` (`changed_when: false`).
  3. When `routeros_upgrade_install` **and** an update is available: `cmd:
     install` (reboots the device), then wait for the API port to drop and
     return within `routeros_upgrade_reboot_timeout`. When
     `routeros_routerboard_firmware`: also upgrade RouterBOARD firmware. This
     whole step is gated off by default.
- Idempotent on the safe path (channel set is guarded, check is read-only).

Molecule: set `channel: stable` + check-for-updates with install gated off;
verify the channel is set and a status was returned; `idempotence` passes.

## Molecule integration

- Four new scenarios: `extensions/molecule/{command,backup,certificate,upgrade}/`
  each with `molecule.yml`, `converge.yml`, `verify.yml`.
- They inherit create/prepare/destroy + the API inventory from the shared
  `extensions/molecule/config.yml`, running against the single shared CHR. Only
  `backup` and `command` override `test_sequence` to
  `[dependency, converge, verify]` (drop `idempotence`); `certificate` and
  `upgrade` use the shared default.
- Wire all four into the CI `molecule-qemu` `shared` job list
  (`.github/workflows/tests.yml`) and the `Makefile` shared pass, appended after
  `configure_full`. They mutate independent device state (certs, backup files,
  update channel) so ordering after the configure scenarios is safe.

## Error handling

- argument_specs enforce required inputs (cert `name`+`common_name`, each
  `command` item's `path`); bad input fails before hitting the device.
- API errors fail the task (module behaviour).
- `upgrade` install (gated) wraps reboot + reconnect with
  `routeros_upgrade_reboot_timeout`; a failure to reconnect fails the run.

## Out of scope

Off-box file transfer, PEM/SCEP certificate import, and exercising the
upgrade-install/reboot path in CI — all noted as follow-ups in the respective
role READMEs and the enhancement backlog.

## Changelog

One `minor_changes` fragment announcing the four new roles.
