# ip_service

Declaratively manage `/ip/service` over the RouterOS API.

    routeros_ip_service:
      - name: telnet
        disabled: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
