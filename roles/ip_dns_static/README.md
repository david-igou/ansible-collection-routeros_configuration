# ip_dns_static

Declaratively manage `/ip/dns/static` over the RouterOS API.

    routeros_ip_dns_static:
      - name: router.lan
        address: "192.168.88.1"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
