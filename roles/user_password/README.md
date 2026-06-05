# user_password

Set or rotate `/user` account passwords over the binary API — the write-only field
the `configure` role can't manage.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.user_password
      vars:
        routeros_user_passwords:
          - { name: admin, password: "{{ vault_admin_password }}" }
```

The users must already exist (create them with `configure` / `/user`); the role
**fails** if a named user is missing rather than silently skipping it. **Not
idempotent** — RouterOS never returns passwords, so the role sets them every run
(reported as `ok` since the API command reports no change). Supply passwords from
a vault. Connection comes from the shared `routeros_api_*` vars.
