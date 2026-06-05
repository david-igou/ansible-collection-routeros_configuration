# reboot

Reboot a RouterOS device (and wait for the API to come back) or shut it down.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.reboot   # reboots + waits

    - role: david_igou.routeros_configuration.reboot    # shut down instead
      vars:
        routeros_shutdown: true
```

Not idempotent. `routeros_shutdown: true` powers the device off (gated; no reconnect
wait). Connection comes from the shared `routeros_api_*` vars.
