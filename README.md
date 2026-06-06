# David_igou Routeros_configuration Collection

This repository contains the `david_igou.routeros_configuration` Ansible Collection.

<!--start requires_ansible-->
This collection requires **ansible-core >= 2.15.0** (see `meta/runtime.yml`).
<!--end requires_ansible-->

## External requirements

Most roles in this collection manage RouterOS over the **binary API** — the
declarative `configure`/`_reconcile` engine via `community.routeros.api_modify`,
`export_vars` via `api_info`, and the operational roles via the generic
`community.routeros.api` module. This requires:

- The **`librouteros`** Python library on the Ansible controller
  (`pip install librouteros`).
- The device's **`api`** service enabled (port 8728), or **`api-ssl`** (port
  8729) for TLS — strongly preferred in production.

The exception is the `backup` role, which runs over **`network_cli`** (SSH) via
`community.routeros.command`, because RouterOS `/export` is console-only; it
needs SSH access to the device rather than the API service.

Connection details for the API roles are supplied once through the shared
`routeros_api_*` variables (see the internal `_reconcile` role). Other modules
and plugins may require additional external libraries — check each module's
documentation.

## Included content

<!--start collection content-->
<!--end collection content-->

## Roles

| Role | Purpose |
| --- | --- |
| `configure` | Declaratively manage RouterOS from one `routeros_config` data structure (the public entrypoint). |
| `export_vars` | Capture a running device's config into a re-appliable `routeros_config` vars file. |
| `backup` | Back up RouterOS configuration — text `/export` over network_cli, plus an optional binary backup. |
| `restore` | Restore a device from a binary backup or a config import. |
| `certificate` | Create, sign, export, and import RouterOS certificates (and ACME requests) over the API. |
| `upgrade` | Set the update channel and install RouterOS package/firmware upgrades over the API. |
| `user_password` | Set or rotate RouterOS `/user` passwords over the API. |
| `command` | Run arbitrary RouterOS API commands — an escape hatch for unmodeled operations. |
| `fetch` | Transfer files to/from the device via `/tool fetch`. |
| `ping` | Run connectivity checks via `/tool ping` over the API. |
| `poe` | Power-cycle, force off/on, or monitor PoE-out ports (imperative; persistent PoE config stays in `configure`). |
| `reboot` | Reboot or shut down a RouterOS device. |
| `reset` | Reset RouterOS configuration (gated; destructive). |
| `_reconcile` | Internal engine — reconciles a single path via `community.routeros.api_modify`. Not called directly. |

Set `routeros_config` — a dict keyed by RouterOS **slash path** — and run the
`configure` role. State is reconciled idempotently in a **canonical dependency
order** (so `/ip/pool` precedes the `/ip/dhcp-server` that references it, a bridge
precedes its ports, etc.), regardless of how you author or merge the dict. Any
path supported by `community.routeros.api_modify` is usable — there is no
per-path role.

```yaml
routeros_config:
  /ip/pool:
    data:
      - name: lan
        ranges: "192.168.88.10-192.168.88.254"
  /ip/firewall/filter:
    purge: true          # exact-state for this path
    order: true          # enforce rule order (requires purge)
    content: remove_as_much_as_possible   # required to purge a keyless path
    data:
      - chain: input
        action: accept
        comment: est
        connection-state: "established,related"
      - chain: input
        action: accept
        comment: mgmt
        protocol: tcp
        dst-port: "22,8728"
      - chain: input
        action: drop
        comment: drop-rest
```

Each path value takes `data` (required), and optional `purge` (exact-state),
`order` (enforce entry order; requires purge), and `content`. Connection comes
from the shared `routeros_api_*` variables. Defaults are **additive**. See
`roles/configure/README.md` for the schema, the ordering model, and how keyed vs
keyless (firewall) updates are matched.

## Using this collection

```bash
    ansible-galaxy collection install david_igou.routeros_configuration
```

You can also include it in a `requirements.yml` file and install it via
`ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
  - name: david_igou.routeros_configuration
```

To upgrade the collection to the latest available version, run the following
command:

```bash
ansible-galaxy collection install david_igou.routeros_configuration --upgrade
```

You can also install a specific version of the collection, for example, if you
need to downgrade when something is broken in the latest version (please report
an issue in this repository). Use the following syntax where `X.Y.Z` can be any
[available version](https://galaxy.ansible.com/david_igou/routeros_configuration):

```bash
ansible-galaxy collection install david_igou.routeros_configuration:==X.Y.Z
```

See
[Ansible Using Collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)
for more details.

## Release notes

See the
[changelog](https://github.com/david-igou/ansible-collection-routeros_configuration/tree/main/CHANGELOG.rst).

## Roadmap

This collection is in early **0.0.x** development — expect breaking changes
between releases until **1.0.0**. Near-term focus is stabilizing the `configure`
`routeros_config` data contract and broadening role coverage. Pin a specific
version in your `requirements.yml` and review the
[changelog](https://github.com/david-igou/ansible-collection-routeros_configuration/tree/main/CHANGELOG.rst)
before upgrading.

## More information

- [Collection documentation](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/)
- [MikroTik RouterOS documentation](https://help.mikrotik.com/docs/)
- [`community.routeros` collection](https://galaxy.ansible.com/ui/repo/published/community/routeros/)
- [Ansible collection development forum](https://forum.ansible.com/c/project/collection-development/27)
- [Ansible User guide](https://docs.ansible.com/ansible/devel/user_guide/index.html)
- [Ansible Developer guide](https://docs.ansible.com/ansible/devel/dev_guide/index.html)
- [Ansible Collections Checklist](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html)
- [Ansible Community code of conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html)
- [The Bullhorn (the Ansible Contributor newsletter)](https://docs.ansible.com/ansible/devel/community/communication.html#the-bullhorn)
- [News for Maintainers](https://forum.ansible.com/tag/news-for-maintainers)

## Licensing

GNU General Public License v3.0 or later.

See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.
