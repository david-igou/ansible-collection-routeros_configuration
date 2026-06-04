# interface_vxlan

Declaratively manage `interface vxlan` over the RouterOS API.

    routeros_interface_vxlan:
      - {name: vxlan1, vni: 100}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
