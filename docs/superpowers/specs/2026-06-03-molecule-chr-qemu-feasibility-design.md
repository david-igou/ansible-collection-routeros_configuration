# Molecule + RouterOS CHR over QEMU — Feasibility Spike Design

- **Date:** 2026-06-03
- **Status:** Approved (design), pending implementation
- **Author:** david_igou (with Claude)
- **Scope:** One throwaway-but-reusable Molecule scenario that proves the
  `david_igou.molecule_provisioners` **qemu** backend can boot a MikroTik CHR
  VM and that Ansible can reach the RouterOS CLI on it.

## Goal

Before building the `david_igou.routeros_configuration` collection's real test
harness, validate the foundation: **Molecule can stand up a RouterOS CHR
instance via the qemu provider, and we can run a RouterOS command against it.**

Success = `molecule test` for the new scenario:

1. Boots a CHR VM through the provisioner's qemu role.
2. Connects to it via `community.routeros` over `network_cli`.
3. Runs `/system/resource/print` and asserts the output identifies RouterOS.

Anything beyond reaching the CLI (applying real config, cloud-init SSH-key
injection) is explicitly out of scope for this spike.

## Background / constraints discovered

- **Repo state:** freshly scaffolded `ansible-creator` collection
  (`david_igou.routeros_configuration`). Existing molecule scenarios under
  `extensions/molecule/` use the legacy `platforms:` + `provisioner: ansible`
  schema; the provisioner repo uses the newer `ansible.executor` schema. This
  spike follows the **provisioner repo's documented pattern**.
- **Provisioner qemu role** (`david_igou.molecule_provisioners`, role `qemu`):
  caches a base image (dedup by SHA256, auto-decompresses xz), builds a NoCloud
  cloud-init **seed ISO** (`cloud-localds`) for SSH-key injection, creates a
  qcow2 overlay, launches `qemu-system-x86_64 -daemonize` with SLIRP
  `hostfwd` (host `2222+index` → guest `22`), then waits for SSH. It is built
  around **Linux cloud images** (POSIX shell, cloud-init cloud-config).
- **CHR is not a Linux cloud image:**
  - Distributed as a **raw `.img` inside a `.zip`** (not qcow2, not xz).
  - Default login is **`admin` with an empty password**.
  - SSH exposes the **RouterOS CLI**, not a POSIX shell — Molecule's normal
    Python-based `prepare`/`converge` cannot run on it.
  - RouterOS 7.x supports cloud-init but imports SSH keys from the NoCloud
    `meta-data: public-keys` field and treats `user-data` as a RouterOS script;
    it does **not** parse the Linux `users:`/`ssh_authorized_keys` cloud-config
    that `cloud-localds` emits by default.
- **Chosen approach (A):** use the qemu role to boot CHR, make readiness a TCP
  port wait (not a Python SSH connection), and verify over `community.routeros`
  authenticating as **`admin` with empty password**. Cloud-init key injection is
  a documented follow-up.

## Two integration gaps this spike must resolve

These are the unknowns the spike exists to validate; the implementation plan
must address each and is expected to iterate on them:

1. **Image format gap.** The role targets qcow2 and auto-decompresses *xz*; CHR
   ships a *zipped raw* image. We will pre-stage the image: download the CHR
   `.img.zip`, unzip to raw, `qemu-img convert -f raw -O qcow2` to qcow2, and
   point the scenario's `image:` at that **local qcow2 file**. This sidesteps
   the role's URL-fetch/decompress assumptions.
2. **Readiness gap.** The role's "wait for SSH" likely assumes a working
   Python/SSH login as the cloud user, which CHR cannot satisfy. We will make
   readiness a **TCP wait on the forwarded SSH port** (`wait_for`), overriding
   or no-oping the role's SSH-connection wait if it blocks. If the role only
   does a TCP wait, no override is needed — to be confirmed during impl.

## Architecture

```
extensions/molecule/chr/
├── collections.yml          # pulls david_igou.molecule_provisioners (git) + community.routeros
├── molecule.yml             # ansible.executor schema; maps create/destroy/prepare/converge/verify
├── create.yml               # import_playbook: david_igou.molecule_provisioners.create
├── destroy.yml              # import_playbook: david_igou.molecule_provisioners.destroy
├── prepare.yml              # stage CHR qcow2 image + TCP-wait for forwarded SSH port
├── converge.yml             # no-op (nothing to configure for the spike) OR thin RouterOS reachability touch
├── verify.yml               # community.routeros: /system/resource/print + assert
└── inventory/
    ├── hosts.yml            # one CHR host under group `molecule`, mp.qemu.image -> local qcow2
    └── group_vars/
        └── molecule.yml     # mp_backend=qemu defaults; network_cli connection vars for converge/verify
```

### Component responsibilities

- **collections.yml** — installs the provisioner collection (git, `main`) and
  `community.routeros` for the verify connection.
- **molecule.yml** — `scenario.name: chr`; maps the five playbooks; verifier
  `ansible`; passes the scenario inventory to the executor.
- **create.yml / destroy.yml** — one-line dispatchers importing the
  provisioner's backend-agnostic playbooks (backend selected as qemu).
- **prepare.yml** — (a) ensures the CHR qcow2 exists locally (download zip →
  unzip → `qemu-img convert` if missing; idempotent, cached by version); (b)
  `wait_for` the forwarded SSH TCP port to accept connections.
- **converge.yml** — no-op for the spike (the goal is boot + reach CLI, not
  config). Kept as an explicit file so the scenario is complete and extensible.
- **verify.yml** — runs `community.routeros.command` `/system/resource/print`
  against the CHR host and asserts the result mentions RouterOS / a version.

### Connection model (verify/converge hosts)

Set on the CHR host (group_vars or hostvars), used only by converge/verify:

```yaml
ansible_connection: ansible.netcommon.network_cli
ansible_network_os: community.routeros.routeros
ansible_host: 127.0.0.1
ansible_port: "{{ 2222 + (group index) }}"   # provided by the qemu role's runtime inventory
ansible_user: admin
ansible_password: ""                           # CHR default
ansible_ssh_common_args: >-
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
# RouterOS may require legacy host-key/KEX algorithms; exact ssh args TBD during impl.
```

The qemu role writes a runtime inventory with `ansible_host`/`ansible_port` for
each host; the scenario layers the RouterOS-specific connection vars on top.

## Image selection

- Source: `https://download.mikrotik.com/routeros/<version>/chr-<version>.img.zip`
  (the versioned form behind <https://mikrotik.com/download/chr>).
- **Pin a specific stable 7.x version** for reproducibility (Renovate can bump
  it later). Exact current-stable version string is confirmed at implementation
  time by checking the download site; the spec does not hard-code a version that
  may not resolve.
- CHR resources: 1 vCPU, **256 MB RAM minimum** (allocate ~256–512 MB), 128 MB
  disk minimum. SLIRP user networking (the role's default) is sufficient.

## Testing / acceptance

- `cd extensions/molecule/chr && PROVISIONER=qemu molecule test` (or the repo's
  standard molecule invocation) completes green:
  create → prepare → converge → verify → destroy.
- The `verify` step's assertion on `/system/resource/print` output is the
  definitive proof of "Molecule can run RouterOS via the qemu provider."
- Manual fallback during bring-up: after `molecule create`, confirm
  `ssh -p 2222 admin@127.0.0.1` reaches the RouterOS prompt.

## Out of scope (follow-ups)

- Cloud-init SSH **public-key** injection into CHR (Approach C) — switch verify
  from password to key auth once boot+connect is proven.
- Applying/asserting real RouterOS configuration (identity, addresses, etc.).
- Multi-version / matrix testing, CI wiring, and the collection's actual roles.

## Risks

- **Role assumptions fight CHR** (image format, SSH-wait). Mitigated by the
  prepare-time image staging and TCP-wait override; if the role hard-blocks,
  we fall back to documenting the minimal change needed in the provisioner repo.
- **RouterOS SSH algorithm negotiation** with `network_cli` may need explicit
  legacy `HostKeyAlgorithms`/KEX ssh args — resolved empirically during impl.
- **No git repo** in this workspace yet — design doc is written but not
  committed (no `.git`). Initialize git separately if version history is wanted.
```

