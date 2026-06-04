# interface_eoip

Declaratively manage `interface eoip` over the RouterOS API.

    routeros_interface_eoip:
      - {name: eoip1, remote-address: 203.0.113.5, tunnel-id: 1}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
