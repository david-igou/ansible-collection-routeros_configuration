# upgrade

Manage a RouterOS device's package update channel and, optionally, install an
available update — over the binary API.

## Usage

```yaml
- hosts: routers
  gather_facts: false
  roles:
    # Safe default: set the channel and check for updates, no install.
    - role: david_igou.routeros_configuration.upgrade
      vars:
        routeros_update_channel: stable

    # Opt in to installing (reboots the device — use a maintenance window).
    - role: david_igou.routeros_configuration.upgrade
      vars:
        routeros_update_channel: stable
        routeros_upgrade_install: true
```

Connection comes from the shared `routeros_api_*` vars (see `defaults/main.yml`).

## Variables

| Var | Default | Meaning |
| --- | --- | --- |
| `routeros_update_channel` | `stable` | `stable` / `testing` / `long-term` / `development` |
| `routeros_upgrade_install` | `false` | install an available update (**reboots**) |
| `routeros_upgrade_reboot_timeout` | `300` | seconds to wait for the API after reboot |

## Idempotency & rollback

**Idempotent:** yes, on the safe path. The channel is set only when it differs
from the current one, and `check-for-updates` is read-only — so a converged
device reports no change on re-run. `check-for-updates` needs outbound internet;
a failed check does not fail the play (the install gate just won't fire).

**Install path:** when `routeros_upgrade_install: true` **and** an update is
available, the role installs it and waits for the API to return after the reboot.
This is inherently a one-time change.

**Rollback:** RouterOS keeps the previous version — downgrade with
`/system package downgrade` (reboots) or restore a binary backup taken before the
upgrade (see the `backup` role).

## Out of scope

RouterBOARD firmware upgrade (`/system routerboard upgrade`) — tracked as a
follow-up.

## RouterBOARD firmware

`routeros_routerboard_upgrade: true` runs `/system routerboard upgrade` and
reboots. Gated and **not exercised in CI** (a CHR has no RouterBOARD).
