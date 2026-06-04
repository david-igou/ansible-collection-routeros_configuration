# ip_dhcp_client

Declaratively manage `/ip/dhcp-client` over the RouterOS API.

    routeros_ip_dhcp_client:
      - interface: ether1
        add-default-route: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
