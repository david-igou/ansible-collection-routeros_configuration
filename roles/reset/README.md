reset
=====

Reset a RouterOS device's configuration to defaults via
`/system reset-configuration`, over the binary API. **Destructive** — it wipes
the configuration and reboots, and is gated behind an explicit confirm variable
so it does nothing unless you opt in.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.

Role Variables
--------------

Set the reset behaviour below; the connection is supplied through the shared
`routeros_api_*` variables (define them once in `group_vars`).
`routeros_api_password` has no default — supply it via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|------------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_reset_confirm` | no | `false` | true, false | **Must be `true` to actually reset.** Safety gate. |
| `routeros_reset_keep_users` | no | `true` | true, false | Keep users/passwords across the reset (`keep-users=yes`). |
| `routeros_reset_no_defaults` | no | `false` | true, false | Skip the default configuration after reset (`no-defaults=yes`). |
| `routeros_reset_run_after_reset` | no | `""` | | Script to run after the reset (e.g. re-enable the API). Empty = none. |
| `routeros_reset_reboot_timeout` | no | `300` | | Seconds to wait for the API after the reset reboot. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

With the gate off the role is a no-op (this is the path exercised in CI; the
actual wipe is not). A reset that drops the API service or your credentials
leaves the device unmanageable — use `routeros_reset_keep_users: true` and/or
`routeros_reset_run_after_reset` to keep it reachable. After the reset reboots,
the role waits for the API port (TLS-aware) and retries `system identity` until
login succeeds. `routeros_reset_run_after_reset` is quoted before being sent, so
a multi-word script string survives intact.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.reset
          vars:
            routeros_reset_confirm: true                       # REQUIRED to act
            routeros_reset_keep_users: true
            routeros_reset_run_after_reset: "/ip service enable api"

License
-------

GPL-2.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
