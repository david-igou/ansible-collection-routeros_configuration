# ip_firewall_raw

Declaratively manage `/ip/firewall/raw` over the RouterOS API.

    routeros_ip_firewall_raw:
      - chain: prerouting
        action: accept
    routeros_ip_firewall_raw_purge: true
    routeros_ip_firewall_raw_order: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
