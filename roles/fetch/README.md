# fetch

Transfer files to/from a RouterOS device with `/tool fetch` (HTTP/S, FTP, TFTP,
SFTP) and remove files with `/file remove`. Use it to stage firmware, scripts,
or certificates onto the device, or to pull backups off-box.

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.fetch
      vars:
        routeros_fetch:
          - url: "https://example.com/extra.npk"
            dst_path: extra.npk
            mode: https
        routeros_fetch_remove:
          - old-backup.backup
```

Connection comes from the shared `routeros_api_*` vars. `fetch` overwrites the
destination each run; `remove` only acts when the file is present (so it is safe
to re-run).
