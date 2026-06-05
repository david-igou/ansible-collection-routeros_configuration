# reset

Reset a RouterOS device's configuration to defaults via `/system reset-configuration`.
**Destructive** — wipes the config and reboots. Gated behind an explicit confirm
var, so it does nothing unless you opt in.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.reset
      vars:
        routeros_reset_confirm: true          # required
        routeros_reset_keep_users: true
        routeros_reset_run_after_reset: "/ip service enable api"
```

Without `routeros_reset_confirm: true` the role is a no-op. The actual reset is
**not exercised in CI** (re-bootstrapping a wiped device reliably is out of scope);
CI tests the safety gate. Connection comes from the shared `routeros_api_*` vars.
