# Design: Thorough, RouterOS-meaningful molecule coverage

Date: 2026-06-05
Status: Approved (design); pending implementation plan
Branch: `test/molecule-thorough-coverage`

## Problem

The `david_igou.routeros_configuration` collection ships 13 roles and a molecule
suite under `extensions/molecule/`. An audit (roles ↔ scenarios ↔ MikroTik
RouterOS v7 docs) found the suite is **already strong** — shared-state single-CHR
design, real `community.routeros.api_info`/`command` device read-back in most
verifies, current molecule 26.x schema (`ansible.executor.args`,
`verifier: ansible`, `shared_state: true`), and **zero RouterOS-correctness
errors** (every path/property/operation verified real in v7). But it has concrete
gaps that keep it from being *thorough*:

1. **No check-mode (`--check`) coverage** anywhere, though `configure`/`_reconcile`
   (`api_modify`), `backup`, and `export_vars` support it meaningfully.
2. **No negative / failure-path tests**, despite explicit validation logic in
   roles: `command` `_cmd_bad` (exactly-one-op), `user_password` missing-user
   assert, `_reconcile` `order`-without-`purge` assert, `ping` unreachable.
3. **Vacuous idempotence on `cmd`-based roles** (`command`, `fetch`,
   `user_password`): `community.routeros.api` returns `changed=False` for
   `cmd`/arbitrary ops regardless of effect (`api.py` `api_arbitrary` →
   `return_result(False)`); `changed=True` only for `add`/`remove`/`update`. So
   molecule's idempotence step on those scenarios can never fail — false comfort.
4. **Destructive paths gated off & untested**: `reset` actual wipe, `restore`'s
   `/import` branch + wrong-password, `reboot` shutdown. (`reboot` and `restore`
   already exercise a real reboot+reconnect on the shared device.)
5. **Applied-but-unasserted values & untested branches**: `/ip/settings`
   `tcp-syncookies`, `/ip/dns` `allow-remote-requests`, `/ip/dns/static`,
   `export_vars` `/system/identity`, certificate trust-chain (issuer), `fetch`
   remove-branch, `command` `add`/`remove` ops; `configure_full` reads back only
   ~5 of 74 applied paths.
6. **RouterOS realism gaps**: `/ip/route` (static routes — the most common
   object, totally absent) and `/system/ntp/client` are not exercised.
7. **Stale docs**: README "Scenarios" table and Makefile `MOLECULE_SCENARIOS`
   reference scenarios that don't exist (`ip_dns`, `system_identity`, …).

## Goals

- Make the suite genuinely thorough and **meaningful to real RouterOS
  operations**, covering check-mode, negative paths, untested role branches, and
  the destructive backup→reset→restore lifecycle.
- Keep every change **ansible-native and molecule-recommended** (current
  `ansible.executor.args` schema, `verifier: ansible`, task-level `check_mode`,
  `block`/`rescue` for negative tests, `api_info` read-back for verification).
- Keep the suite's CHR-boot budget small and avoid coupling scenarios to a
  fragile shared mutation order.
- Give readers a clear `extensions/molecule/README.md` explaining the
  architecture.

## Non-goals / explicit exclusions (with rationale)

- **No assertion on an actual `upgrade` install.** It is non-deterministic
  (depends on a newer RouterOS version existing upstream + CHR internet at test
  time). The shared `upgrade` scenario already proves the idempotent channel-set.
  Documented as an intentional exclusion (consistent with the existing
  `EXCLUSIONS.md` "no silent caps" philosophy).
- **No reset/restore on the shared CHR.** `/system reset-configuration` wipes the
  `api` service and the ether2 `dhcp-client` that the fixed `127.0.0.1:8728`
  hostfwd depends on, which would sever the management plane for every later
  shared scenario. `run-after-reset` workarounds are exactly the obtuse,
  order-coupling machinery we want to avoid. The lifecycle moves to a dedicated
  throwaway CHR instead.
- **`shutdown`** is folded as the final act of the dedicated `lifecycle`
  scenario (when the VM is disposable anyway), not given its own scenario.

## Architecture: two tiers

### Tier 1 — Shared CHR (no new VM boots)

Under `shared_state: true` the `default` scenario already owns
create/prepare/destroy of one CHR; additional scenarios that reach it over
`127.0.0.1:8728` are nearly free. All Tier-1 work runs here.

**T1.1 Fill missing read-back assertions** (edits to existing verifies):
- `configure_singletons/verify.yml`: assert `/ip/settings` `tcp-syncookies` and
  `/ip/dns` `allow-remote-requests` (both applied today, never asserted).
- `configure_lists`: assert the `/ip/dns/static` record (applied, never asserted).
- `export_vars/verify.yml`: assert the `/system/identity` capture (the second
  requested path) in addition to `/ip/address`.
- `certificate/verify.yml`: assert `mol-host`'s issuer/`ca` is `mol-ca`
  (trust-chain), not merely "has a non-empty fingerprint".

**T1.2 New `configure_check_mode` scenario** (shared CHR): apply a brand-new,
otherwise-unused path with `check_mode: true`; assert the module reports
`changed: true`; `api_info` read-back proves the entry was **not** created; then
real-apply and confirm it now exists. Ansible-native task-level `check_mode`.
Uses a unique path/port not touched by other scenarios so the "does not exist"
assertion holds.

**T1.3 New `negative` scenario** (shared CHR, `block`/`rescue`; drops
`idempotence` from its `test_sequence`): assert roles fail *as designed* —
- `command` malformed item (two op keys) → fails with the `_cmd_bad` message;
- `user_password` missing user → fails with the missing-users message;
- `configure`/`_reconcile` `order: true` + `purge: false` → fails with the
  order-requires-purge assert;
- `ping` an unreachable address → role completes, assert `received == 0`.

All safe: each fails at validation *before* any device mutation, or is read-only.

**T1.4 Exercise untested role branches** (edits to existing scenarios):
- `fetch`: add `routeros_fetch_remove` for the fetched file → assert it is gone
  (`api_info path: file`).
- `command`: add an `/ip/firewall/address-list` entry via the `add` op (returns
  real `changed=True`), verify it, then `remove` it, verify gone — covering
  `add`/`remove` beyond the `cmd` happy path.

**T1.5 Realism additions to `configure_full`**:
- Add `/ip/route` (a `blackhole` static route — always valid on a bare CHR) and
  `/system/ntp/client`.
- Broaden `configure_full/verify.yml` read-back from ~5 paths to a representative
  set across pattern classes (e.g. nat, firewall address-list, queue,
  bridge-vlan, wireguard peer). Update `EXCLUSIONS.md` counts accordingly.

**T1.6 Honesty fix**: add code comments where the `idempotence` step is vacuous
for `cmd`-based roles (`command`/`fetch`/`user_password`), so readers don't
mistake it for real idempotence coverage; the real proof there is the verify
read-back.

**T1.7 Doc/stale fixes**: update README "Scenarios" table and Makefile
`MOLECULE_SCENARIOS` to the real + new scenario set; add the new scenarios to the
Makefile shared-pass ordering.

### Tier 2 — Dedicated opt-out `lifecycle` CHR (1 new boot)

Runs as its **own** `molecule test -s lifecycle` invocation (like `chr`), *after*
the shared pass tears its CHR down — so it can reuse the same `8728/2223` hostfwd
with no port conflict. Opts out of `shared_state` and owns its
create/prepare/destroy (modelled on `chr/`, but with the apinet hostfwd inventory
+ a `utils`-style prepare so the API is reachable).

**T2.1 `lifecycle` scenario** — the meaningful destructive end-to-end on a
throwaway VM, realizing the create→configure→backup→reset→restore vision safely:
1. **configure** a distinctive known state (identity + pool + firewall rule +
   address) via the `configure` role;
2. **backup** (binary `/system backup save` + text `/export`);
3. **mutate** (change identity, add a marker entry);
4. **restore** the binary backup (`/system backup load` → real reboot →
   reconnect) → **verify** the mutation reverted (identity back to the
   backed-up value, marker gone) — proves the backup/restore round-trip across a
   real reboot;
5. **reset** with `routeros_reset_confirm: true` + `routeros_reset_run_after_reset`
   re-enabling API reachability (staged `.rsc`) → **verify** config wiped
   (identity default, pool gone) — exercises the *real* wipe + reconnect;
6. also cover `restore`'s **`/import`** branch and a **wrong-password** negative
   within the same boot;
7. optionally `routeros_shutdown: true` as the final act before destroy.

The reset + `run-after-reset` reconnect is the one empirically-risky piece;
per the validation plan it is run and confirmed, with a documented fallback to a
simpler reset assertion if `run-after-reset` proves flaky.

## Verification / validation

- Each affected scenario is run via `make molecule SCENARIO=<name>` against a live
  CHR as it is implemented (evidence-backed, per the chosen validation mode).
- The `lifecycle` scenario is the primary risk and is validated end-to-end before
  the work is called done.
- `extensions/molecule/README.md` is updated to explain the two-tier architecture
  (shared CHR vs dedicated opt-out CHRs), the scenario catalogue (including
  `configure_check_mode`, `negative`, `lifecycle`), how to run them, and the
  boot budget (shared + `chr` + `lifecycle` = 3 boots).

## Boot budget

shared (1) + existing `chr` (1) + new `lifecycle` (1) = **3 CHR boots** for the
full suite.

## Risks

- **`run-after-reset` reconnect determinism** (T2.1 step 5) — mitigated by
  running the scenario during implementation; documented fallback.
- **Port reuse across opt-out scenarios** — avoided because opt-out scenarios run
  as separate sequential `molecule test` invocations, never concurrently with the
  shared pass.
- **`configure_check_mode` path collision** — avoided by choosing a path/port not
  used by any other scenario.
