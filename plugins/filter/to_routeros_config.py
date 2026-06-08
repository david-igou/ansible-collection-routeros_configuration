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


def to_routeros_config(results, redact=False, sensitive_fields=None):
    """Build a routeros_config dict from looped api_info results.

    Args:
        results: list of api_info loop result dicts (each with 'item' + 'result').
        redact: when True, blank out sensitive field values.
        sensitive_fields: field names to redact (defaults to DEFAULT_SENSITIVE_FIELDS).

    Returns:
        dict: {slash_path: {'data': [entries]}} for every non-empty path.
    """
    if not isinstance(results, list):
        raise AnsibleFilterError(
            "to_routeros_config expects a list of api_info results, got %s"
            % type(results).__name__
        )
    if sensitive_fields is None:
        sensitive_fields = DEFAULT_SENSITIVE_FIELDS

    config = {}
    for item in results:
        if not isinstance(item, dict) or "item" not in item:
            raise AnsibleFilterError(
                "each result must be a dict with an 'item' key (the path)"
            )
        entries = item.get("result") or []
        if not entries:
            continue
        cleaned = []
        for entry in entries:
            new_entry = {k: v for k, v in entry.items() if k != ".id"}
            # Drop entries that carry no settable fields once .id is removed:
            # an all-default singleton captured with handle_disabled=omit, or an
            # entry that held only .id. There is nothing for the configure role
            # to reconcile, so it is noise in the captured baseline.
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
        config[item["item"]] = {"data": cleaned}
    return config


class FilterModule:
    """filter plugin."""

    def filters(self):
        """Map filter names to functions."""
        return {"to_routeros_config": to_routeros_config}
