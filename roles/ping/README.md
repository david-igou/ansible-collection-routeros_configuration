# ping

Connectivity checks via `/tool ping` over the binary API — useful for pre/post-change
validation in playbooks.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.ping
      vars:
        routeros_ping:
          - { address: "1.1.1.1", count: 3 }
```

Results are registered in `_routeros_ping`. Read-only. Connection comes from the
shared `routeros_api_*` vars.
