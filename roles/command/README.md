# command

Run a list of arbitrary RouterOS API operations — an escape hatch for one-off
actions not covered by the other roles (run a script, make a lease static, log out
a HotSpot user, etc.). Uses `community.routeros.api` over the binary API.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.command
      vars:
        routeros_command:
          - { path: "system script", cmd: "run .id=*1" }
          - { path: "ip dhcp-server lease", cmd: "make-static .id=*2" }
```

**Not idempotent** — it runs whatever you give it. Connection comes from the shared
`routeros_api_*` vars.

Set `no_log: true` on an item whose command carries a secret (it is hidden from
logs):

```yaml
routeros_command:
  - { path: "ppp secret", add: "name=vpn password=s3cret", no_log: true }
```
