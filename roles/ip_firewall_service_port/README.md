# ip_firewall_service_port

Declaratively manage `/ip/firewall/service-port` over the RouterOS API.

    routeros_ip_firewall_service_port:
          - name: ftp
            disabled: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
