# _reconcile (internal engine)

Reconciles one RouterOS config path declaratively via
`community.routeros.api_modify`. Not a user entrypoint — subsystem roles
include it:

    - ansible.builtin.include_role:
        name: _reconcile
      vars:
        rcfg_path: ip address
        rcfg_data: "{{ routeros_ip_address }}"
        rcfg_purge: "{{ routeros_ip_address_purge }}"

Connection comes from the shared `routeros_api_*` vars (see defaults).
`rcfg_order: true` requires `rcfg_purge: true`.

## Idempotency & rollback

**Idempotent:** yes — wraps `community.routeros.api_modify`, which reconciles
desired vs on-device state and reports no change once converged.

**Destructive options:** `rcfg_purge: true` maps to `handle_absent_entries:
remove` and `rcfg_order: true` to `ensure_order` — both can delete on-device
entries. There is no built-in undo; roll back by re-applying a known-good
`rcfg_data` or restoring a device backup taken beforehand.
