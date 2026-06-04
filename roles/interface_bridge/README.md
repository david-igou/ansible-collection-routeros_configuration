# interface_bridge

Declaratively manage `interface bridge` over the RouterOS API.

    routeros_interface_bridge:
      - {name: bridge1, comment: lan}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
