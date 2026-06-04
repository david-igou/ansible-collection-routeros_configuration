# interface_bridge_port

Declaratively manage `interface bridge port` over the RouterOS API.

    routeros_interface_bridge_port:
      - {bridge: bridge1, interface: ether3}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
