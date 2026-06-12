ping
====

Connectivity checks via `/tool ping` over the binary API — run them from the
device to validate reachability before or after a change.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.

Role Variables
--------------

The connection is supplied through the shared `routeros_api_*` variables (define
them once in `group_vars`); `routeros_api_password` has no default — supply it
via Ansible Vault. The role runs from the controller (`delegate_to: localhost`) — no SSH
or Python is needed on the device; see the
[getting-started guide](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/docsite/guide.html) for a minimal inventory.

| Variable | Required | Default | Choices | Comments |
|-------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_ping` | no | `[]` | | Targets to ping (see item keys below). |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Each `routeros_ping` item:

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `address` | yes | | Address/host to ping. |
| `count` | no | `4` | Number of echo requests. |
| `interface` | no | | Source interface. |

Read-only and idempotent (a ping changes no state; the task reports `ok`).
Results are registered as `_routeros_ping` — a looped result, so `.results` is a
list aligned with `routeros_ping`, and each entry's `.msg` is the list of
per-packet rows whose **last** row carries the running totals, e.g.
`(_routeros_ping.results[0].msg | last).received`.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.ping
          vars:
            routeros_ping:
              - address: "1.1.1.1"
                count: 3
              - address: "10.0.0.1"
                count: 5
                interface: ether1

      tasks:
        - name: Fail if the uplink is down
          ansible.builtin.assert:
            that:
              - (_routeros_ping.results[0].msg | last).received | int > 0

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
