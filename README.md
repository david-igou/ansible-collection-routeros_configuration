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

Each subsystem role declaratively manages one RouterOS config path. Set its
`routeros_<path>` variable (a list of desired entries) and run the role; state
is reconciled idempotently via `community.routeros.api_modify`.

| Role | Manages | Notes |
| --- | --- | --- |
| `system_identity` | `/system/identity` | Device name (singleton). |
| `ip_address` | `/ip/address` | IPv4 addresses. `routeros_ip_address_purge` for exact-state. |
| `ip_firewall_filter` | `/ip/firewall/filter` | Ordered rules; `_purge`/`_order`/`_content` toggles. |

All roles share one connection contract through the `routeros_api_*` variables
(hostname, username, password, tls, validate_certs, port) and delegate
reconciliation to the internal `_reconcile` engine role. Roles default to
**additive** behavior (declared entries are added/updated, others untouched);
opt into exact-state deletion per role with the `*_purge` toggle.

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
