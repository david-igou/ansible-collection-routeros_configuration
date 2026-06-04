# system_identity

Declaratively manage `/system/identity` (device name) over the RouterOS API.

    routeros_system_identity:
      - name: core-router

Requires the shared `routeros_api_*` connection vars (see the `_reconcile` role).
