fetch
=====

Transfer files to/from a RouterOS device with `/tool fetch` (HTTP/S, FTP, TFTP,
SFTP) and remove files with `/file remove`, over the binary API. Use it to stage
firmware, scripts, or certificates onto the device, or to push backups off-box.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.
- Network reachability from the **device** to the fetch `url` (the transfer runs
  on the router, not the controller).

Role Variables
--------------

The connection is supplied through the shared `routeros_api_*` variables (define
them once in `group_vars`); `routeros_api_password` has no default — supply it
via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|-------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_fetch` | no | `[]` | | Files to transfer (see item keys below). |
| `routeros_fetch_remove` | no | `[]` | | List of file names to delete from the device (`/file remove`). |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Each `routeros_fetch` item:

| Item key | Required | Default | Choices | Comments |
|----------|----------|---------|--------------------------------|------------------------------------------------------------|
| `url` | yes | | | Source URL. |
| `dst_path` | yes | | | Destination file name on the device. |
| `mode` | no | `http` | http, https, ftp, tftp, sftp | Transfer mode. |
| `extra` | no | | | Extra `/tool fetch` args appended verbatim (e.g. `upload=yes`, `user=… password=…`). |
| `no_log` | no | `false` | true, false | Hide this item from logs (set when `url`/`extra` carries credentials). |

A `fetch` overwrites the destination each run and is not idempotent; `remove`
only acts when the named file is present, so it is safe to re-run. `url` and
`dst_path` are quoted before being sent; `extra` is passed verbatim (a
multi-argument escape hatch — quote values within it yourself if needed).

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.fetch
          vars:
            routeros_fetch:
              - url: "https://example.com/extra.npk"
                dst_path: extra.npk
                mode: https
            routeros_fetch_remove:
              - old-backup.backup

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
