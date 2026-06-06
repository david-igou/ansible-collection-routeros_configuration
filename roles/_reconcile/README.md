# _reconcile (internal engine)

Reconciles one RouterOS config path declaratively via
`community.routeros.api_modify`. Not a user entrypoint — the `configure` role
includes it once per path, looping over `routeros_config` (the leading slash is
trimmed and inner slashes become spaces, e.g. `/ip/pool` -> `ip pool`):

    - ansible.builtin.include_role:
        name: _reconcile
      vars:
        rcfg_path: ip pool
        rcfg_data: "{{ routeros_config['/ip/pool'].data }}"
        rcfg_purge: "{{ routeros_config['/ip/pool'].purge | default(false) }}"
        rcfg_order: "{{ routeros_config['/ip/pool'].order | default(false) }}"
        rcfg_content: "{{ routeros_config['/ip/pool'].content | default('ignore') }}"

Connection comes from the shared `routeros_api_*` vars (see defaults).
`rcfg_order: true` requires `rcfg_purge: true`.

## Idempotency & rollback

**Idempotent:** yes — wraps `community.routeros.api_modify`, which reconciles
desired vs on-device state and reports no change once converged.

**Destructive options:** `rcfg_purge: true` maps to `handle_absent_entries:
remove` and `rcfg_order: true` to `ensure_order` — both can delete on-device
entries. There is no built-in undo; roll back by re-applying a known-good
`rcfg_data` or restoring a device backup taken beforehand.
