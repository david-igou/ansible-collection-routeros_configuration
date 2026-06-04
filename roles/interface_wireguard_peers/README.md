# interface_wireguard_peers

Declaratively manage `interface wireguard peers` over the RouterOS API.

    routeros_interface_wireguard_peers:
      - {interface: wg0, public-key: KEY, allowed-address: 10.0.0.2/32}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
