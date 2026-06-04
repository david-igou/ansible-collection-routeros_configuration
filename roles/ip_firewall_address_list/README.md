# ip_firewall_address_list

Declaratively manage `/ip/firewall/address-list` over the RouterOS API.

    routeros_ip_firewall_address_list:
          - list: blocked
            address: "203.0.113.0/24"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
