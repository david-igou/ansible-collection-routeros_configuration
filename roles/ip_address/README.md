# ip_address

Declaratively manage `/ip/address` over the RouterOS API.

    routeros_ip_address:
      - {address: "192.168.88.1/24", interface: "ether1"}
      - {address: "10.0.0.1/24", interface: "ether2"}
    routeros_ip_address_purge: true   # optional: exact-state

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
