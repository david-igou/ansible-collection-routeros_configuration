certificate
===========

Create, sign, export, and import RouterOS certificates — and request ACME
(Let's Encrypt) certs — over the binary API. Closes the TLS-bootstrap gap: the
collection's roles default to `tls: true`, but `api_modify` treats `certificate`
as read-only, so certificates go through the `api` module's `add`/`sign`/etc.

Requirements
------------

- The [`community.routeros`](https://galaxy.ansible.com/ui/repo/published/community/routeros/) collection.
- The `librouteros` Python library on the controller (`pip install librouteros`).
- The device's `api` (8728) or `api-ssl` (8729, preferred) service enabled.

Role Variables
--------------

The connection is supplied through the shared `routeros_api_*` variables (define
them once in `group_vars`); `routeros_api_password` has no default — supply it
via Ansible Vault.

| Variable | Required | Default | Choices | Comments |
|---------------------------------|----------|------------------------|-------------|------------------------------------------------------------|
| `routeros_certificates` | no | `[]` | | Certificates to create and sign (see item keys below). |
| `routeros_certificates_export` | no | `[]` | | Certificates to export to files (see item keys below). |
| `routeros_certificates_import` | no | `[]` | | Certificates to import from files (see item keys below). |
| `routeros_acme` | no | `[]` | | ACME (Let's Encrypt) requests; each item carries an `args` string (the `add-acme` arguments). Gated; not exercised in CI. |
| `routeros_api_hostname` | no | `{{ inventory_hostname }}` | | API host/IP of the device. |
| `routeros_api_username` | no | `admin` | | API username. |
| `routeros_api_password` | yes | _(undefined)_ | | API password — secret; supply via Vault. |
| `routeros_api_tls` | no | `true` | true, false | Use TLS (`api-ssl`, port 8729). |
| `routeros_api_validate_certs` | no | `true` | true, false | Validate the device's TLS certificate. |
| `routeros_api_port` | no | `""` | | TCP port; empty lets the module pick 8728/8729 from `tls`. |

`routeros_certificates` item (list CA certs before the host certs that use them):

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `name` | yes | | Certificate name. |
| `common_name` | yes | | Certificate CN. |
| `key_size` | no | `2048` | RSA key size. |
| `days_valid` | no | `365` | Validity in days. |
| `key_usage` | no | | List of key usages (e.g. `[key-cert-sign, crl-sign]` for a CA). |
| `ca` | no | | Name of the signing CA; omit for self-signed. |

`routeros_certificates_export` item:

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `name` | yes | | Certificate to export. |
| `file_name` | no | = `name` | Output file name. |
| `type` | no | `pem` | Export type (`pem`/`pkcs12`). |
| `export_passphrase` | no | | Passphrase to encrypt the exported key (omit to export the public cert only). |

`routeros_certificates_import` item:

| Item key | Required | Default | Comments |
|----------|----------|---------|------------------------------------------------------------|
| `file_name` | yes | | File on the device to import. |
| `name` | no | | Name for the imported certificate. |
| `passphrase` | no | | Passphrase for an encrypted key. |

Create/sign are idempotent (only creates absent names, only signs unsigned
certs); import skips a file when a cert with the target `name` already exists, so
re-runs don't duplicate. Export and import are imperative file operations
(RouterOS deletes a file when it is imported), so that flow does not converge to
a no-op. Free-form name/CN/CA/file/passphrase values are quoted before being
sent; passphrase-bearing and ACME tasks are `no_log`.

Dependencies
------------

None. (Requires the `community.routeros` collection — see Requirements. Pair with
the `fetch` role to stage import files.)

Example Playbook
----------------

    - hosts: routers
      gather_facts: false
      roles:
        - role: david_igou.routeros_configuration.certificate
          vars:
            routeros_certificates:
              # A self-signed CA (no `ca:`), usable to sign other certs.
              - name: lan-ca
                common_name: LAN Root CA
                key_usage:
                  - key-cert-sign
                  - crl-sign
              # A host certificate signed by that CA.
              - name: router-api
                common_name: router.lan
                ca: lan-ca
            routeros_certificates_export:
              - name: lan-ca
                file_name: lan-ca
                type: pem

License
-------

GPL-3.0-or-later. See [LICENSE](../../LICENSE).

Author Information
------------------

David Igou — https://github.com/david-igou/ansible-collection-routeros_configuration
