# ip_cloud

Declaratively manage `/ip/cloud` over the RouterOS API.

    routeros_ip_cloud:
      - ddns-update-interval: "none"
        update-time: false

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
