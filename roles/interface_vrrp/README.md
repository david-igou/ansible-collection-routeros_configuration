# interface_vrrp

Declaratively manage `interface vrrp` over the RouterOS API.

    routeros_interface_vrrp:
      - {name: vrrp1, interface: ether3, vrid: 1}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
