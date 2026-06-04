# ip_firewall_mangle

Declaratively manage `/ip/firewall/mangle` over the RouterOS API.

    routeros_ip_firewall_mangle:
      - chain: prerouting
        action: accept
    routeros_ip_firewall_mangle_purge: true
    routeros_ip_firewall_mangle_order: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
