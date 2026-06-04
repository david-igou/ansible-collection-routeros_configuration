# ip_firewall_nat

Declaratively manage `/ip/firewall/nat` over the RouterOS API.

    routeros_ip_firewall_nat:
      - chain: srcnat
        action: masquerade
        out-interface: ether1
    routeros_ip_firewall_nat_purge: true
    routeros_ip_firewall_nat_order: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
