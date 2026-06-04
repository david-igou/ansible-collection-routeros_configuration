# interface_wireguard

Declaratively manage `interface wireguard` over the RouterOS API.

    routeros_interface_wireguard:
      - {name: wg0, listen-port: 13231}

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
