restore
=======

Restore a RouterOS device from a binary backup (`/system backup load`) and/or
import a configuration script (`/import`), over the binary API. The reverse of
the `backup` role.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.
- The backup (`.backup`) or script (`.rsc`) file **already present on the
  device** — stage it first with the `fetch` role if needed.

Role Variables
--------------

Set the desired restore inputs below; the connection is supplied through the
shared `routeros_api_*` variables (define them once in `group_vars`).
`routeros_api_password` has no default — supply it via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|------------------------------------|----------|------------------------|---------|------------------------------------------------------------|
| `routeros_restore_backup_name` | no | `""` | | On-device binary backup name (without `.backup`). Empty = skip the backup-load path. |
| `routeros_restore_backup_password` | no | `""` | | Backup decryption password (required by RouterOS even for unencrypted backups; hidden from logs). |
| `routeros_restore_import_file` | no | `""` | | On-device `.rsc` file to import. Empty = skip the import path. |
| `routeros_restore_reboot_timeout` | no | `300` | | Seconds to wait for the API after a backup-load reboot. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

A binary backup load **reboots** the device; the role waits for the API port to
open (TLS-aware) and retries `system identity` until login succeeds. `/import`
does not reboot. Loading a backup over the API requires a non-empty
`routeros_restore_backup_password` — so always save backups encrypted (the
`backup` role's `routeros_backup_password`). The backup name/password are quoted
before being sent, so values with spaces or special characters are handled.
Restoring is an imperative action and is not idempotent.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements. Pair
with the `fetch` role to stage the file and the `backup` role to produce it.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        # Load a binary backup. REBOOTS; the role waits for the device back.
        - role: david_igou.routeros_configuration.restore
          vars:
            routeros_restore_backup_name: pre-change
            routeros_restore_backup_password: "{{ vault_backup_password }}"

        # Or import a config script (no reboot).
        - role: david_igou.routeros_configuration.restore
          vars:
            routeros_restore_import_file: bootstrap.rsc

License
-------

GPL-2.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
