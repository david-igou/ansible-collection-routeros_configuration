# Operational task roles — design (Tier A/B/C)

Date: 2026-06-05

Ten operational features from the MikroTik docs review (issues #13–22). All are
imperative actions over the binary API (`community.routeros.api` `cmd`, except
where noted), reusing the `routeros_api_*` contract via a `module_defaults`
block, `delegate_to: localhost`. New roles unless marked "extend".

`community.routeros.api` returns results under `.msg`; `cmd` is non-idempotent
and always reports `changed=false` (so action-only roles pass molecule
idempotence trivially). The `api` `cmd` runs `verb [params]` where params become
`key=value` (incl. `.id=`); CLI `[find ...]` is NOT supported — look up `.id`
first.

## Assumptions (made per the user's direction)

- **Destructive/unrecoverable-on-CHR paths are gated and not exercised in CI**,
  documented (no silent caps): RouterBOARD firmware upgrade (CHR has no
  RouterBOARD), ACME (needs a public domain), `/system shutdown` (can't verify
  return), and the *actual* `/system reset-configuration` (re-bootstrapping a
  wiped CHR reliably is out of scope — the role is gated behind an explicit
  confirm var, and molecule tests the gate).
- **Reboot and binary-restore ARE exercised** — they reboot the CHR but recover,
  so their scenarios run last in the shared pass, each waiting for the API to
  return before the next.
- Throwaway test objects are used where touching shared state would break the
  pass (e.g. `user_password` sets a *new* user's password, never `admin`).

## Roles

### facts (#21) — `api_facts`, read-only, idempotent
Run `community.routeros.api_facts` (gather_subset configurable). Molecule: assert
`ansible_net_*`/`ansible_facts` populated.

### ping (#22) — `/tool ping`, idempotent
`routeros_ping`: list of `{address, count?, interface?}`. Each → `cmd: ping
address=<> count=<>`. Registers results. Molecule: ping the SLIRP gateway
(`10.0.3.2`), assert `received > 0` in the result.

### command (#15) — arbitrary api ops
`routeros_command`: list of `{path, one-of cmd|add|remove|update}`. Passes
through to `community.routeros.api`. Molecule: `set` system note, assert it.

### fetch (#14) — `/tool fetch` + `/file remove`
`routeros_fetch`: list of `{url, dst_path, mode?, ...}` → `cmd: fetch ...`.
`routeros_fetch_remove`: list of file names → `/file remove`. Molecule: fetch the
device's own web root (`http://127.0.0.1/`) to a file, assert it appears in
`/file`, then remove it.

### user_password (#17) — set `/user` passwords
`routeros_user_passwords`: list of `{name, password}`. Per user: query `.id` by
name, then `cmd: set .id=<id> password=<pw>` (no_log). Not idempotent (password
is write-only). Molecule: create a throwaway `pwtest` user (api, guarded), set
its password, then authenticate as `pwtest` via `api_info` (success proves it).

### certificate extensions (#18) — extend roles/certificate
Add `routeros_certificates_export` (`{name, file_name, type?, export_passphrase?}`
→ `cmd: export-certificate ...`), `routeros_certificates_import`
(`{file_name, name?, passphrase?}` → `cmd: import ...`), and
`routeros_acme` (gated `{dns_name, ...}` → `cmd: add-acme ...`, untested).
Molecule (extend certificate scenario): export `mol-ca` to a `.crt`, import it
back under a new name, assert the imported cert exists.

### upgrade extension (#19) — extend roles/upgrade
Add `routeros_routerboard_upgrade` (bool, default false) → `cmd: upgrade` on
`system routerboard` then reboot+wait. Gated; not exercised on CHR (no
RouterBOARD) — documented.

### reset (#20) — `/system reset-configuration`, gated
`routeros_reset_confirm` (default false) gates the action.
`routeros_reset_keep_users`, `_no_defaults`, `_run_after_reset`. When confirmed →
`cmd: reset-configuration ...` (reboots). Molecule: run **unconfirmed**, assert
the role makes no change (the gate). The real reset is documented as not
exercised in CI.

### restore (#13) — binary backup load / import
`routeros_restore_backup` (`{name, password?}` → `cmd: /system backup load`,
reboots) and `routeros_restore_import` (`{file_name, ...}` → `cmd: /import`).
Molecule: set identity `rst-baseline`, `system backup save name=rst`, set
identity `rst-changed`, restore loads `rst` (reboots → identity reverts), wait
for the API, assert identity == `rst-baseline`. Runs near the end (reboots).

### reboot (#16) — `/system reboot` (+ shutdown gated)
`routeros_reboot` (bool, default true) → `cmd: reboot`, then `wait_for` the API
port. `routeros_shutdown` (bool, default false, gated/untested). Molecule (LAST
scenario): reboot, wait for the API, assert `/system/resource` uptime is small
(recently rebooted).

## Molecule integration

Most scenarios join the shared-CHR API pass. Order: the existing scenarios, then
the new safe ones (facts, ping, command, fetch, user_password, reset-gated,
certificate ext folded into the existing certificate scenario), then the
**rebooting** ones last: `restore`, then `reboot` (very last). Each rebooting
scenario waits for the API to return so the next can run. Wired into the CI
`shared` leg and the `Makefile`.

Validated locally end-to-end (`molecule test -s default -s ...`, QEMU CHR),
including idempotence, before any push.

## Changelog

One `minor_changes` fragment per role/extension.
