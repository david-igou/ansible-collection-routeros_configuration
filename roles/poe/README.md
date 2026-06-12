poe
===

Imperative PoE-out operations on a RouterOS device — power-cycle a port, force
`poe-out` off/on, or read live `monitor` status — over the binary API.

The operational counterpart to the `configure` role, **not** a replacement.
Persistent PoE configuration (the ping watchdog `power-cycle-ping-*`, periodic
`power-cycle-interval`, `poe-priority`, `poe-voltage`, `poe-lldp-enabled`, and
the global `/interface ethernet poe settings` power budget) is desired state and
belongs in `configure` via `api_modify`. This role performs the one-shot actions
that have no state to reconcile.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.
- PoE-out-capable hardware (e.g. a CRS3xx PoE switch). PoE is hardware-specific;
  a CHR (used in CI) has no PoE controller, so the live actions are validated on
  real hardware while CI covers the input-validation and no-entry paths.

Role Variables
--------------

Set the action and its targets below; the connection is supplied through the
shared `routeros_api_*` variables (define them once in `group_vars`).
`routeros_api_password` has no default — supply it via Ansible Vault. The role runs from the controller (`delegate_to: localhost`) — no SSH
or Python is needed on the device; see the
[getting-started guide](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/docsite/guide.html) for a minimal inventory.

| Variable | Required | Default | Choices | Comments |
|---------------------------------|----------|------------------------|------------------------------------------|------------------------------------------------------------|
| `routeros_poe_action` | no | `monitor` | monitor, power_cycle, power_off, power_on | The PoE-out action (see the actions table below). |
| `routeros_poe_interfaces` | no | `[]` | | Target PoE-out interfaces by ethernet interface name. Required (non-empty) for the write actions; an empty list with `monitor` reads all PoE-out ports. |
| `routeros_poe_duration` | no | `5s` | | `power_cycle` only — how long to drop power, as a RouterOS duration (e.g. `5s`, `30s`, `1m`). The device enforces the 0..1m range. |
| `routeros_poe_mode` | no | `auto-on` | auto-on, forced-on, forced-on-a, forced-on-bt | `power_on` only — the `poe-out` value to restore. `forced-on-a`/`forced-on-bt` require 802.3bt-capable hardware. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Actions (`routeros_poe_action`):

| Action | Effect |
| --- | --- |
| `monitor` (default) | Read-only live status (`poe-out-status`, voltage, current, power); results land in the `routeros_poe_monitor` fact. An empty `routeros_poe_interfaces` reads all PoE-out ports. |
| `power_cycle` | Drop power to the target ports for `routeros_poe_duration`, then restore — power-cycles the attached devices. |
| `power_off` | Set `poe-out=off` on the target ports (cut power; reversible via `power_on`). |
| `power_on` | Restore `poe-out` to `routeros_poe_mode` (`auto-on` by default). |

Write actions (`power_cycle`/`power_off`/`power_on`) require a non-empty
`routeros_poe_interfaces`; a named interface with no PoE-out entry fails clearly.

`routeros_poe_monitor` holds one element per monitored port — each the API
`monitor` output for that port (a single-entry list of fields such as
`poe-out-status`, plus `poe-out-voltage` / `poe-out-current` /
`poe-out-power` while a device is drawing power). E.g. the status of the
first port: `routeros_poe_monitor[0][0]['poe-out-status']`.

`power_off`/`power_on` set the `poe-out` field via `api_find_and_modify`, while
`monitor`/`power_cycle` resolve the entry `.id` and run the keyed-menu command.
The actions are one-shot, so the role is not idempotent (read-only `monitor`
reports no change).

Per-host (PoE-port-as-hostvar) model
------------------------------------

Target the powered hosts and point the connection at each host's switch — the
host loop is the fan-out:

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

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        # Read-only: monitor every PoE-out port (the default action).
        - role: david_igou.routeros_configuration.poe

        # Power-cycle two ports for 10 seconds.
        - role: david_igou.routeros_configuration.poe
          vars:
            routeros_poe_action: power_cycle
            routeros_poe_duration: 10s
            routeros_poe_interfaces:
              - ether5
              - ether6

        # Cut power to a port (reversible with power_on).
        - role: david_igou.routeros_configuration.poe
          vars:
            routeros_poe_action: power_off
            routeros_poe_interfaces:
              - ether5

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
