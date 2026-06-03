# Molecule scenarios

Each scenario lives in its own subdirectory. Invoke from the **collection root**:

```bash
# Resolve runtime deps once, then run a scenario:
make molecule SCENARIO=chr

# Or directly (after `make install`), from the collection root:
MOLECULE_GLOB="extensions/molecule/*/molecule.yml" molecule test -s chr
```

`MOLECULE_GLOB` overrides molecule's default `molecule/<scenario>/` layout to
point at this collection's `extensions/molecule/<scenario>/` layout. Running
from the collection root also lets molecule auto-discover
`extensions/molecule/config.yml` (which only fires from the collection root, not
a scenario subdir).

## Deterministic collection resolution

- **Test-only** provisioner backends come from
  [`david_igou.molecule_provisioners`](https://galaxy.ansible.com/ui/repo/published/david_igou/molecule_provisioners/),
  pinned in `extensions/molecule/requirements-test.yml` and installed
  automatically by molecule's `dependency` step (configured in
  `extensions/molecule/config.yml`). It is **not** in the root `requirements.yml`,
  so consumers of this collection never auto-pull test tooling.
- **Runtime** deps (`community.routeros`, `ansible.netcommon`) come from the root
  `requirements.yml` / `galaxy.yml` and are installed by `make install` (which
  `make molecule` runs first).

No collection needs to be manually pre-installed: `make molecule SCENARIO=chr`
resolves everything.

## Scenarios

| Scenario | Backend | What it proves |
| --- | --- | --- |
| `chr` | qemu | A MikroTik CHR VM boots via the qemu provider and RouterOS is reachable over `community.routeros` (network_cli). See `chr/README.md`. |
