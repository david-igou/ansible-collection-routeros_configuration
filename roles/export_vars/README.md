# export_vars

The **reverse of the `configure` role**: read a running RouterOS device over the
binary API and write an equivalent `routeros_config` vars file to the Ansible
controller. Use it to bring an existing device under declarative management —
capture, commit to version control, then re-apply with `configure`.

## Usage

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.export_vars
      vars:
        routeros_export_vars_dir: ./host_vars-captured
        # Capture only some paths (faster than all 508):
        routeros_export_vars_paths:
          - /ip/address
          - /ip/firewall/filter
          - /interface/bridge
```

Produces `./host_vars-captured/<inventory_hostname>.yml`:

```yaml
---
routeros_config:
  /ip/address:
    data:
      - address: 192.168.88.1/24
        interface: ether1
  ...
```

Feed it straight back into `configure` (e.g. as `host_vars/<host>.yml`).
Connection comes from the shared `routeros_api_*` vars (see `defaults/main.yml`).

## Variables

| Var | Default | Meaning |
| --- | --- | --- |
| `routeros_export_vars_dir` | `./routeros-vars` | controller output directory |
| `routeros_export_vars_paths` | full `rcfg_path_order` (508) | slash paths to capture |
| `routeros_export_vars_redact` | `false` | replace secret values with `REDACTED` |
| `routeros_export_vars_handle_disabled` | `omit` | how unset fields are captured: `omit` / `exclamation` / `null-value` |
| `routeros_export_vars_exclude_paths` | curated list | runtime/state/hardware paths to skip |
| `routeros_export_vars_ordered_paths` | firewall/routing/queue chains | paths captured with `order` + `purge` |
| `routeros_export_vars_volatile_fields` | `{/system/clock: [date, time]}` | per-path runtime fields to strip |

**Only configure-modifiable paths are captured.** The role loads the `configure`
role's canonical `rcfg_path_order` — every path `api_modify` can write
(read-only/status paths are excluded) — and exports only paths in that set, so
the result re-applies cleanly. Any path you request via `routeros_export_vars_paths`
that the `configure` role cannot modify is dropped before querying and reported
in a debug message.

**Runtime/state paths are excluded.** `api_modify` "understands" some paths that
are really device state, not configuration — `/file`, `/system/script/environment`,
`/ip/pool/used`, `/system/resource/*`, `/partitions`, `/queue/interface`, `/ip/cloud`,
and `/certificate` (metadata only, no key material). `routeros_export_vars_exclude_paths`
drops these so the baseline stays declarative; set it to `[]` to capture everything.
To drop a few *more* paths without re-listing the defaults, use
`routeros_export_vars_exclude_paths_extra` (merged onto the default list):

```yaml
routeros_export_vars_exclude_paths_extra:
  - /system/script   # manage scripts elsewhere
  - /ip/tftp
```

**Order-sensitive paths capture order.** Firewall chains, routing filters, and
simple queues are evaluated top-down. `routeros_export_vars_ordered_paths` are
emitted with **`order: true`, `purge: true` and `content`** (default
`remove_as_much_as_possible`, via `routeros_export_vars_ordered_content`) so
`configure` enforces the exact ordered state. `content` is required: `api_modify`
rejects `purge` (remove) combined with the default `content: ignore` on these
paths, so without it the path would abort on re-apply. Because `purge` is implied
(api_modify's `ensure_order` requires it), re-applying **removes any on-device
entry not in the captured baseline** for those paths — intended for exact-state
management.

**Volatile fields are stripped.** `routeros_export_vars_volatile_fields` removes
runtime values that are state, not config (by default `/system/clock`'s `date`
and `time`, which would otherwise push a stale timestamp on re-apply).

**Unset fields default to `omit`.** `routeros_export_vars_handle_disabled` is
passed to `api_info`: `omit` (default) captures only fields that are actually
set — the cleanest baseline to review and curate. Use `exclamation` to keep
unset fields as `!field` markers (the `configure` role reads these as
reset-to-default) when you want the capture to also force defaults on apply.
Empty entries (all-default singletons, `.id`-only) are dropped and empty paths
omitted regardless.

When `routeros_export_vars_paths` is unset, the role captures every configurable
path (omitting empty ones) from `rcfg_path_order`. Querying all 508 paths takes a
while — pass a subset for speed.
No device implements every path, so paths this device doesn't expose (wireless,
CAPsMAN, container, etc.) are skipped rather than fatal — `api_info` errors
matching "not supported", "no such command", or the RouterOS "contact MikroTik
support and send a supout file" sentinel (broken read implementations under e.g.
`/routing/pimsm/*`) are tolerated and the path is omitted; any other failure
(auth, connection, TLS) still aborts. Skipped paths are listed in a debug
message.

## Secrets

By default the captured file **includes service secrets** (WireGuard keys, IPsec
PSKs, PPP/SNMP/WiFi secrets) so it re-applies cleanly — **`ansible-vault` encrypt
it**. Set `routeros_export_vars_redact: true` to replace those with `REDACTED`
(safe to commit, but won't re-apply the secrets). Local `/user` passwords are
write-only on RouterOS and never appear in any capture.

## Idempotency & caveats

**Idempotent:** the vars file is written with `ansible.builtin.copy`, so a re-run
against unchanged device config reports `ok`.

**Best-effort equivalent:** `api_info` fields do not always map 1:1 to the
`api_modify` input the `configure` role uses (some computed/normalised values).
Review a captured file before re-applying. The output uses plain `data:` lists;
add per-path `purge`/`order`/`content` yourself where you want exact-state.
