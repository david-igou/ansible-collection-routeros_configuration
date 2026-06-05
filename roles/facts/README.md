# facts

Gather RouterOS device facts over the binary API (`community.routeros.api_facts`),
setting `ansible_net_*` facts for reporting, drift detection, and pre-flight checks.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.facts
- debug: { var: ansible_net_version }
```

Read-only and idempotent. Connection comes from the shared `routeros_api_*` vars.
