reboot
======

Reboot a RouterOS device (and wait for the API to actually answer again) or,
gated, shut it down — over the binary API.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.

Role Variables
--------------

Set the role behaviour below; the connection is supplied through the shared
`routeros_api_*` variables (define them once in `group_vars`).
`routeros_api_password` has no default — supply it via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|--------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_reboot` | no | `true` | true, false | Reboot the device and wait for the API to return. |
| `routeros_shutdown` | no | `false` | true, false | Shut the device down instead (takes precedence; no reconnect wait — it powers off). |
| `routeros_reboot_timeout` | no | `300` | | Seconds to wait for the API after the reboot. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

After issuing the reboot the role waits for the API port to open (TLS-aware:
8729 when `routeros_api_tls`, else 8728), then retries a `system identity` call
until login succeeds — the port opens a few seconds before logins are accepted.
A reboot/shutdown is an action, not a desired state, so the role is not
idempotent (it reports `changed` whenever it runs).

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        # Reboot and block until the API is reachable again (the default).
        - role: david_igou.routeros_configuration.reboot

        # Shut the device down instead.
        - role: david_igou.routeros_configuration.reboot
          vars:
            routeros_reboot: false
            routeros_shutdown: true

License
-------

GPL-2.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
