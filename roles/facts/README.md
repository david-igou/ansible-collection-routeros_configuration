facts
=====

Gather RouterOS device facts over the binary API
(`community.routeros.api_facts`), setting `ansible_net_*` facts for reporting,
drift detection, conditionals, and pre-flight checks.

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
|-------------------------------|----------|------------------------|------------------------------------|------------------------------------------------------------|
| `routeros_facts_subset` | no | `[all]` | all, hardware, interfaces, routing | Fact subsets to gather (`gather_subset`). Prefix a value with `!` to exclude it. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

Read-only and idempotent. Sets standard network facts including
`ansible_net_version`, `ansible_net_hostname`, `ansible_net_model`,
`ansible_net_serialnum`, and `ansible_net_interfaces` (the exact set depends on
`routeros_facts_subset` and the device).

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.facts
          vars:
            routeros_facts_subset:
              - hardware
              - interfaces

    - name: Show the gathered version
      ansible.builtin.debug:
        var: ansible_net_version

License
-------

GPL-2.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
