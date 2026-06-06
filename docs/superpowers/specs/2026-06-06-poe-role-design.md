# `poe` role — design

Date: 2026-06-06

An **imperative** role for ad-hoc PoE-out operations that have no clean
steady-state to reconcile — the operational counterpart to `configure`. Built
from a full read of the MikroTik PoE-Out manual
(<https://manual.mikrotik.com/docs/hardware/poe-out.md>,
<https://help.mikrotik.com/docs/spaces/ROS/pages/19136769/PoE-Out>).

It does **not** replace `configure`. Persistent PoE knobs stay in `configure`
via `api_modify`; this role only performs the imperative/operational actions
`api_modify` can't express idempotently.

Like the other operational roles, it runs over the binary API
(`community.routeros.api` / `api_find_and_modify`), reuses the shared
`routeros_api_*` connection contract via a `module_defaults` block, and
`delegate_to: localhost`, `connection: local`.

## Imperative vs. stateful — the boundary

The PoE-Out menu splits cleanly into "do something now" vs "desired steady
state". This role owns the former; `configure` owns the latter.

**In scope (this role — imperative):**

- `power_cycle` — `/interface ethernet poe power-cycle <iface> duration=<dur>`.
  A *command* (not a settable property in ROS7) that drops power to the port for
  a duration, then restores it. No state to reconcile — the headline
  "power-cycle a host" feature.
- `power_off` / `power_on` — `set <iface> poe-out=off | auto-on | forced-on |
  forced-on-a | forced-on-bt`. `poe-out` *is* a reconcilable property (so
  `configure` owns steady state), but "shut this PD down now / power it back up"
  is a legitimate one-shot action. (Action names are `power_off`/`power_on`, not
  bare `off`/`on`, because YAML parses bare `on`/`off` as booleans — a footgun in
  `routeros_poe_action: on`.)
- `monitor` — `/interface ethernet poe monitor <iface> once`. Read-only live
  telemetry: `poe-out-status` (`powered-on`, `waiting-for-load`,
  `short-circuit`, `overload`, `voltage-too-low/high`, `current-too-low`,
  `voltage_on_poe-in`, `power_reset`, `controller_*`), `poe-out-voltage`,
  `poe-out-current`, `poe-out-power`, `poe-out-power-pair`. No config equivalent.

**Out of scope (stays in `configure`):**

- The ping watchdog: `power-cycle-ping-enabled` / `power-cycle-ping-address` /
  `power-cycle-ping-timeout`.
- Periodic `power-cycle-interval`.
- `poe-priority`, `poe-voltage`, `poe-lldp-enabled`.
- The global `/interface ethernet poe settings` budget
  (`poe-out-limit-power`, `routerboard-max-self-power`, `psuX-*`).

These are persistent desired-state knobs `api_modify` reconciles cleanly.

## Variable interface — single action + targets

Mirrors the `reboot` role's shape (one action per include; the play's host loop
is the fan-out). Chosen to fit the "PoE port is a hostvar on the powered host"
inventory model (see below).

```yaml
# Shared connection block — identical to reboot/command.
routeros_api_hostname: "{{ inventory_hostname }}"
routeros_api_username: admin
# routeros_api_password: "{{ vault_routeros_api_password }}"
routeros_api_tls: true
routeros_api_validate_certs: true
routeros_api_port: ""

# The PoE action to perform.
routeros_poe_action: monitor          # monitor | power_cycle | power_off | power_on
# Target PoE-out interfaces. Write actions REQUIRE a non-empty list (empty =
# hard fail). monitor with an empty list reads all PoE-out ports.
routeros_poe_interfaces: []
# power_cycle only: how long to drop power (RouterOS duration, 0..1m).
routeros_poe_duration: 5s
# action=power_on only: the poe-out value to restore.
routeros_poe_mode: auto-on            # auto-on | forced-on | forced-on-a | forced-on-bt
```

Default is `monitor` of all ports — a bare `include_role` with no vars is
read-only and harmless.

## Behaviour per action

| Action | Mechanism | `changed` |
| --- | --- | --- |
| `monitor` | resolve each iface → `.id`, then `community.routeros.api` `cmd: "monitor .id=<id> once"`; collect into a registered fact + `debug` | `false` |
| `power_cycle` | resolve `.id`, `cmd: "power-cycle .id=<id> duration=<dur>"` | `true` |
| `power_off` | `community.routeros.api_find_and_modify` find `{name: <iface>}` set `{poe-out: "off"}`, `require_matches_min: 1` | module-reported |
| `power_on` | `api_find_and_modify` find `{name: <iface>}` set `{poe-out: <routeros_poe_mode>}`, `require_matches_min: 1` | module-reported |

`power_off`/`power_on` set a field, so `api_find_and_modify` (find-by-name) is
cleanest — no manual id juggling, honest `changed`, and `require_matches_min: 1`
fails when the interface has no PoE-out entry. `monitor`/`power_cycle` are keyed-menu
*commands*, so the `api` `cmd` form needs the entry `.id` (the `api` `cmd` takes
`key=value` only — no CLI positionals / `[find]`); a small pre-read maps
interface name → `.id`. Results land under `.msg`.

User-supplied values interpolated into `cmd` strings are quoted with
`community.routeros.quote_argument_value`, consistent with the other operational
roles.

## Targeting & the per-host hostvar model

Targets are interface names. The connection always goes to whatever
`routeros_api_hostname` resolves to (the role runs `delegate_to: localhost` +
`connection: local` internally and the module reaches the device over TCP by
hostname) — Ansible `delegate_to` to the router is **not** the mechanism and
would not propagate into the role's inner tasks anyway.

The "each powered host carries its own PoE port" model is expressed by targeting
the powered hosts and pointing the connection at each host's switch:

```yaml
- name: Power-cycle each device's PoE port on its switch
  hosts: poe_powered_devices          # each has poe_switch + poe_port hostvars
  gather_facts: false
  tasks:
    - name: Cycle this host's port
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.poe
      vars:
        routeros_api_hostname: "{{ poe_switch }}"
        routeros_api_password: "{{ hostvars[poe_switch].routeros_api_password }}"
        routeros_poe_action: power_cycle
        routeros_poe_interfaces:
          - "{{ poe_port }}"
```

The host loop is the fan-out — each invocation connects to *its* switch and
cycles *its* port. (Router creds come from `hostvars[poe_switch]` or a shared
group_var.) The router-centric model — `hosts: routers`, many interfaces in one
`routeros_poe_interfaces` list — also works.

## Safety / validation (baked in; no extra gate)

Per the user's choice, selecting the action **is** the opt-in (`power_off` is
reversible via `power_on`, so it is not gated like `reset`/`shutdown`). Guards:

- Write actions (`power_off`/`power_on`/`power_cycle`) **hard-fail on an empty
  `routeros_poe_interfaces`** — never act on every port by accident.
- `routeros_poe_action` ∈ {`monitor`, `power_cycle`, `power_off`, `power_on`}
  (argument-spec `choices`).
- `routeros_poe_mode` ∈ {`auto-on`, `forced-on`, `forced-on-a`, `forced-on-bt`}
  (argument-spec `choices`).
- `routeros_poe_duration` validated as a RouterOS duration ≤ 1m.
- A named interface with no PoE-out entry on the device fails clearly
  (`no PoE-out entry for <iface>`) rather than silently no-op'ing.

## Testing — honest, given CHR has no PoE hardware

CHR is an x86 VM with no PoE controller, so the live PoE ops cannot be exercised
in CI. Approach (consistent with the collection's existing "untested-on-CHR"
precedent — shutdown, ACME, RouterBOARD firmware, real reset):

- **Fully tested on CHR (hardware-independent):** input validation — empty
  `routeros_poe_interfaces` guard, invalid action, invalid mode, invalid
  duration; and the "interface has no PoE entry" path (CHR's
  `/interface ethernet poe` is empty or absent → clean failure / empty
  `monitor`). This is the molecule `poe` scenario's core.
- **Untested-on-CHR (no PoE hardware), validated later on a real device:** the
  actual `power_cycle` / `power_off` / `power_on` / live `monitor` readings,
  documented as such (no silent caps).
- The scenario drops idempotence (imperative role, like `command`).
- First confirm what CHR's `/interface ethernet poe` actually returns and shape
  the validation assertions to match.

## Files

New:

- `roles/poe/defaults/main.yml`
- `roles/poe/meta/argument_specs.yml` (with three worked examples, per the
  collection's docsite convention)
- `roles/poe/meta/main.yml`
- `roles/poe/tasks/main.yml`
- `roles/poe/README.md`
- `extensions/molecule/poe/{molecule.yml, converge.yml, verify.yml}`
- `changelogs/fragments/poe-role.yml`

Edit:

- `README.md` — add a `poe` row to the Roles table.

## Out of scope / deferred

- Live-hardware molecule coverage (validated manually on a real PoE device).
- Any `/interface ethernet poe settings` budget management or watchdog config —
  belongs to `configure`.
