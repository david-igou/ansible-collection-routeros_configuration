# ip_arp

Declaratively manage `/ip/arp` over the RouterOS API.

    routeros_ip_arp:
      - address: "192.168.88.10"
        mac-address: "00:11:22:33:44:55"
        interface: ether1

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
