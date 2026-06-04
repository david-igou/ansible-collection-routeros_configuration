# interface_list_member

Declaratively manage `interface list member` over the RouterOS API.

    routeros_interface_list_member:
      - {list: WAN, interface: ether3}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
