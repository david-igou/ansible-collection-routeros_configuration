upgrade
=======

Manage a RouterOS device's package update channel and, optionally, install an
available package update or RouterBOARD firmware — over the binary API.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.
- Outbound internet from the device for `check-for-updates` / `install`.

Role Variables
--------------

Set the upgrade behaviour below; the connection is supplied through the shared
`routeros_api_*` variables (define them once in `group_vars`).
`routeros_api_password` has no default — supply it via Ansible Vault. The role runs from the controller (`delegate_to: localhost`) — no SSH
or Python is needed on the device; see the
[getting-started guide](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/docsite/guide.html) for a minimal inventory.

| Variable | Required | Default | Choices | Comments |
|---------------------------------|----------|------------------------|------------------------------------------|------------------------------------------------------------|
| `routeros_update_channel` | no | `stable` | stable, testing, long-term, development | RouterOS package update channel. |
| `routeros_upgrade_install` | no | `false` | true, false | Install an available update (**reboots** the device). |
| `routeros_routerboard_upgrade` | no | `false` | true, false | Flash newer RouterBOARD firmware if available (**reboots**). |
| `routeros_upgrade_reboot_timeout` | no | `300` | | Seconds to wait for the API after a reboot. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

**Idempotent on the safe path:** the channel is set only when it differs, and
`check-for-updates` is read-only, so a converged device reports no change. A
failed check (no internet) does not fail the play — the install gate just won't
fire. **Install path:** when `routeros_upgrade_install: true` and an update is
available, the role installs it and waits for the API to return after the reboot
(port open, TLS-aware, then a `system identity` retry until login succeeds);
this is a one-time change. **RouterBOARD firmware** (`routeros_routerboard_upgrade`)
flashes and reboots only when `current-firmware` differs from `upgrade-firmware`,
so an enabled flag is a no-op once up to date (gated; not exercised in CI — a CHR
has no RouterBOARD). To roll back, `/system package downgrade` or restore a
pre-upgrade backup (see the `restore` role).

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        # Safe default: set the channel and check for updates, no install.
        - role: david_igou.routeros_configuration.upgrade
          vars:
            routeros_update_channel: stable

        # Opt in to installing (reboots — use a maintenance window).
        - role: david_igou.routeros_configuration.upgrade
          vars:
            routeros_update_channel: stable
            routeros_upgrade_install: true

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
