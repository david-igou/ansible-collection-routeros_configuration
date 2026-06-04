# ip_dhcp_server

Declaratively manage `/ip/dhcp-server` over the RouterOS API.

    routeros_ip_dhcp_server:
      - name: dhcp1
        interface: ether2
        address-pool: lan-pool

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
