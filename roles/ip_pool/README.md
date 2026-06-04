# ip_pool

Declaratively manage `/ip/pool` over the RouterOS API.

    routeros_ip_pool:
      - name: lan-pool
        ranges: "192.168.88.10-192.168.88.254"
    routeros_ip_pool_purge: true   # optional: exact-state

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
