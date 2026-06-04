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
