# configure

Declaratively manage RouterOS over the binary API from a single data structure.
Replaces the per-path roles: every `community.routeros.api_modify` path is driven
by one `routeros_config` dict.

    routeros_config:
      /ip/pool:
        data:
          - name: lan
            ranges: "192.168.88.10-192.168.88.254"
      /ip/firewall/filter:
        purge: true
        order: true
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

## Requirements & usage

- `librouteros` on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729) service enabled.
- The shared `routeros_api_*` connection variables in `group_vars`;
  `routeros_api_password` has no default — supply it via Ansible Vault. The
  role runs from the controller (`delegate_to: localhost`) — no SSH or Python
  is needed on the device; see the
  [getting-started guide](https://david-igou.github.io/ansible-collection-routeros_configuration/branch/main/docsite/guide.html)
  for a minimal inventory.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.configure
      vars:
        routeros_config:
          /system/identity:
            data:
              - name: edge-router
```

In practice, keep `routeros_config` in `group_vars`/`host_vars` (or capture it
from a live device with `export_vars`) rather than inline in the play.

## Per-path options

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `data` | list | required | desired entries for the path |
| `purge` | bool | `false` | remove on-device entries not in `data` |
| `order` | bool | `false` | enforce entry order (requires `purge`) |
| `content` | str | `ignore` | how to treat fields absent from a matched entry |

Keys are RouterOS **slash paths** (`/ip/firewall/filter`), mapped to the
space-separated `api_modify` path internally.

## Ordering & dependencies

`configure` applies paths in a canonical dependency order (`vars/main.yml`), so
`/ip/pool` precedes the `/ip/dhcp-server` that references it and a bridge precedes
its ports — regardless of how you write `routeros_config` or how it merges across
group_vars/host_vars. Unlisted paths apply last.

## How updates work

Reconciliation is `api_modify`'s. **Keyed paths** (e.g. `/ip/pool` by `name`)
match by primary key, so editing a non-key field updates in place. **Keyless
paths** (firewall, route, dns-static, arp) have no key — `api_modify` overwrites
the most-similar existing entry; for predictable firewall updates give each rule
a stable `comment` and use `purge: true` (+ `order: true`), since additive mode
adds an edited keyless rule as a duplicate.

Connection comes from the shared `routeros_api_*` vars (see the `_reconcile` role).

## Idempotency & rollback

**Idempotent:** yes — a converged device reports `ok`/no changes on re-run.
Reconciliation is `api_modify`'s, which compares desired vs on-device state.

**Destructive options:** `purge: true` *removes* on-device entries absent from
`data`, and `order: true` (which requires `purge`) rewrites entry order — both
can delete live configuration. Review a `--check` / `--diff` run before applying
`purge`/`order` to a production path.

**Rollback:** this role has no built-in undo. Recover by re-applying a known-good
`routeros_config` (the desired state *is* the source of truth) or restoring a
device backup (`/system/backup`) or exported config (`/export`) taken beforehand.
Keep `routeros_config` in version control so any prior state can be re-applied.
