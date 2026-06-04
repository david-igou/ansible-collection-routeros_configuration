# interface_ethernet

Declaratively manage `interface ethernet` over the RouterOS API.

    routeros_interface_ethernet:
      - {name: ether3, comment: uplink, mtu: 1500}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
