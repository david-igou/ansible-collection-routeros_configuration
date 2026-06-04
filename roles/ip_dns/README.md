# ip_dns

Declaratively manage `/ip/dns` over the RouterOS API.

    routeros_ip_dns:
      - servers: "1.1.1.1,8.8.8.8"
        allow-remote-requests: false

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
