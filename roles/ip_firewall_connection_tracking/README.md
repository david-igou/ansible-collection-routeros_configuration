# ip_firewall_connection_tracking

Declaratively manage `/ip/firewall/connection/tracking` over the RouterOS API.

    routeros_ip_firewall_connection_tracking:
          - loose-tcp-tracking: false

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
