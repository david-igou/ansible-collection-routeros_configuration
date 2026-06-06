# poe

Imperative PoE-out operations on a RouterOS device over the binary API:
power-cycle a port, force `poe-out` off/on, or read live `monitor` status.

This is the operational counterpart to the `configure` role — **not** a
replacement. Persistent PoE configuration (the ping watchdog
`power-cycle-ping-*`, periodic `power-cycle-interval`, `poe-priority`,
`poe-voltage`, `poe-lldp-enabled`, and the global `/interface ethernet poe
settings` power budget) is desired-state and belongs in `configure` via
`api_modify`. This role performs the one-shot actions that have no state to
reconcile.

## Actions (`routeros_poe_action`)

| Action | Effect |
| --- | --- |
| `monitor` (default) | Read-only live status (`poe-out-status`, voltage, current, power). Empty `routeros_poe_interfaces` reads all PoE-out ports. Results in the `routeros_poe_monitor` fact. |
| `power_cycle` | Drop power to the target ports for `routeros_poe_duration` (0..1m), then restore — power-cycles the attached devices. |
| `power_off` | Set `poe-out=off` on the target ports (cut power; reversible via `power_on`). |
| `power_on` | Restore `poe-out` to `routeros_poe_mode` (`auto-on` by default). |

Write actions (`power_cycle`/`power_off`/`power_on`) require a non-empty
`routeros_poe_interfaces`; a named interface with no PoE-out entry fails clearly.

## Variables

See `meta/argument_specs.yml` for the full list (and three worked examples in the
rendered role reference). Key variables: `routeros_poe_action`,
`routeros_poe_interfaces`, `routeros_poe_duration`, `routeros_poe_mode`, plus the
shared `routeros_api_*` connection variables.

## Per-host (PoE-port-as-hostvar) model

Target the powered hosts and point the connection at each host's switch — the
host loop is the fan-out:

```yaml
- hosts: poe_powered_devices          # each has poe_switch + poe_port hostvars
  gather_facts: false
  tasks:
    - name: Power-cycle this host's port on its switch
      ansible.builtin.include_role:
        name: david_igou.routeros_configuration.poe
      vars:
        routeros_api_hostname: "{{ poe_switch }}"
        routeros_api_password: "{{ hostvars[poe_switch].routeros_api_password }}"
        routeros_poe_action: power_cycle
        routeros_poe_interfaces:
          - "{{ poe_port }}"
```

## Note on hardware / testing

PoE-out is hardware-specific. The CHR used in CI has no PoE controller, so the
live actions are validated on real hardware; CI covers the input-validation and
no-entry paths.
