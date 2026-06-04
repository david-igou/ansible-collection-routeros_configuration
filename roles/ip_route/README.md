# ip_route

Declaratively manage `/ip/route` over the RouterOS API.

    routeros_ip_route:
      - dst-address: "10.0.0.0/8"
        gateway: "192.168.88.254"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
