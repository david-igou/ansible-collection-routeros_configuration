# Copyright (c) 2026, David Igou
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shape community.routeros.api_info loop results into a routeros_config dict."""

from __future__ import absolute_import, annotations, division, print_function


__metaclass__ = type  # pylint: disable=C0103

from ansible.errors import AnsibleFilterError


DOCUMENTATION = """
    name: to_routeros_config
    author: David Igou (@david-igou)
    version_added: "1.0.0"
    short_description: Build a routeros_config dict from api_info results.
    description:
      - Turns the registered results of a looped C(community.routeros.api_info)
        into the C(routeros_config) structure the C(configure) role consumes.
      - Each entry has its C(.id) removed. Entries left with no settable fields
        (and paths left with no entries) are omitted, so all-default singletons
        and empty paths do not clutter the capture. Optionally redacts sensitive
        field values.
    options:
      _input:
        description:
          - The C(results) list registered from a looped C(api_info) task. Each
            element exposes C(item) (the slash path) and C(result) (the entries).
        type: list
        elements: dict
        required: true
      redact:
        description: Replace the value of any sensitive field with C(REDACTED).
        type: bool
        default: false
      sensitive_fields:
        description: Field names treated as sensitive when O(redact=true).
        type: list
        elements: str
      volatile_fields:
        description:
          - Mapping of slash path to a list of runtime field names to strip from
            that path's entries (e.g. C(/system/clock) C(date)/C(time)).
        type: dict
      ordered_paths:
        description:
          - Slash paths whose entry order is significant. These are emitted with
            C(order: true) and C(purge: true) so the configure role enforces order.
        type: list
        elements: str
"""

EXAMPLES = """
- name: Capture paths
  community.routeros.api_info:
    path: "{{ item | replace('/', ' ') | trim }}"
    hide_defaults: true
    include_dynamic: false
    include_read_only: false
  loop: "{{ routeros_export_vars_paths }}"
  register: captured

- name: Assemble routeros_config
  ansible.builtin.set_fact:
    routeros_config: "{{ captured.results | david_igou.routeros_configuration.to_routeros_config }}"
"""

RETURN = """
  _value:
    description: A C(routeros_config) dict, keyed by slash path, each with a C(data) list.
    type: dict
"""

# Readable secret fields (verified against community.routeros field metadata).
# /user password is write-only and never appears in api_info output.
DEFAULT_SENSITIVE_FIELDS = [
    "private-key",
    "preshared-key",
    "secret",
    "password",
    "authentication-password",
    "encryption-password",
    "passphrase",
]


def to_routeros_config(
    results,
    redact=False,
    sensitive_fields=None,
    volatile_fields=None,
    ordered_paths=None,
):
    """Build a routeros_config dict from looped api_info results.

    Args:
        results: list of api_info loop result dicts (each with 'item' + 'result').
        redact: when True, blank out sensitive field values.
        sensitive_fields: field names to redact (defaults to DEFAULT_SENSITIVE_FIELDS).
        volatile_fields: {slash_path: [field, ...]} of runtime values to strip
            (e.g. /system/clock date/time), so they do not enter the baseline.
        ordered_paths: slash paths whose entry order is significant (firewall
            chains, routing filters, simple queues). These are emitted with
            ``order: true`` and ``purge: true`` so the configure role enforces
            both membership and order (api_modify's ensure_order requires purge).

    Returns:
        dict: {slash_path: {'data': [entries], ['order', 'purge']}} per non-empty path.
    """
    if not isinstance(results, list):
        raise AnsibleFilterError(
            "to_routeros_config expects a list of api_info results, got %s"
            % type(results).__name__
        )
    if sensitive_fields is None:
        sensitive_fields = DEFAULT_SENSITIVE_FIELDS
    volatile_fields = volatile_fields or {}
    ordered = set(ordered_paths or [])

    config = {}
    for item in results:
        if not isinstance(item, dict) or "item" not in item:
            raise AnsibleFilterError(
                "each result must be a dict with an 'item' key (the path)"
            )
        path = item["item"]
        entries = item.get("result") or []
        if not entries:
            continue
        # .id is never re-appliable; volatile fields are runtime state, not config.
        drop = {".id"} | set(volatile_fields.get(path, []))
        cleaned = []
        for entry in entries:
            new_entry = {k: v for k, v in entry.items() if k not in drop}
            # Drop entries that carry no settable fields once stripped: an
            # all-default singleton captured with handle_disabled=omit, an entry
            # that held only .id, or one left empty after volatile stripping.
            # There is nothing for the configure role to reconcile.
            if not new_entry:
                continue
            if redact:
                for field in sensitive_fields:
                    if field in new_entry:
                        new_entry[field] = "REDACTED"
            cleaned.append(new_entry)
        # Omit the path entirely if no entry survived.
        if not cleaned:
            continue
        entry_block = {"data": cleaned}
        if path in ordered:
            # ensure_order needs purge — see the _reconcile role's assertion.
            entry_block["order"] = True
            entry_block["purge"] = True
        config[path] = entry_block
    return config


class FilterModule:
    """filter plugin."""

    def filters(self):
        """Map filter names to functions."""
        return {"to_routeros_config": to_routeros_config}
