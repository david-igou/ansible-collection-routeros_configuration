# ip_firewall_filter

Declaratively manage `/ip/firewall/filter` over the RouterOS API. Rules are
ordered; enable `_order` (which requires `_purge`) for exact ordered state.

    routeros_ip_firewall_filter:
      - {chain: input, action: accept, connection-state: "established,related"}
      - {chain: input, action: accept, protocol: icmp}
      - {chain: input, action: drop, comment: "drop the rest"}
    routeros_ip_firewall_filter_purge: true
    routeros_ip_firewall_filter_order: true

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
**Caution:** enabling `_purge` on an incomplete list can lock you out.
