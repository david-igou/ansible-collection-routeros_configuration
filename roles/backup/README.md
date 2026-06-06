# backup

Back up a RouterOS device's configuration, following the official RouterOS
backup/restore mechanisms:

- **Text export** (`/export`) → a portable, version-controllable `.rsc` file on
  the Ansible controller. This is the **idempotent** primary artifact: it is
  rewritten only when the device configuration changed.
- **Binary backup** (`/system backup save`, opt-in) → a full-fidelity,
  same-device/same-version restore image kept on the device.

Unlike the rest of this collection, `backup` runs over **network_cli** (SSH CLI),
not the binary API — `/export` is a console-only command.

## Connection

Configure the device for network_cli (libssh; paramiko fails RouterOS SSH):

```yaml
ansible_connection: ansible.netcommon.network_cli
ansible_network_os: community.routeros.routeros
ansible_network_cli_ssh_type: libssh
ansible_user: "admin+cet1024w"   # +cet1024w stops RouterOS' interactive cursor probe
ansible_password: "{{ vault_routeros_password }}"
```

## Usage

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.backup
      vars:
        routeros_backup_dir: ./routeros-backups
        routeros_backup_binary: true
        routeros_backup_password: "{{ vault_backup_password }}"
```

## Variables

| Var | Default | Meaning |
| --- | --- | --- |
| `routeros_backup_dir` | `./routeros-backups` | controller dir for the `.rsc` export |
| `routeros_backup_show_sensitive` | `true` | `/export show-sensitive` (include service secrets) |
| `routeros_backup_export_options` | `""` | extra `/export` args (menu path, `terse`) |
| `routeros_backup_binary` | `false` | also `/system backup save` on the device |
| `routeros_backup_name` | `ansible` | binary backup file name |
| `routeros_backup_password` | `""` | binary backup encryption password (secret) |

## What the export does and does not contain

With `routeros_backup_show_sensitive: true` the `.rsc` includes service secrets
(WireGuard keys, IPsec PSKs, PPP secrets, SNMP communities, WiFi passphrases).
Per the official docs, `/export` **never** includes **local user passwords,
installed certificates, SSH keys, Dude, or the User-manager database** — there is
no export mechanism for those. Use a binary backup (`routeros_backup_binary:
true`) when you need a restore that preserves them.

## Idempotency & restore

**Idempotent:** yes, for the text export — the `.rsc` is written with
`ansible.builtin.copy`, so a re-run against unchanged config reports `ok` (the
volatile `# … by RouterOS` timestamp header line is stripped so it does not cause
spurious diffs). The optional binary backup writes a fresh point-in-time file
each run but is reported as a non-change so it does not break idempotence.

**Restore (run on the device, per the official docs):**
- Text export: `/import file-name=<name>.rsc` — merges the config; review first.
- Binary backup: `/system backup load name=<name> password=<password>` — full
  restore, reboots the device; restore on the **same RouterOS version**.

**Security:** both the `.rsc` (with `show-sensitive`) and the binary backup
contain secrets — store them encrypted and restrict access. The binary backup
should be password-encrypted (`routeros_backup_password`).
