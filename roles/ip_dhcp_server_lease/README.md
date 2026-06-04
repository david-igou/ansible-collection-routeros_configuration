# ip_dhcp_server_lease

Declaratively manage `/ip/dhcp-server/lease` over the RouterOS API.

    routeros_ip_dhcp_server_lease:
      - server: dhcp1
        address: "192.168.88.100"
        mac-address: "00:11:22:33:44:55"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
