# ip_vrf

Declaratively manage `/ip/vrf` over the RouterOS API.

    routeros_ip_vrf:
      - name: mgmt
        interfaces: ether5

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
