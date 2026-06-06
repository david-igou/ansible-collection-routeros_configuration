# david_igou.routeros_configuration

![Galaxy Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgalaxy.ansible.com%2Fapi%2Fv3%2Fplugin%2Fansible%2Fcontent%2Fpublished%2Fcollections%2Findex%2Fdavid_igou%2Frouteros_configuration%2F&query=%24.highest_version.version&label=galaxy)
![Ansible](https://img.shields.io/badge/ansible-%3E%3D2.15-blue?logo=ansible)
![CI](https://img.shields.io/github/actions/workflow/status/david-igou/ansible-collection-routeros_configuration/tests.yml?branch=main&label=CI)
![License](https://img.shields.io/github/license/david-igou/ansible-collection-routeros_configuration)
![Last Commit](https://img.shields.io/github/last-commit/david-igou/ansible-collection-routeros_configuration)
[![Docs](https://img.shields.io/badge/docs-online-success?logo=readthedocs)](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/)

📖 **Documentation site:** <https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/>
— generated collection + role reference (rebuilt on every push to `main`).

## Description

Ansible collection for managing MikroTik RouterOS **declaratively**. At its core,
the [`configure`](roles/configure/) role reconciles a single `routeros_config`
data structure against the device — adding, updating, and optionally purging
entries idempotently — in a canonical dependency order, driving any path
`community.routeros.api_modify` supports (no per-path role). The
[`export_vars`](roles/export_vars/) role does the reverse, capturing a running
device into a re-appliable `routeros_config` file.

Around that core sit single-purpose **operational** roles for day-2 work —
backup/restore, certificates, upgrades, password rotation, file transfer,
connectivity checks, PoE power management, reboot/reset, and an arbitrary-command
escape hatch. Most roles talk to the device over the `community.routeros`
**binary API** from the controller (`delegate_to: localhost`); the `backup` role
is the exception, running over `network_cli` (SSH) because RouterOS `/export` is
console-only.

Targeted at homelab / lab operators who want their RouterOS configuration in
version control and reconciled like any other infrastructure-as-code.

> **Status: early-stage (0.0.x) — expect breaking changes.** The `routeros_config`
> data contract, variable names, defaults, and role names may shift between 0.0.x
> releases without long deprecation windows. Pin a specific version in your
> `requirements.yml`.

## Requirements

- **Ansible** >= 2.15 on the control node (see `meta/runtime.yml`).
- **`librouteros`** Python library on the controller (`pip install librouteros`)
  — the binary-API roles depend on it.
- A **RouterOS device** with the **`api`** service enabled (port 8728), or
  **`api-ssl`** (port 8729) for TLS — strongly preferred in production.
- For the **`backup`** role only: **SSH** access to the device (`network_cli`),
  since `/export` is console-only rather than on the binary API.

Connection details for the API roles are supplied once through the shared
`routeros_api_*` variables (define them in `group_vars`); `routeros_api_password`
has no default — supply it via Ansible Vault.

### Collection dependencies

Declared in `galaxy.yml` and auto-resolved by Galaxy on install:

| Collection | Required for | Version |
|---|---|---|
| `community.routeros` | the RouterOS API / network_cli modules every role uses | >= 3.0.0 |
| `ansible.netcommon` | the `network_cli` connection (the `backup` role) | >= 8.0.0 |
| `ansible.utils` | pulled transitively; declared for clarity | * |

## Installation

Install from Ansible Galaxy:

```bash
ansible-galaxy collection install david_igou.routeros_configuration
```

Or pin a version in `requirements.yml`:

```yaml
---
collections:
  - name: david_igou.routeros_configuration
    version: 0.0.1-alpha
```

Upgrade to the latest:

```bash
ansible-galaxy collection install david_igou.routeros_configuration --upgrade
```

## Use Cases

### Reconcile a device from declarative data

Drive the `configure` role with a `routeros_config` dict keyed by RouterOS slash
path. Keys may be authored in any order — the role re-sorts them into a canonical
dependency order (e.g. `/ip/pool` before the `/ip/dhcp-server` that references
it, a bridge before its ports) before applying:

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.configure
      vars:
        routeros_config:
          /ip/pool:
            data:
              - name: lan
                ranges: "192.168.88.10-192.168.88.254"
          /ip/firewall/filter:
            purge: true                            # exact-state for this path
            order: true                            # enforce rule order (requires purge)
            content: remove_as_much_as_possible    # required to purge a keyless path
            data:
              - chain: input
                action: accept
                connection-state: "established,related"
                comment: est
              - chain: input
                action: drop
                comment: drop-rest
```

A second run with the same data reports no changes.

### Capture an existing device into version control

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.export_vars
```

Writes a per-host `routeros_config` vars file (capture → review → re-apply with
`configure`). Secrets are included by default — encrypt the output with Vault, or
set `routeros_export_vars_redact: true`.

### Back up (and restore) a device

```yaml
- hosts: routers
  gather_facts: false
  roles:
    # Idempotent text /export to a .rsc on the controller, plus an optional binary backup.
    - role: david_igou.routeros_configuration.backup
    # Restore from a binary backup (reboots) or import a .rsc script.
    - role: david_igou.routeros_configuration.restore
      vars:
        routeros_restore_backup_name: pre-change
        routeros_restore_backup_password: "{{ vault_backup_password }}"
```

### Day-2 operations

```yaml
- hosts: routers
  gather_facts: false
  roles:
    # Power-cycle a PoE-out port (e.g. reboot an attached AP/camera).
    - role: david_igou.routeros_configuration.poe
      vars:
        routeros_poe_action: power_cycle
        routeros_poe_interfaces:
          - ether5
    # Reboot and wait for the API to answer again.
    - role: david_igou.routeros_configuration.reboot
```

## Roles

| Role | Purpose |
|---|---|
| [`configure`](roles/configure/) | Declaratively manage RouterOS from one `routeros_config` data structure (the public entrypoint). |
| [`export_vars`](roles/export_vars/) | Capture a running device's config into a re-appliable `routeros_config` vars file. |
| [`backup`](roles/backup/) | Back up RouterOS configuration — text `/export` over network_cli, plus an optional binary backup. |
| [`restore`](roles/restore/) | Restore a device from a binary backup or a config import. |
| [`certificate`](roles/certificate/) | Create, sign, export, and import RouterOS certificates (and ACME requests) over the API. |
| [`upgrade`](roles/upgrade/) | Set the update channel and install RouterOS package/firmware upgrades over the API. |
| [`user_password`](roles/user_password/) | Set or rotate RouterOS `/user` passwords over the API. |
| [`command`](roles/command/) | Run arbitrary RouterOS API commands — an escape hatch for unmodeled operations. |
| [`fetch`](roles/fetch/) | Transfer files to/from the device via `/tool fetch`. |
| [`ping`](roles/ping/) | Run connectivity checks via `/tool ping` over the API. |
| [`poe`](roles/poe/) | Power-cycle, force off/on, or monitor PoE-out ports (imperative; persistent PoE config stays in `configure`). |
| [`reboot`](roles/reboot/) | Reboot or shut down a RouterOS device. |
| [`reset`](roles/reset/) | Reset RouterOS configuration (gated; destructive). |
| [`_reconcile`](roles/_reconcile/) | Internal engine — reconciles a single path via `community.routeros.api_modify`. Not called directly. |

Any path supported by `community.routeros.api_modify` is usable through
`configure` — there is no per-path role. See
[`roles/configure/README.md`](roles/configure/README.md) for the `routeros_config`
schema, the ordering model, and how keyed vs keyless (firewall) updates are
matched.

## Testing

[Molecule](https://ansible.readthedocs.io/projects/molecule/) scenarios live in
`extensions/molecule/`. They share a single QEMU **CHR** (Cloud Hosted Router)
instance across scenarios, exercising the roles against a real RouterOS over the
API (and `network_cli` for `backup`).

```bash
make molecule                  # the shared CHR pass across all scenarios
make molecule SCENARIO=poe     # a single scenario against the shared CHR
```

See [`extensions/molecule/README.md`](extensions/molecule/README.md) for the
scenario catalogue and provisioner wiring. Hardware-specific operations that a
CHR cannot exercise (PoE power actions, RouterBOARD firmware, ACME, a real
reset/shutdown) are gated and validated on real hardware rather than in CI.

## Contributing

Contributions are welcome. See [CONTRIBUTING](CONTRIBUTING); the project follows
the [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/devel/community/code_of_conduct.html)
(local copy at [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)).

Bug reports and feature requests:
<https://github.com/david-igou/ansible-collection-routeros_configuration/issues/new/choose>.

## Support

This is a personal-project collection — **not an Ansible Certified Collection**,
no commercial support. Best-effort community support via GitHub:

- **Issues**: <https://github.com/david-igou/ansible-collection-routeros_configuration/issues>
- **Security**: report sensitive issues privately via the repository's GitHub
  Security Advisories (the **Security** tab) rather than a public issue.
- **Discussions / questions**: open an issue; there is no separate forum.

Only the most recent release receives fixes. The collection is at 0.0.x (alpha) —
pin to a specific version if you depend on a given shape.

## Release Notes and Roadmap

- **Release notes**: [CHANGELOG.rst](CHANGELOG.rst)
- **Galaxy listing**: <https://galaxy.ansible.com/ui/repo/published/david_igou/routeros_configuration/>
- **Roadmap**: no formal roadmap. Near-term focus is stabilizing the `configure`
  `routeros_config` data contract and broadening operational role coverage. Open
  issues tagged `enhancement` at
  <https://github.com/david-igou/ansible-collection-routeros_configuration/issues?q=label%3Aenhancement>
  are the de-facto backlog.

## Related Information

- [**Documentation site**](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/)
  — the getting-started guide plus the generated collection / role reference
  (antsibull-docs).
- [Getting-started guide](docs/docsite/rst/guide.rst) — declarative-config
  walkthrough and a minimal inventory.

External:

- [MikroTik RouterOS documentation](https://help.mikrotik.com/docs/) — upstream OS
- [`community.routeros` collection](https://galaxy.ansible.com/ui/repo/published/community/routeros/)
  — the underlying API / network_cli modules
- [Ansible Using Collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html)

## License Information

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
