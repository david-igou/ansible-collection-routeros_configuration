command
=======

Run a list of arbitrary RouterOS API operations — an escape hatch for one-off
actions not covered by the other roles (run a script, make a DHCP lease static,
log out a HotSpot user, toggle a service, …). Uses `community.routeros.api` over
the binary API. Reach for a dedicated role first (`configure` for declarative
state, `certificate`, `upgrade`, …); use `command` only when nothing else fits.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.

Role Variables
--------------

The connection is supplied through the shared `routeros_api_*` variables (define
them once in `group_vars`); `routeros_api_password` has no default — supply it
via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|-------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_command` | no | `[]` | | List of operations to run (see item keys below). |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Each `routeros_command` item has a `path` and **exactly one** operation key
(the role validates this and fails on a typo'd or ambiguous key):

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `path` | yes | | API path / menu, e.g. `system script`, `ip firewall filter`. |
| `cmd` | one-of | | An arbitrary command within the path, e.g. `run .id=*1`. |
| `add` | one-of | | `key=value …` arguments to add an entry. |
| `remove` | one-of | | The `.id` of an entry to remove. |
| `update` | one-of | | `.id=… key=value …` arguments to update an entry. |
| `no_log` | no | `false` | Hide this item from logs (set when it carries a secret). |

**Not idempotent.** `add`/`remove`/`update` report `changed` from the module; an
arbitrary `cmd` reports `ok` (the API can't tell whether a free-form command
changed anything). For idempotent, drift-correcting state, use `configure`.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.command
          vars:
            routeros_command:
              - path: "system script"
                cmd: "run .id=*1"
              - path: "ip dhcp-server lease"
                cmd: "make-static .id=*2"
              - path: "ip firewall address-list"
                add: "list=blocked address=203.0.113.5"
              - path: "ip firewall address-list"
                remove: "*7"
              # Carries a secret — hide it from logs:
              - path: "ppp secret"
                add: "name=vpn password=s3cret"
                no_log: true

License
-------

GPL-2.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
