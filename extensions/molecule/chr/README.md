# `chr` Molecule scenario

Feasibility scenario proving the `david_igou.molecule_provisioners` **qemu**
backend can boot a MikroTik CHR (Cloud Hosted Router) VM and that Ansible can
manage RouterOS on it via `community.routeros`.

## Run

```bash
cd extensions/molecule/chr
CHR_VERSION=7.21.4 bash files/stage-chr-image.sh   # one-time image staging
molecule test -s chr
```

`verify.yml` runs `/system resource print` over `community.routeros` (network_cli)
and asserts on the RouterOS version. A green run ends with, e.g.:

> `RouterOS reachable via qemu provider: version: 7.21.4 (long-term)`

## How it works

- **Image** — CHR ships a zipped *raw* `.img`; the qemu role consumes qcow2.
  `files/stage-chr-image.sh` downloads, unzips, and `qemu-img convert`s it to
  `~/.cache/chr-images/chr-<ver>.qcow2`, which `inventory/hosts.yml` references
  via a `file://` URL.
- **Boot** — `create.yml` dispatches to the provisioner's qemu role (SLIRP
  networking, host `2222+index` → guest `22`).
- **prepare.yml** — does *not* import the provisioner prepare (its
  `wait_for_connection` needs a POSIX shell CHR lacks). Instead it TCP-waits on
  the forwarded SSH port, then bootstraps a known admin password over the
  empty-password login (CHR's default `admin` has no password, which network_cli
  refuses).
- **verify.yml** — connects with `community.routeros` over network_cli. The
  login user is `admin+cet1024w`: the `+cet1024w` suffix disables RouterOS
  console colors and forces a fixed wide terminal, so RouterOS skips its
  interactive cursor-probe that otherwise hangs network_cli. (Mirrors
  `igou-inventory` `group_vars/routeros.yml`.)

## Requirements

- System: `qemu-system-x86_64`, `qemu-img`, `genisoimage` (or `cloud-localds`),
  `unzip`, `sshpass`. KVM (`/dev/kvm`) recommended; falls back to TCG.
- Python: `ansible-pylibssh` (libssh backend — paramiko fails to negotiate
  RouterOS SSH). See `test-requirements.txt`.
- Collections: installed from `requirements.yml` (provisioner + community.routeros
  + ansible.netcommon).

## Pinned image

CHR `7.21.4` from <https://mikrotik.com/download/chr>. Bump `CHR_VERSION` in
`files/stage-chr-image.sh`, `inventory/hosts.yml`, and `prepare.yml` together.

## Known limitations / follow-ups

- Auth uses a password bootstrapped post-boot (`molecule`). Production RouterOS
  uses SSH keys; injecting a key (cloud-init `meta-data: public-keys`, or
  `/user/ssh-keys/import` in prepare) is a follow-up.
- `converge.yml` is a no-op; applying/asserting real RouterOS config is future
  work for the collection's roles.
- network_cli (CLI) is used here to mirror the production inventory. The
  `community.routeros.api_*` modules (API on 8728) are the path for declarative
  config and would need the API port reachable (e.g. a forwarded port).
