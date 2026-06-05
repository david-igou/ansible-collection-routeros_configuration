# `certificate` and `upgrade` roles — design

Date: 2026-06-05

Two more Tier 2 imperative roles (after `backup`). Both run over the **binary
API** (`community.routeros.api`, `delegate_to: localhost`), reuse the
`routeros_api_*` connection contract via a `module_defaults` block, and are
**idempotent** by querying current state and gating actions with `when`. Their
molecule scenarios join the shared-CHR API pass like the `configure_*` scenarios.

`community.routeros.api` returns query/command output in `.message` (a list of
dicts) and is not idempotent itself, so each role reads first and only acts when
needed.

## `certificate` — create + sign, idempotent

api_modify treats `certificate` as read-only, so this uses the `api` module's
`add`/`cmd`. Closes the TLS-bootstrap gap (the collection defaults to
`tls: true`).

- Var `routeros_certificates` (default `[]`): list of dicts —
  `name` (req), `common_name` (req), `key_size` (default 2048),
  `days_valid` (default 365), `key_usage` (list, optional), `ca` (name of a
  signing cert; omitted → self-signed).
- Tasks (in one `module_defaults` block):
  1. Read `certificate`.
  2. `add name=… common-name=… key-size=… days-valid=… [key-usage=…]` for each
     cert whose name is absent (creates the request/template).
  3. Re-read `certificate` (`changed_when: false`).
  4. For each cert with an empty `fingerprint` (not yet signed):
     `cmd: sign .id=<id> [ca=<ca>] name=<name>`. Self-signed when `ca` omitted.
- Idempotent: a cert that exists and is signed (non-empty `fingerprint`) skips
  both add and sign, so re-runs report no change. List CAs before the host certs
  that reference them.

## `upgrade` — channel + check, gated install

- Vars: `routeros_update_channel` (default `stable`),
  `routeros_upgrade_install` (default `false`),
  `routeros_upgrade_reboot_timeout` (default 300).
- Tasks:
  1. Read `system package update`.
  2. `cmd: set channel=<channel>` only when the current channel differs
     (idempotent).
  3. `cmd: check-for-updates` (`changed_when: false`); re-read status.
  4. When `routeros_upgrade_install` **and** an update is available:
     `cmd: install` (reboots), then `wait_for` the API port to return within
     `routeros_upgrade_reboot_timeout`. Gated off by default.
- Idempotent on the safe path (channel set is conditional, check is read-only).

## Molecule (`extensions/molecule/{certificate,upgrade}/`)

Shared-CHR API scenarios (like `configure_*`), keeping the default
`converge → idempotence → verify` sequence (both roles are idempotent).

- `certificate`: converge creates a self-signed CA plus a host cert signed by it;
  verify asserts (via `api_info`) both exist with a non-empty `fingerprint`; the
  idempotence step proves no-op re-runs.
- `upgrade`: converge sets `channel: stable` with install gated off; verify
  asserts the channel is set. `check-for-updates` needs outbound internet, which
  the shared CHR has (SLIRP NAT + `/ip/dns` from the configure scenarios); if it
  proves flaky in CI it will be made tolerant.

Wire both into the CI `shared` leg and the `Makefile`, after `backup`.

## Validation

Developed and run green locally with `molecule test -s default -s certificate
-s upgrade` (QEMU CHR) **before** pushing — including the `changed=0` idempotence
runs — then CI confirms.

## Out of scope

PEM/SCEP certificate import, `trusted` flag management, RouterBOARD firmware
upgrade, and exercising the upgrade-install/reboot path in CI. Tracked in the
backlog.

## Changelog

One `minor_changes` fragment per role.
