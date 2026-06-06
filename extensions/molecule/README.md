# Molecule scenarios

These scenarios test the collection's roles against a **real MikroTik CHR**
(Cloud Hosted Router) VM booted over qemu by
[`david_igou.molecule_provisioners`](https://galaxy.ansible.com/ui/repo/published/david_igou/molecule_provisioners/).
They are not mocks: every `verify.yml` reads real device state back over the
binary API (`community.routeros.api_info` / `api`) or the CLI
(`community.routeros.command`).

Invoke from the **collection root**:

```bash
# Full suite: the shared pass (one CHR for all the shared scenarios), then the
# two dedicated-CHR scenarios (chr, lifecycle):
make molecule

# A single scenario:
make molecule SCENARIO=configure_singletons      # shared tier (auto-prepends `default`)
make molecule SCENARIO=lifecycle                 # dedicated tier (boots its own CHR)
```

## Two tiers

**Tier 1 — shared CHR.** `extensions/molecule/config.yml` sets
`shared_state: true` and a dedicated `default` scenario owns the instance
lifecycle: molecule runs `default`'s **create + prepare + destroy exactly once**
for the whole run, and every shared scenario reuses that single CHR over the
fixed `127.0.0.1:8728` API hostfwd (their api tasks `delegate_to: localhost`, so
no SSH to the device is needed). This replaces ~20 per-scenario boots with one.
Because all shared scenarios mutate the same device sequentially, each binds
**dedicated ports** where it would otherwise conflict (see
`utils/inventory/hosts.yml`, 11 ethers).

A single shared scenario has **no `create` step of its own**, so
`make molecule SCENARIO=<name>` automatically prepends `default` (which boots and
tears down the CHR around it) — see the Makefile's `SELF_OWNING` logic.

**Tier 2 — dedicated opt-out CHRs.** Some scenarios cannot share the device:
`chr` verifies over `network_cli` (its own runtime inventory), and `lifecycle`
performs a real `reset-configuration` that would sever the shared device's
management plane. These set `shared_state: false`, own their create/prepare/
destroy, and run as **separate** `molecule test -s <name>` invocations (after the
shared pass has torn its CHR down, so the `8728/2223` hostfwd is free).

**Boot budget:** shared (1) + `chr` (1) + `lifecycle` (1) = **3 CHR boots** for
the full suite.

## Scenario catalogue

### configure role (declarative `routeros_config`)

| Scenario | Proves |
| --- | --- |
| `default` | Shared-state owner: boots + prepares the one CHR; its converge is a no-op. |
| `configure_lists` | Keyed-path apply (`/ip/pool`, `/ip/dns/static`), in-place **update** of a non-key field (matched by key), and `purge`. |
| `configure_singletons` | Singleton paths (`/system/identity`, `/ip/dns`, `/ip/settings`) — asserts servers, `allow-remote-requests`, `tcp-syncookies`. |
| `configure_ordered` | Keyless ordered firewall with `purge`+`order`; in-place update matched by `comment` (no duplicate). |
| `configure_modify_only` | `/ip/service` built-in rows that can only be modified (disables `telnet`). |
| `configure_dependency_chain` | Cross-path **ordering** (`bridge→port`, `pool→dhcp-server→lease`, `list→member`) authored shuffled, applied + idempotent. |
| `configure_full` | Comprehensive — 75+ CHR-configurable paths in one shuffled call; converge proves ordering, idempotence proves clean reconciliation. See `configure_full/EXCLUSIONS.md`. |
| `configure_check_mode` | `--check` predicts a change but writes **nothing** (read-back proves the device is untouched); the real apply then lands it. |

### operational roles

| Scenario | Proves |
| --- | --- |
| `backup` | `/export` (with a service secret present, user passwords absent) + binary `/system backup save`; idempotent text export. |
| `certificate` | Create + sign a CA and a host cert; **trust chain** (`mol-host.ca == mol-ca`, `akid == ca.skid`); export-kept / import-consumed files. |
| `command` | The escape hatch: `cmd` (set note) plus an `add`+`remove` address-list round-trip. |
| `export_vars` | Captures device config into a replayable `routeros_config` vars file (no `.id` leakage); asserts `/ip/address` + `/system/identity` capture. |
| `fetch` | `/tool fetch` onto the device, then the `routeros_fetch_remove` delete branch. |
| `ping` | `/tool ping` reachability (received > 0). |
| `reboot` | `/system reboot` + reconnect; asserts uptime reset. |
| `reset` | The **safety gate**: with `routeros_reset_confirm` unset, the destructive reset does **not** run (a marker identity survives). |
| `restore` | Binary backup save → mutate → `/system backup load` (real reboot) → identity reverted. |
| `upgrade` | Sets the package update `channel` idempotently (install is gated off). |
| `user_password` | Rotates a throwaway user's password, then **authenticates** as that user with the new password. |

### cross-cutting

| Scenario | Proves |
| --- | --- |
| `negative` | Failure paths: `command` two-op item, `user_password` missing user, `configure` `order` without `purge` all fail as designed; an unreachable `ping` returns 0 received. No mutation occurs (validation fires first). |
| `integration_hello_world` | Localhost smoke test of the integration-target harness (no CHR). |

### dedicated-CHR (Tier 2)

| Scenario | Backend | Proves |
| --- | --- | --- |
| `chr` | qemu (network_cli) | A CHR boots via the qemu provider and RouterOS is reachable over `community.routeros` (CLI). |
| `lifecycle` | qemu (API + CLI) | The destructive end-to-end on a throwaway CHR: configure a baseline → binary backup → wrong-password restore is rejected → restore round-trip (real reboot, identity reverts) → `/import` of a set-based partial script → real `reset-configuration` wipe (proven by the device going unreachable on the managed interface). |

## What is and isn't covered

- **Idempotence is vacuous for `cmd`-based roles** (`command`, `fetch`,
  `user_password`): `community.routeros.api` returns `changed=False` for `cmd`
  (arbitrary) ops regardless of effect, so molecule's idempotence step there can
  never fail. The verify **read-backs** are the real proof for those roles.
- **`upgrade` install is not asserted** — whether a newer RouterOS version
  exists upstream is non-deterministic, so only the idempotent channel-set is
  tested.
- **Path coverage** for `configure_full` (which paths a bare CHR can/can't
  configure, and why) is documented in `configure_full/EXCLUSIONS.md`
  (reproduce with `utils/scripts/probe_paths.py`). `/ip/route` is notably *not*
  reconcilable idempotently via the keyless `configure` path on a bare CHR — see
  that file.
- **Not exercised by design:** the `reset` role's `run-after-reset` recovery and
  the `restore` role's import of a *full* `/export` — staging a custom `.rsc` on
  the device (SFTP/`/file`) is fragile and out of molecule's scope, and a full
  add-based `/export` cannot be re-imported onto a populated device
  (`... such name exists`). `lifecycle` instead proves the reset wipe by
  unreachability and tests `/import` with a set-based partial script.

## How it's wired

`extensions/molecule/config.yml` is auto-discovered (only from the collection
root) and deep-merged into every scenario: it sets `shared_state`, the
`dependency` step (pins the test-only provisioner from
`requirements-test.yml`), the shared `test_sequence`
(`dependency → converge → idempotence → verify`), `verifier: ansible`, and the
provisioner wiring (`create`/`prepare`/`destroy` → `utils/playbooks/`,
`converge`/`verify` → each scenario's own dir). So a shared scenario's
`molecule.yml` is just its name; dedicated scenarios override `shared_state` and
`test_sequence`.

- **Test-only** provisioner backends come from `requirements-test.yml`
  (installed by molecule's `dependency` step) — **not** the root
  `requirements.yml`, so consumers never auto-pull test tooling.
- **Runtime** deps (`community.routeros`, `ansible.netcommon`) come from the root
  `requirements.yml` and are installed by `make install`.

`MOLECULE_GLOB=extensions/molecule/*/molecule.yml` (exported by the Makefile)
points molecule at this collection's layout and lets it auto-discover
`config.yml`.
