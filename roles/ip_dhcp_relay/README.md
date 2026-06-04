# ip_dhcp_relay

Declaratively manage `/ip/dhcp-relay` over the RouterOS API.

    routeros_ip_dhcp_relay:
      - name: relay1
        interface: ether2
        dhcp-server: "192.168.88.1"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
