# ip_dhcp_server_network

Declaratively manage `/ip/dhcp-server/network` over the RouterOS API.

    routeros_ip_dhcp_server_network:
      - address: "192.168.88.0/24"
        gateway: "192.168.88.1"
        dns-server: "192.168.88.1"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
