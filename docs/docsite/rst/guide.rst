.. _ansible_collections.david_igou.routeros_configuration.docsite.guide:

Getting started
===============

``david_igou.routeros_configuration`` manages the state of MikroTik RouterOS
devices **declaratively**. You describe the desired configuration as data and a
single role — :ansplugin:`configure <david_igou.routeros_configuration.configure#role>`
— reconciles the device to match it (add, update, and optionally purge entries),
idempotently. Around that core sit single-purpose operational roles for backup,
restore, certificates, upgrades, reboots, and more. Most roles talk to the
device over the ``community.routeros`` binary API, run from the controller; the
``backup`` role is the exception, running over ``network_cli`` (SSH) because
RouterOS ``/export`` is console-only.

.. note::

   Early-stage 0.0.x — expect breaking changes between releases. Pin a specific
   version in your ``requirements.yml``.

The setup
---------

You need, on the **control node**:

- ansible-core >= 2.15;
- the ``librouteros`` Python library — every binary-API role depends on it:

  .. code-block:: bash

     pip install librouteros

and on the **device**: the ``api`` service enabled (port 8728), or ``api-ssl``
(port 8729) for TLS. Both are managed under ``/ip service`` on RouterOS.

Install the collection (its runtime dependency, ``community.routeros``, is
resolved automatically):

.. code-block:: bash

   ansible-galaxy collection install david_igou.routeros_configuration

The roles connect to the device's binary API from the controller
(``delegate_to: localhost``), so the connection is configured with
``routeros_api_*`` variables rather than an SSH ``ansible_connection`` — no SSH
or Python is needed on the device. A minimal inventory:

.. code-block:: yaml

   # inventory/hosts.yml
   all:
     children:
       routers:
         hosts:
           router-01:
             ansible_host: 192.0.2.1
         vars:
           routeros_api_hostname: "{{ ansible_host }}"  # API target; else defaults to inventory_hostname
           routeros_api_username: admin
           routeros_api_password: "{{ vault_routeros_api_password }}"  # via Ansible Vault
           routeros_api_tls: true
           routeros_api_validate_certs: true

Create the vaulted password in one step:

.. code-block:: bash

   ansible-vault encrypt_string 'changeme' --name vault_routeros_api_password \
     >> inventory/group_vars/routers/vault.yml

.. note::

   **First contact with a fresh device:** a factory-default RouterOS device has
   no certificate on ``api-ssl``, so the TLS settings above cannot connect yet.
   Bootstrap on a trusted network with ``routeros_api_tls: false`` (plain api,
   port 8728), provision a certificate with the
   :ansplugin:`certificate <david_igou.routeros_configuration.certificate#role>`
   role (and bind it to ``api-ssl`` via ``configure``), then switch TLS on.

Declarative configuration
--------------------------

Drive the ``configure`` role with a ``routeros_config`` dict, keyed by RouterOS
path. Each path carries a ``data`` list (the desired entries) and optional
``purge`` / ``order`` / ``content`` controls. Keys may be authored in any order —
the role re-sorts them into a canonical dependency order before applying:

.. code-block:: yaml

   - hosts: routers
     gather_facts: false  # the device runs no Python; roles talk to the API from the controller
     roles:
       - role: david_igou.routeros_configuration.configure
         vars:
           routeros_config:
             /system/identity:
               data:
                 - name: edge-router
             /ip/pool:
               data:
                 - name: lan-pool
                   ranges: 192.168.88.10-192.168.88.254
             /ip/firewall/filter:
               purge: true        # exact-state for this chain
               order: true        # enforce rule order
               content: remove_as_much_as_possible
               data:
                 - chain: input
                   action: accept
                   connection-state: "established,related"
                   comment: est
                 - chain: input
                   action: accept
                   protocol: tcp
                   dst-port: "22,8728"
                   comment: mgmt
                 - chain: input
                   action: drop
                   comment: drop-rest

.. warning::

   ``purge: true`` removes every on-device entry not present in ``data`` —
   review a ``--check --diff`` run before applying ``purge``/``order`` to a
   production chain.

A second run with the same data reports no changes. Capture an existing device's
configuration into a re-appliable ``routeros_config`` file with the
:ansplugin:`export_vars <david_igou.routeros_configuration.export_vars#role>`
role (built on the collection's
:ansplugin:`to_routeros_config <david_igou.routeros_configuration.to_routeros_config#filter>`
and
:ansplugin:`to_indented_yaml <david_igou.routeros_configuration.to_indented_yaml#filter>`
filters, which are reusable in your own plays).

SSH connection for the backup role
----------------------------------

The :ansplugin:`backup <david_igou.routeros_configuration.backup#role>` role is
the one exception to the API model: RouterOS ``/export`` is console-only, so it
runs over ``network_cli`` (SSH). Give backup-targeted hosts the standard
network-CLI connection variables (libssh — paramiko fails RouterOS SSH):

.. code-block:: yaml

   # group_vars/routers/network_cli.yml
   ansible_connection: ansible.netcommon.network_cli
   ansible_network_os: community.routeros.routeros
   ansible_network_cli_ssh_type: libssh
   ansible_user: "admin+cet1024w"  # +cet1024w stops RouterOS' interactive cursor probe
   ansible_password: "{{ vault_routeros_api_password }}"

Operational roles
-----------------

Beyond ``configure``, the collection provides focused roles for day-2
operations — back up and restore configuration, manage certificates, set update
channels and install upgrades, rotate user passwords, reboot or reset the
device, transfer files, manage PoE-out power (power-cycle, off/on, monitor), and
run connectivity checks or arbitrary API commands.
Each role's parameters, defaults, and behavior are documented in the role
reference (see the **Roles** section in the navigation). Roles whose names start
with an underscore (``_reconcile``, ``_wait_api``) are internal helpers — they
appear in the generated role index but are not meant to be called directly.
