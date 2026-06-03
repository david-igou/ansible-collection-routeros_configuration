# Molecule + RouterOS CHR over QEMU — Feasibility Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the `david_igou.molecule_provisioners` qemu backend can boot a MikroTik CHR VM and that Ansible can reach the RouterOS CLI on it, via a new `extensions/molecule/chr/` Molecule scenario.

**Architecture:** A Molecule scenario follows the provisioner repo's documented pattern (`collections.yml` + one-line `create.yml`/`destroy.yml` dispatchers). A `prepare.yml` pre-stages the CHR image (download `.img.zip` → unzip → `qemu-img convert` raw→qcow2, since the role wants qcow2 but CHR ships zipped raw) and TCP-waits on the forwarded SSH port (CHR has no POSIX shell for the role's normal SSH-wait). A `verify.yml` connects via `community.routeros` over `network_cli` as `admin`/empty-password and asserts on `/system/resource/print`.

**Tech Stack:** Molecule, Ansible, `david_igou.molecule_provisioners` (qemu role), `community.routeros`, QEMU/KVM (`qemu-system-x86_64`, `qemu-img`), `genisoimage`/`cloud-localds`, MikroTik CHR (RouterOS 7.x).

**Reference spec:** `docs/superpowers/specs/2026-06-03-molecule-chr-qemu-feasibility-design.md`

> **Note on TDD shape:** This is infrastructure glue, not application code. The "test" for each task is running the actual Molecule/QEMU command and observing the expected real-world result (a booted VM, an SSH banner, a RouterOS command response). Each task states the command and the exact expected observation before the implementing change, then validates it.

> **Note on commits:** The workspace is not yet a git repo. Task 0 initializes it so the frequent-commit discipline applies. If the user declines git, skip the `git commit` step in each task.

---

### Task 0: Initialize repo and prerequisites

**Files:**
- Modify: workspace root (git init)
- Create: none

- [ ] **Step 1: Initialize git and snapshot the scaffold**

```bash
cd /workspace/ansible-collection-routeros_configuration
git init
git add -A
git commit -m "chore: initial scaffold snapshot before CHR molecule spike"
```

Expected: a repo with one commit. If the user does not want git, skip this and all later commit steps.

- [ ] **Step 2: Install the cloud-image seed tool (cloud-localds) for the qemu role's preferred path**

```bash
command -v cloud-localds || sudo dnf install -y cloud-utils || pip install --user cloud-init || true
command -v cloud-localds && echo "cloud-localds OK" || echo "will fall back to genisoimage (present)"
```

Expected: either `cloud-localds OK`, or confirmation we fall back to the already-present `genisoimage`. Both are acceptable — the role tries `cloud-localds` first, then `genisoimage`.

- [ ] **Step 3: Confirm virtualization tooling is present**

```bash
for t in qemu-system-x86_64 qemu-img genisoimage unzip molecule ansible-galaxy; do command -v $t >/dev/null && echo "FOUND $t" || echo "MISSING $t"; done
ls -l /dev/kvm 2>/dev/null && echo "KVM available" || echo "No /dev/kvm — role falls back to TCG (slower, still works)"
```

Expected: all tools `FOUND`. KVM present is ideal; TCG fallback is acceptable.

- [ ] **Step 4: Add test collections to the collection's requirements**

Create/append `test-requirements` collection deps. Create `extensions/molecule/chr/collections.yml` later (Task 2); here just record the Galaxy collection dep for `community.routeros` in `galaxy.yml` is NOT needed (runtime test dep only). No file change in this step — proceed.

- [ ] **Step 5: Commit (no-op if nothing changed)**

```bash
git add -A && git commit -m "chore: confirm qemu/seed tooling for CHR spike" --allow-empty
```

---

### Task 1: Determine and pin the CHR image version + validate raw→qcow2 staging by hand

This is the riskiest gap (image format). Validate it standalone before wiring into Molecule.

**Files:**
- Create: `extensions/molecule/chr/files/stage-chr-image.sh` (helper used by prepare.yml)

- [ ] **Step 1: Discover the current stable CHR version**

```bash
curl -s https://mikrotik.com/download/chr | grep -oiE 'chr-[0-9]+\.[0-9]+(\.[0-9]+)?\.img\.zip' | head -5
# Fallback: browse the index
curl -s https://download.mikrotik.com/routeros/ | grep -oE '7\.[0-9]+(\.[0-9]+)?' | sort -V | tail -5
```

Expected: a concrete stable version string, e.g. `7.16.1`. Record it as `CHR_VERSION`. Pin this exact value in the helper script and inventory.

- [ ] **Step 2: Write the image staging helper**

Create `extensions/molecule/chr/files/stage-chr-image.sh`:

```bash
#!/usr/bin/env bash
# Stage a MikroTik CHR raw image as qcow2 for the molecule qemu provisioner.
# Idempotent: skips download/convert if the qcow2 already exists.
set -euo pipefail

CHR_VERSION="${CHR_VERSION:?set CHR_VERSION, e.g. 7.16.1}"
CACHE_DIR="${CHR_CACHE_DIR:-$HOME/.cache/chr-images}"
ZIP_URL="https://download.mikrotik.com/routeros/${CHR_VERSION}/chr-${CHR_VERSION}.img.zip"

mkdir -p "$CACHE_DIR"
zip_path="$CACHE_DIR/chr-${CHR_VERSION}.img.zip"
raw_path="$CACHE_DIR/chr-${CHR_VERSION}.img"
qcow2_path="$CACHE_DIR/chr-${CHR_VERSION}.qcow2"

if [[ -f "$qcow2_path" ]]; then
  echo "$qcow2_path"
  exit 0
fi

[[ -f "$zip_path" ]] || curl -fSL -o "$zip_path" "$ZIP_URL"
[[ -f "$raw_path" ]] || unzip -o "$zip_path" -d "$CACHE_DIR" >/dev/null
# CHR zip contains a single chr-<ver>.img raw disk
img_inside="$(unzip -Z1 "$zip_path" | grep -E '\.img$' | head -1)"
[[ -f "$CACHE_DIR/$img_inside" ]] && raw_path="$CACHE_DIR/$img_inside"
qemu-img convert -f raw -O qcow2 "$raw_path" "$qcow2_path"
echo "$qcow2_path"
```

```bash
chmod +x extensions/molecule/chr/files/stage-chr-image.sh
```

- [ ] **Step 3: Run the helper to verify download + conversion works**

```bash
CHR_VERSION=<pinned> bash extensions/molecule/chr/files/stage-chr-image.sh
```

Expected: prints a path ending in `.qcow2`. Verify it:

```bash
qemu-img info "$HOME/.cache/chr-images/chr-<pinned>.qcow2"
```

Expected: `file format: qcow2`, virtual size a few hundred MB.

- [ ] **Step 4: Smoke-boot the qcow2 directly to confirm CHR runs under this host's QEMU**

```bash
qemu-system-x86_64 -name chr-smoke -m 256 \
  $( [ -e /dev/kvm ] && echo -enable-kvm -cpu host || echo -accel tcg ) \
  -drive file="$HOME/.cache/chr-images/chr-<pinned>.qcow2",format=qcow2,if=virtio \
  -netdev user,id=n0,hostfwd=tcp::2299-:22 -device virtio-net,netdev=n0 \
  -nographic -serial mon:stdio -daemonize -pidfile /tmp/chr-smoke.pid
sleep 45
ssh -p 2299 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no admin@127.0.0.1
```

Expected: RouterOS login succeeds with empty password (just press Enter) and shows the RouterOS banner / prompt. This proves CHR boots and SSH-with-empty-password works — the foundation of the whole approach. If SSH needs legacy algorithms, note the exact `ssh` flags that worked (they feed `ansible_ssh_common_args` later). Then tear down:

```bash
kill "$(cat /tmp/chr-smoke.pid)" 2>/dev/null || true
```

- [ ] **Step 5: Commit**

```bash
git add extensions/molecule/chr/files/stage-chr-image.sh
git commit -m "feat(molecule): add CHR raw->qcow2 image staging helper"
```

---

### Task 2: Scaffold the Molecule scenario skeleton

**Files:**
- Create: `extensions/molecule/chr/collections.yml`
- Create: `extensions/molecule/chr/molecule.yml`
- Create: `extensions/molecule/chr/create.yml`
- Create: `extensions/molecule/chr/destroy.yml`
- Create: `extensions/molecule/chr/inventory/hosts.yml`
- Create: `extensions/molecule/chr/inventory/group_vars/molecule.yml`

- [ ] **Step 1: collections.yml — pull provisioner + RouterOS collections**

Create `extensions/molecule/chr/collections.yml`:

```yaml
---
collections:
  - name: https://github.com/david-igou/ansible-collection-molecule_provisioners.git
    type: git
    version: main
  - name: community.routeros
  - name: ansible.netcommon
```

- [ ] **Step 2: create.yml / destroy.yml — one-line dispatchers**

Create `extensions/molecule/chr/create.yml`:

```yaml
---
- name: Provision molecule instances
  import_playbook: david_igou.molecule_provisioners.create
```

Create `extensions/molecule/chr/destroy.yml`:

```yaml
---
- name: Destroy molecule instances
  import_playbook: david_igou.molecule_provisioners.destroy
```

- [ ] **Step 3: molecule.yml — executor + playbook map (qemu backend)**

Create `extensions/molecule/chr/molecule.yml`:

```yaml
---
ansible:
  executor:
    args:
      ansible_playbook:
        - --inventory=inventory/
  playbooks:
    create: create.yml
    destroy: destroy.yml
    prepare: prepare.yml
    converge: converge.yml
    verify: verify.yml
scenario:
  name: chr
verifier:
  name: ansible
```

- [ ] **Step 4: inventory/hosts.yml — one CHR host on the qemu backend**

Create `extensions/molecule/chr/inventory/hosts.yml` (set `<pinned>` and the staged qcow2 path from Task 1):

```yaml
---
all:
  children:
    molecule:
      hosts:
        chr-1:
          mp:
            qemu:
              image: "{{ lookup('env', 'HOME') }}/.cache/chr-images/chr-<pinned>.qcow2"
              ssh_user: admin
              cpus: 1
              memory: 256
```

- [ ] **Step 5: inventory/group_vars/molecule.yml — qemu backend + RouterOS connection**

Create `extensions/molecule/chr/inventory/group_vars/molecule.yml`:

```yaml
---
# Force the qemu backend for this scenario regardless of PROVISIONER env.
mp_backend: qemu

mp_defaults:
  qemu:
    cpus: 1
    memory: 256
    ssh_user: admin

# RouterOS connection for converge/verify only. The qemu role supplies
# ansible_host (127.0.0.1) and ansible_port (forwarded) via runtime inventory.
ansible_connection: ansible.netcommon.network_cli
ansible_network_os: community.routeros.routeros
ansible_user: admin
ansible_password: ""
ansible_ssh_common_args: >-
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
  -o PubkeyAuthentication=no -o PreferredAuthentications=password
```

> If Task 1 Step 4 needed extra `ssh` algorithm flags, append them to `ansible_ssh_common_args` here verbatim.

- [ ] **Step 6: Install the scenario collections and verify they resolve**

```bash
cd extensions/molecule/chr
ansible-galaxy collection install -r collections.yml -p ~/.ansible/collections
ansible-galaxy collection list 2>/dev/null | grep -Ei 'molecule_provisioners|routeros|netcommon'
```

Expected: all three collections listed. Confirms the provisioner role `david_igou.molecule_provisioners.qemu` and `community.routeros` are importable.

- [ ] **Step 7: Commit**

```bash
cd /workspace/ansible-collection-routeros_configuration
git add extensions/molecule/chr/
git commit -m "feat(molecule): scaffold chr scenario (collections, dispatchers, inventory)"
```

---

### Task 3: prepare.yml — stage image + TCP-wait for SSH port

**Files:**
- Create: `extensions/molecule/chr/prepare.yml`

- [ ] **Step 1: Write prepare.yml**

Create `extensions/molecule/chr/prepare.yml` (set `<pinned>`):

```yaml
---
- name: Prepare CHR image and wait for SSH port
  hosts: localhost
  gather_facts: false
  vars:
    chr_version: "<pinned>"
  tasks:
    - name: Stage the CHR qcow2 image (download + unzip + convert if missing)
      ansible.builtin.command:
        cmd: "{{ playbook_dir }}/files/stage-chr-image.sh"
      environment:
        CHR_VERSION: "{{ chr_version }}"
      register: stage_result
      changed_when: false

    - name: Show staged image path
      ansible.builtin.debug:
        var: stage_result.stdout

- name: Wait for CHR SSH to accept TCP connections
  hosts: molecule
  gather_facts: false
  connection: local
  tasks:
    - name: Wait for forwarded SSH port (TCP only — CHR has no POSIX shell)
      ansible.builtin.wait_for:
        host: "{{ ansible_host | default('127.0.0.1') }}"
        port: "{{ ansible_port | default(2222) }}"
        timeout: 180
        delay: 5
```

> The qcow2 must already exist before `create` boots the VM. Because Molecule runs `prepare` after `create`, the staging here is a safety/idempotency net; the image is actually produced on first run by the Task 1 helper. If the role needs the file at `create` time, run the helper once manually (Task 4 Step 1) before `molecule test`.

- [ ] **Step 2: Lint the playbook syntax**

```bash
cd extensions/molecule/chr
ansible-playbook --syntax-check -i inventory/ prepare.yml
```

Expected: `playbook: prepare.yml` with no syntax errors. (Connection vars referencing network_cli are fine for syntax-check.)

- [ ] **Step 3: Commit**

```bash
cd /workspace/ansible-collection-routeros_configuration
git add extensions/molecule/chr/prepare.yml
git commit -m "feat(molecule): chr prepare stages image and TCP-waits for SSH"
```

---

### Task 4: First boot — `molecule create` and manual reachability

**Files:** none (validation task)

- [ ] **Step 1: Pre-stage the image so it exists at create time**

```bash
cd extensions/molecule/chr
CHR_VERSION=<pinned> bash files/stage-chr-image.sh
```

Expected: prints the qcow2 path (instant if already cached from Task 1).

- [ ] **Step 2: Run molecule create**

```bash
cd extensions/molecule/chr
molecule create -s chr
```

Expected: the provisioner qemu role caches the image, builds a seed ISO, creates a qcow2 overlay, and launches QEMU. Ends with a success play recap. If it fails on image format/decompress, inspect the role's expectation and (fallback) point `image:` at the staged qcow2 directly / adjust as the error dictates — this is the documented image-format gap.

- [ ] **Step 3: Inspect the runtime inventory to learn the real forwarded port**

```bash
find ~/.cache/molecule ~/.local/share/molecule -name '*.yml' 2>/dev/null | xargs grep -l ansible_port 2>/dev/null | head
# or check the ephemeral dir printed by molecule; note ansible_host / ansible_port for chr-1
```

Expected: `chr-1` has `ansible_host: 127.0.0.1` and `ansible_port: 2222` (or `2222+index`). Record it.

- [ ] **Step 4: Manually confirm the RouterOS CLI is reachable**

```bash
ssh -p <port> -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o PubkeyAuthentication=no -o PreferredAuthentications=password admin@127.0.0.1 \
    '/system resource print'
```

Expected: RouterOS prints resource info (version, uptime, board-name). This is the live proof of the core goal. If the connection negotiation fails, capture the working `ssh` flags and fold them into `ansible_ssh_common_args` (Task 2 Step 5).

- [ ] **Step 5: Tear down**

```bash
molecule destroy -s chr
```

Expected: QEMU process stopped, overlay/seed cleaned. No commit (validation only).

---

### Task 5: converge.yml (no-op) + verify.yml (RouterOS assertion)

**Files:**
- Create: `extensions/molecule/chr/converge.yml`
- Create: `extensions/molecule/chr/verify.yml`

- [ ] **Step 1: converge.yml — explicit no-op (spike configures nothing)**

Create `extensions/molecule/chr/converge.yml`:

```yaml
---
- name: Converge (no-op for the CHR feasibility spike)
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Nothing to configure yet
      ansible.builtin.debug:
        msg: "CHR boot validated; configuration is a follow-up."
```

- [ ] **Step 2: verify.yml — run a RouterOS command and assert**

Create `extensions/molecule/chr/verify.yml`:

```yaml
---
- name: Verify Molecule can reach the RouterOS CLI on CHR
  hosts: molecule
  gather_facts: false
  tasks:
    - name: Query system resource over the RouterOS CLI
      community.routeros.command:
        commands:
          - /system resource print
      register: chr_resource
      retries: 6
      delay: 10
      until: chr_resource is succeeded

    - name: Assert the response identifies RouterOS
      ansible.builtin.assert:
        that:
          - chr_resource.stdout | length > 0
          - chr_resource.stdout[0] is search('version')
        success_msg: "RouterOS reachable via qemu provider: {{ chr_resource.stdout[0] | regex_search('version:.*') }}"
        fail_msg: "Did not get a RouterOS resource response: {{ chr_resource.stdout | default('<none>') }}"
```

- [ ] **Step 3: Syntax-check both playbooks**

```bash
cd extensions/molecule/chr
ansible-playbook --syntax-check -i inventory/ converge.yml verify.yml
```

Expected: no syntax errors.

- [ ] **Step 4: Commit**

```bash
cd /workspace/ansible-collection-routeros_configuration
git add extensions/molecule/chr/converge.yml extensions/molecule/chr/verify.yml
git commit -m "feat(molecule): chr converge (no-op) and verify (/system resource assert)"
```

---

### Task 6: Full `molecule test` green run

**Files:** none (validation task)

- [ ] **Step 1: Ensure image staged, then run the full sequence**

```bash
cd extensions/molecule/chr
CHR_VERSION=<pinned> bash files/stage-chr-image.sh
molecule test -s chr
```

Expected sequence: dependency → create → prepare → converge → **verify (asserts RouterOS)** → destroy, all passing. The verify play's `success_msg` printing the RouterOS version is the definitive acceptance signal.

- [ ] **Step 2: If verify's network_cli connection fails, debug with the known-good ssh flags**

Re-run just the failing stage without teardown:

```bash
molecule converge -s chr   # leaves the VM up
molecule verify -s chr
# iterate on ansible_ssh_common_args / ansible_network_cli_ssh_type (libssh vs paramiko) in group_vars
molecule destroy -s chr
```

Expected: verify passes once the ssh negotiation matches what worked manually in Task 4 Step 4. Common levers: set `ansible_network_cli_ssh_type: libssh` (or `paramiko`), add legacy `HostKeyAlgorithms`/`KexAlgorithms` to `ansible_ssh_common_args`.

- [ ] **Step 3: Commit any connection-var fixes**

```bash
cd /workspace/ansible-collection-routeros_configuration
git add extensions/molecule/chr/inventory/group_vars/molecule.yml
git commit -m "fix(molecule): chr network_cli ssh negotiation for verify" --allow-empty
```

---

### Task 7: Document the result and follow-ups

**Files:**
- Create: `extensions/molecule/chr/README.md`

- [ ] **Step 1: Write a short scenario README**

Create `extensions/molecule/chr/README.md`:

```markdown
# `chr` Molecule scenario

Feasibility scenario proving the `david_igou.molecule_provisioners` **qemu**
backend can boot a MikroTik CHR VM and that Ansible can reach the RouterOS CLI.

## Run

    cd extensions/molecule/chr
    CHR_VERSION=<pinned> bash files/stage-chr-image.sh   # one-time image staging
    molecule test -s chr

`verify.yml` runs `/system resource print` over `community.routeros`
(`network_cli`, `admin`/empty password) and asserts on the RouterOS version.

## Pinned image

CHR `<pinned>` from https://mikrotik.com/download/chr. The staging helper
converts the zipped raw `.img` to qcow2 (the qemu role consumes qcow2).

## Known limitations / follow-ups

- Auth uses CHR's default empty admin password. Cloud-init SSH **public-key**
  injection (NoCloud `meta-data: public-keys`) is a follow-up.
- `converge.yml` is a no-op; applying/asserting real RouterOS config is future
  work that the real collection roles will drive.
```

- [ ] **Step 2: Update the spec's Status to reflect the validated outcome**

Edit `docs/superpowers/specs/2026-06-03-molecule-chr-qemu-feasibility-design.md` header `Status:` line to `Implemented — CHR boots and RouterOS CLI reachable via qemu provider` (or note any caveats found).

- [ ] **Step 3: Commit**

```bash
git add extensions/molecule/chr/README.md docs/superpowers/specs/2026-06-03-molecule-chr-qemu-feasibility-design.md
git commit -m "docs(molecule): document chr scenario and follow-ups"
```

---

## Self-Review notes

- **Spec coverage:** scenario skeleton (Task 2) ↔ spec architecture; image-format gap (Task 1) ↔ spec gap #1; readiness/TCP-wait (Task 3) ↔ spec gap #2; admin/empty-password network_cli verify (Task 5/6) ↔ spec connection model + success bar; image pinning (Task 1) ↔ spec image selection; follow-ups (Task 7) ↔ spec out-of-scope.
- **Placeholders:** `<pinned>` and `<port>` are intentional runtime-discovered values (CHR current stable version; forwarded SSH port from the role's runtime inventory), each with an explicit discovery step (Task 1 Step 1, Task 4 Step 3). All code blocks are complete.
- **Consistency:** `stage-chr-image.sh` env contract (`CHR_VERSION`, output qcow2 path), the qcow2 cache path, and `community.routeros.command` register/assert names are consistent across Tasks 1–7.
