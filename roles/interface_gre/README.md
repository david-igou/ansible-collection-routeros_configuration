# interface_gre

Declaratively manage `interface gre` over the RouterOS API.

    routeros_interface_gre:
      - {name: gre1, remote-address: 203.0.113.5}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
