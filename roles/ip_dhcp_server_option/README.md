# ip_dhcp_server_option

Declaratively manage `/ip/dhcp-server/option` over the RouterOS API.

    routeros_ip_dhcp_server_option:
      - name: tftp
        code: 66
        value: "'192.168.88.1'"

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
