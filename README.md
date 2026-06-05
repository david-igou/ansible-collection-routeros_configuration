# David_igou Routeros_configuration Collection

This repository contains the `david_igou.routeros_configuration` Ansible Collection.

<!--start requires_ansible-->
<!--end requires_ansible-->

## External requirements

The roles in this collection manage RouterOS declaratively over the **binary
API** via `community.routeros.api_modify`/`api_info`. This requires:

- The **`librouteros`** Python library on the Ansible controller
  (`pip install librouteros`).
- The device's **`api`** service enabled (port 8728), or **`api-ssl`** (port
  8729) for TLS — strongly preferred in production.

Connection details are supplied once through the shared `routeros_api_*`
variables (see the internal `_reconcile` role). Other modules and plugins may
require additional external libraries — check each module's documentation.

## Included content

<!--start collection content-->
<!--end collection content-->

## Roles

| Role | Purpose |
| --- | --- |
| `configure` | Declaratively manage RouterOS from one `routeros_config` data structure (the public entrypoint). |
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
[changelog](https://github.com/ansible-collections/david_igou.routeros_configuration/tree/main/CHANGELOG.rst).

## Roadmap

<!-- Optional. Include the roadmap for this collection, and the proposed release/versioning strategy so users can anticipate the upgrade/update cycle. -->

## More information

<!-- List out where the user can find additional information, such as working group meeting times, slack/matrix channels, or documentation for the product this collection automates. At a minimum, link to: -->

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
