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
    version_added: "0.0.1-alpha"
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
        description:
          - Replace the value of any sensitive field with C(REDACTED).
          - By default a field is sensitive when its name ends in C(key),
            C(secret), C(password) or C(passphrase), or is a known secret the
            suffixes miss (e.g. the WEP C(static-key-0..3)). Known public
            fields such as a WireGuard peer's C(public-key) are exempted.
        type: bool
        default: false
      sensitive_fields:
        description:
          - Field names treated as sensitive when O(redact=true). When set,
            ONLY these exact names are redacted — the default suffix matching
            is replaced, not extended.
        type: list
        elements: str
      volatile_fields:
        description:
          - Mapping of slash path to a list of field names to strip from that
            path's entries — either volatile runtime values (e.g. C(/system/clock)
            C(date)/C(time)) or values that break api_modify's round-trip matching
            (e.g. C(/ip/ipsec/policy) C(group)).
        type: dict
      ordered_paths:
        description:
          - Slash paths whose entry order is significant. These are emitted with
            C(order=true), C(purge=true) and C(content) so the configure role
            enforces order (api_modify rejects purge with the default
            content=ignore on these paths).
        type: list
        elements: str
      ordered_content:
        description:
          - The C(content) value (handle_entries_content) emitted for ordered
            paths. Defaults to C(remove_as_much_as_possible).
        type: str
        default: remove_as_much_as_possible
    notes:
      - Redaction is opt-in. A redacted capture is for review only — the
        literal C(REDACTED) values do not round-trip; prefer encrypting an
        unredacted capture with Ansible Vault.
    seealso:
      - module: community.routeros.api_info
      - module: community.routeros.api_modify
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

# community.routeros exposes dozens of readable secret-bearing fields
# (pre-shared-key, l2tp-secret, radius secret, eap-password, ...) and the set
# grows with every release — match by suffix instead of maintaining an
# exact-name list. tests/unit/test_to_routeros_config.py pins this heuristic
# against the installed community.routeros field metadata.
DEFAULT_SENSITIVE_SUFFIXES = ("key", "secret", "password", "passphrase")

# Secrets the suffixes miss: WEP static keys, /system/ntp/key's key-val, and
# RoMON's secrets list.
DEFAULT_SENSITIVE_FIELDS = frozenset(
    {
        "key-val",
        "secrets",
        "static-key-0",
        "static-key-1",
        "static-key-2",
        "static-key-3",
    }
)

# Suffix-matched fields that are NOT secrets: a WireGuard peer's public-key is
# required config, allow-sharedkey is a boolean, lacp-user-key an LACP integer.
DEFAULT_PUBLIC_FIELDS = frozenset({"public-key", "allow-sharedkey", "lacp-user-key"})


def _is_sensitive(field, sensitive_fields):
    """Return True when a field's value must be redacted.

    A user-supplied sensitive_fields list keeps exact-match semantics; the
    default is suffix matching plus the exact-name extras, with public-field
    exemptions.
    """
    if sensitive_fields is not None:
        return field in sensitive_fields
    if field in DEFAULT_PUBLIC_FIELDS:
        return False
    return field in DEFAULT_SENSITIVE_FIELDS or field.endswith(DEFAULT_SENSITIVE_SUFFIXES)


def to_routeros_config(
    results,
    redact=False,
    sensitive_fields=None,
    volatile_fields=None,
    ordered_paths=None,
    ordered_content="remove_as_much_as_possible",
):
    """Build a routeros_config dict from looped api_info results.

    Args:
        results: list of api_info loop result dicts (each with 'item' + 'result').
        redact: when True, blank out sensitive field values.
        sensitive_fields: exact field names to redact (default: any field whose
            name ends in key/secret/password/passphrase, minus known public
            fields — see _is_sensitive).
        volatile_fields: {slash_path: [field, ...]} of runtime values to strip
            (e.g. /system/clock date/time), so they do not enter the baseline.
        ordered_paths: slash paths whose entry order is significant (firewall
            chains, routing filters, simple queues). These are emitted with
            ``order: true``, ``purge: true`` AND ``content`` so the configure
            role enforces both membership and order. api_modify's ensure_order
            requires purge (handle_absent_entries=remove), and on these paths it
            also rejects remove combined with the default content=ignore — so
            content must be pinned or every ordered path is DOA against configure.
        ordered_content: the ``content`` value emitted for ordered paths
            (handle_entries_content); defaults to ``remove_as_much_as_possible``.

    Returns:
        dict: {slash_path: {'data': [...], ['order', 'purge', 'content']}} per non-empty path.
    """
    if not isinstance(results, list):
        raise AnsibleFilterError(
            "to_routeros_config expects a list of api_info results, got %s"
            % type(results).__name__
        )
    volatile_fields = volatile_fields or {}
    ordered = set(ordered_paths or [])

    config = {}
    for index, item in enumerate(results):
        if not isinstance(item, dict) or "item" not in item:
            raise AnsibleFilterError(
                "result %d must be a dict with an 'item' key (the path), got %s"
                % (index, type(item).__name__)
            )
        path = item["item"]
        if path in config:
            raise AnsibleFilterError(
                "result %d repeats path %r — a duplicate capture would silently"
                " overwrite the earlier one" % (index, path)
            )
        entries = item.get("result") or []
        if not entries:
            continue
        # .id is never re-appliable; volatile_fields drops per-path values that are
        # runtime state or that break api_modify's round-trip matching.
        drop = {".id"} | set(volatile_fields.get(path, []))
        cleaned = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise AnsibleFilterError(
                    "path %r: each entry must be a dict, got %s"
                    % (path, type(entry).__name__)
                )
            new_entry = {k: v for k, v in entry.items() if k not in drop}
            # Drop entries that carry no settable fields once stripped: an
            # all-default singleton captured with handle_disabled=omit, an entry
            # that held only .id, or one left empty after volatile stripping.
            # There is nothing for the configure role to reconcile.
            if not new_entry:
                continue
            if redact:
                for field in new_entry:
                    if _is_sensitive(field, sensitive_fields):
                        new_entry[field] = "REDACTED"
            cleaned.append(new_entry)
        # Omit the path entirely if no entry survived.
        if not cleaned:
            continue
        entry_block = {"data": cleaned}
        if path in ordered:
            # ensure_order needs purge (handle_absent_entries=remove), and on
            # these paths api_modify rejects remove + the default content=ignore.
            # Pin content too, or configure aborts on every ordered path.
            entry_block["order"] = True
            entry_block["purge"] = True
            entry_block["content"] = ordered_content
        config[path] = entry_block
    return config


class FilterModule:
    """filter plugin."""

    def filters(self):
        """Map filter names to functions."""
        return {"to_routeros_config": to_routeros_config}
