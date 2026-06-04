# ip_neighbor_discovery_settings

Declaratively manage `/ip/neighbor/discovery-settings` over the RouterOS API.

    routeros_ip_neighbor_discovery_settings:
      - discover-interface-list: none

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
