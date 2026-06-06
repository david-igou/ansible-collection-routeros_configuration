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

Install the collection (and its runtime dependency, ``community.routeros``):

.. code-block:: bash

   ansible-galaxy collection install david_igou.routeros_configuration

The roles connect to the device's binary API from the controller
(``delegate_to: localhost``), so the connection is configured with
``routeros_api_*`` variables rather than an SSH ``ansible_connection``. A
minimal inventory:

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

Declarative configuration
--------------------------

Drive the ``configure`` role with a ``routeros_config`` dict, keyed by RouterOS
path. Each path carries a ``data`` list (the desired entries) and optional
``purge`` / ``order`` / ``content`` controls. Keys may be authored in any order —
the role re-sorts them into a canonical dependency order before applying:

.. code-block:: yaml

   - hosts: routers
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

A second run with the same data reports no changes. Capture an existing device's
configuration into a re-appliable ``routeros_config`` file with the
:ansplugin:`export_vars <david_igou.routeros_configuration.export_vars#role>`
role.

Operational roles
-----------------

Beyond ``configure``, the collection provides focused roles for day-2
operations — back up and restore configuration, manage certificates, set update
channels and install upgrades, rotate user passwords, reboot or reset the
device, transfer files, and run connectivity checks or arbitrary API commands.
Each role's parameters, defaults, and behavior are documented in the role
reference (see the **Roles** section in the navigation).
