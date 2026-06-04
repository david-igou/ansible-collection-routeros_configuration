# ip_settings

Declaratively manage `/ip/settings` over the RouterOS API.

    routeros_ip_settings:
      - ip-forward: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
