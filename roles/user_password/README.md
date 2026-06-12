user_password
=============

Set or rotate `/user` account passwords over the binary API — the write-only
field the `configure` role can't manage (RouterOS never returns a password, so it
cannot be reconciled declaratively).

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.
- The target users **must already exist** (create them with `configure` / `/user`).

Role Variables
--------------

The connection is supplied through the shared `routeros_api_*` variables (define
them once in `group_vars`); `routeros_api_password` has no default — supply it
via Ansible Vault. The role runs from the controller (`delegate_to: localhost`) — no SSH
or Python is needed on the device; see the
[getting-started guide](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/docsite/guide.html) for a minimal inventory.

| Variable | Required | Default | Choices | Comments |
|-------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_user_passwords` | no | `[]` | | Users and the passwords to set (see item keys below; the password-setting task is `no_log`). |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Each `routeros_user_passwords` item:

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `name` | yes | | An **existing** user name. |
| `password` | yes | | The new password (quoted before sending; supply via Vault). |

The role reads the users first and **fails** if any requested `name` does not
exist, rather than silently skipping it. **Not idempotent** — RouterOS never
returns passwords, so it sets them every run (reported as `ok`). If you rotate
the account the role authenticates as, update `routeros_api_password` for later
plays.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.user_password
          vars:
            routeros_user_passwords:
              - name: admin
                password: "{{ vault_admin_password }}"
              - name: monitoring
                password: "{{ vault_monitoring_password }}"

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
