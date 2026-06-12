.. _ansible_collections.david_igou.routeros_configuration.docsite.export_vars_role:

david_igou.routeros_configuration.export_vars role
==================================================

Captures a running device's configuration over the API into a ``routeros_config`` vars file that ``configure`` can re-apply. The reverse of ``configure``.

Built on the collection's
:ansplugin:`to_routeros_config <david_igou.routeros_configuration.to_routeros_config#filter>`
(shapes ``api_info`` results into ``routeros_config``, with redaction and
ordered-path handling) and
:ansplugin:`to_indented_yaml <david_igou.routeros_configuration.to_indented_yaml#filter>`
(lint-clean YAML serialization) filters — both reusable in your own plays.

See the :ansplugin:`full role reference <david_igou.routeros_configuration.export_vars#role>` for all parameters and defaults.
