# restore

Restore a RouterOS device from a binary backup (`/system backup load`) or import a
config script (`/import`). The reverse of the `backup` role.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.restore
      vars:
        routeros_restore_backup_name: pre-change   # loads pre-change.backup; REBOOTS
        routeros_restore_backup_password: "{{ vault_backup_password }}"
```

A binary backup load **reboots** the device; the role waits for the API to return.
`/import` does not reboot. The backup/`.rsc` file must already be on the device
(stage it with the `fetch` role). Connection comes from the shared `routeros_api_*`
vars.

**Note:** loading a binary backup over the API requires a non-empty
`routeros_restore_backup_password` — RouterOS rejects an empty password on
`/system backup load`. Save backups encrypted (the `backup` role's
`routeros_backup_password`).
