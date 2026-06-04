# interface_bridge_vlan

Declaratively manage `interface bridge vlan` over the RouterOS API.

    routeros_interface_bridge_vlan:
      - {bridge: bridge1, vlan-ids: 10, tagged: bridge1}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
