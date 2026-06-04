# interface_vlan

Declaratively manage `interface vlan` over the RouterOS API.

    routeros_interface_vlan:
      - {name: vlan10, vlan-id: 10, interface: ether3}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
