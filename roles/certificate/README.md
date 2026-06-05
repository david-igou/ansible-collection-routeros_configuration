# certificate

Create and sign RouterOS certificates over the binary API, idempotently. Closes
the TLS-bootstrap gap: the collection's roles default to `tls: true`, but
`api_modify` treats `certificate` as read-only, so certificates need the `api`
module's `add`/`sign`.

## Usage

```yaml
- hosts: routers
  gather_facts: false
  roles:
    - role: david_igou.routeros_configuration.certificate
      vars:
        routeros_certificates:
          # A self-signed CA (no `ca:`), usable to sign other certs.
          - name: lan-ca
            common_name: LAN Root CA
            key_usage: [key-cert-sign, crl-sign]
          # A host certificate signed by that CA.
          - name: router-api
            common_name: router.lan
            ca: lan-ca
```

Connection comes from the shared `routeros_api_*` vars (see `defaults/main.yml`).

## Per-certificate options

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | str | required | certificate name |
| `common_name` | str | required | certificate CN |
| `key_size` | int | `2048` | RSA key size |
| `days_valid` | int | `365` | validity in days |
| `key_usage` | list | — | key usages (e.g. `[key-cert-sign, crl-sign]` for a CA) |
| `ca` | str | — | name of the signing CA; omit for self-signed |

## Idempotency & rollback

**Idempotent:** yes. The role reads existing certificates first; it only creates
requests whose `name` is absent and only signs certs with an empty `fingerprint`
(not yet signed). A converged device reports no change on re-run. List CA certs
before the host certs that reference them.

**Rollback:** remove a certificate with `community.routeros.api` (`path:
certificate`, `cmd: remove …`) or in WinBox/CLI; re-running this role recreates
it. Certificates and their private keys are sensitive — protect the device and
any exported key material.

## Out of scope

Importing existing PEM cert/key files, SCEP enrollment, and `trusted`-flag
management — tracked as follow-ups.
