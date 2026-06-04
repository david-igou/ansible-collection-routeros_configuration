# interface_bonding

Declaratively manage `interface bonding` over the RouterOS API.

    routeros_interface_bonding:
      - {name: bond1, slaves: ether5/ether6}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
