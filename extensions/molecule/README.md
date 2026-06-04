# Molecule scenarios

Each scenario lives in its own subdirectory. Invoke from the **collection root**:

```bash
# Shared pass: boot ONE CHR and run every subsystem-role scenario against it,
# then the standalone chr scenario:
make molecule

# A single scenario (boots/uses one CHR for just that scenario):
make molecule SCENARIO=ip_dns

# Or directly (after `make install`), from the collection root:
MOLECULE_GLOB="extensions/molecule/*/molecule.yml" \
  molecule test --all --exclude chr --exclude integration_hello_world
```

## Shared state — one CHR for the whole suite

`extensions/molecule/config.yml` sets `shared_state: true`, and a dedicated
`default` scenario owns the instance lifecycle: under shared state molecule runs
the `default` scenario's **create + prepare + destroy exactly once** for the
entire run, and every subsystem-role scenario reuses that single CHR. Those role
scenarios therefore declare a trimmed `test_sequence` of just
`dependency → converge → idempotence → verify` — they reach the shared device
over the fixed `127.0.0.1:8728` API hostfwd (their api tasks `delegate_to:
localhost`, so no SSH to the device is needed). This replaces ~40 per-scenario
CHR boots with one.

Because all scenarios mutate the same device sequentially, each binds **dedicated
ports** where it would otherwise conflict (bonding on ether5/6, bridge ports on
ether7/8, dhcp-client/relay/vrf on ether9/10/11), while additive L3 config stacks
on ether3/4 — see `utils/inventory/hosts.yml` (11 ethers).

The `chr` scenario opts out (`shared_state: false`): it verifies over
`network_cli` (SSH CLI), which needs its own runtime inventory, so run it
standalone with `make molecule SCENARIO=chr`.

`MOLECULE_GLOB` overrides molecule's default `molecule/<scenario>/` layout to
point at this collection's `extensions/molecule/<scenario>/` layout. Running
from the collection root also lets molecule auto-discover
`extensions/molecule/config.yml` (which only fires from the collection root, not
a scenario subdir).

## Deterministic collection resolution

- **Test-only** provisioner backends come from
  [`david_igou.molecule_provisioners`](https://galaxy.ansible.com/ui/repo/published/david_igou/molecule_provisioners/),
  pinned in `extensions/molecule/requirements-test.yml` and installed
  automatically by molecule's `dependency` step (configured in
  `extensions/molecule/config.yml`). It is **not** in the root `requirements.yml`,
  so consumers of this collection never auto-pull test tooling.
- **Runtime** deps (`community.routeros`, `ansible.netcommon`) come from the root
  `requirements.yml` / `galaxy.yml` and are installed by `make install` (which
  `make molecule` runs first).

No collection needs to be manually pre-installed: `make molecule SCENARIO=chr`
resolves everything.

## Scenarios

All scenarios drive the single `configure` role with a `routeros_config` dict;
they run on **one shared CHR** (see "Shared state" below).

| Scenario | Backend | What it proves |
| --- | --- | --- |
| `chr` | qemu | A MikroTik CHR VM boots via the qemu provider and RouterOS is reachable over `community.routeros` (network_cli). Opts out of shared state. |
| `configure_lists` | qemu | Keyed-path apply (e.g. `/ip/pool` by `name`), in-place **update** of a non-key field (matched by key), and `purge`. |
| `configure_singletons` | qemu | Singleton paths (`/system/identity`, `/ip/dns`, `/ip/settings`). |
| `configure_ordered` | qemu | Keyless ordered firewall with `purge`+`order`; in-place **update** of a rule matched by `comment` (no duplicate). |
| `configure_modify_only` | qemu | `fixed_entries` paths — disables the built-in `telnet` service. |
| `configure_dependency_chain` | qemu | Cross-path **ordering**: `bridge→port`, `pool→dhcp-server→lease`, `list→member` authored in shuffled key order, applied correctly + idempotently. |
| `configure_full` | qemu | Comprehensive — applies 74 of the CHR-configurable `api_modify` paths in one shuffled call; converge proves ordering, idempotence proves clean reconciliation. See `configure_full/EXCLUSIONS.md`. |

Provisioner wiring, `test_sequence`, and `verifier` are centralised in
`extensions/molecule/config.yml`, so each scenario's `molecule.yml` is just its
name; the per-scenario `converge.yml` / `verify.yml` stay in the scenario dir.
The binary API (port 8728) is reached over a dedicated SLIRP `hostfwd`; the
shared host provides 11 ether NICs (ether1 SSH, ether2 API, ether3–11 spare) so
the port-binding scenarios (bridge ports on ether7/8, bonding on ether5/6,
dhcp-client/relay on ether9/10) coexist on one device — see
`utils/inventory/hosts.yml`.
