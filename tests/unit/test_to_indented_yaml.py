# Copyright (c) 2026, David Igou
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the to_indented_yaml filter."""

import datetime

import yaml

import pytest

from ansible_collections.david_igou.routeros_configuration.plugins.filter.to_indented_yaml import (
    to_indented_yaml,
)
from ansible.errors import AnsibleFilterError


CONFIG = {
    "routeros_config": {
        "/ip/address": {
            "data": [{"address": "192.168.88.1/24", "interface": "ether1"}],
        },
        "/ip/firewall/filter": {
            "data": [{"chain": "input", "action": "accept"}],
            "order": True,
            "purge": True,
            "content": "remove_as_much_as_possible",
        },
    }
}


def test_sequences_are_indented() -> None:
    """List items are indented beyond their parent key (yaml[indentation]).

    PyYAML's default emitter writes indentless block sequences (the dash
    aligned with the parent key), which ansible-lint's yamllint config
    rejects. The whole point of this filter is the indented form.
    """
    out = to_indented_yaml(CONFIG)
    assert "    data:\n      - address: 192.168.88.1/24\n" in out


def test_round_trips_to_the_same_structure() -> None:
    """The emitted YAML parses back into the input data unchanged."""
    out = to_indented_yaml(CONFIG)
    assert yaml.safe_load(out) == CONFIG


def test_keys_are_sorted() -> None:
    """Keys are emitted sorted, matching to_nice_yaml's layout."""
    out = to_indented_yaml({"b": 1, "a": 2})
    assert out.index("a:") < out.index("b:")


def test_ends_with_single_newline() -> None:
    """The output ends with exactly one newline (yaml[new-line-at-end-of-file])."""
    out = to_indented_yaml(CONFIG)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_unicode_emitted_literally() -> None:
    """Non-ASCII values stay literal instead of \\u escapes (allow_unicode)."""
    out = to_indented_yaml({"comment": "café"})
    assert "café" in out


def test_handles_string_and_int_subclasses() -> None:
    """Tagged scalar subclasses (ansible-core 2.19+ templating) serialize.

    Values arriving through Jinja templating are str/int subclasses under
    data tagging; plain yaml.SafeDumper raises RepresenterError on them.
    """

    class TaggedStr(str):
        pass

    class TaggedInt(int):
        pass

    out = to_indented_yaml(
        {TaggedStr("mtu"): TaggedInt(1500), "name": TaggedStr("ether1")}
    )
    assert yaml.safe_load(out) == {"mtu": 1500, "name": "ether1"}


def test_rejects_unrepresentable_objects() -> None:
    """A value YAML cannot represent raises AnsibleFilterError, not a traceback."""
    with pytest.raises(AnsibleFilterError):
        to_indented_yaml({"bad": object()})


def test_indent_option_changes_nesting_width() -> None:
    """indent=4 widens each nesting level (the filter's only tunable)."""
    out = to_indented_yaml({"key": {"nested": [1]}}, indent=4)
    assert "key:\n    nested:\n        - 1\n" in out


def test_deeply_nested_sequences_stay_indented() -> None:
    """Sequence indentation holds at depth: list-of-lists and list-under-list-item."""
    out = to_indented_yaml({"rules": [{"ports": [22, 8728]}], "matrix": [[1, 2]]})
    assert yaml.safe_load(out) == {"rules": [{"ports": [22, 8728]}], "matrix": [[1, 2]]}
    # The inner sequence is indented beneath its parent key, not flush with it.
    assert "  - ports:\n      - 22\n" in out
    # Nested lists gain a level per depth.
    assert "matrix:\n  - - 1\n    - 2\n" in out


def test_top_level_list() -> None:
    """A top-level sequence serializes and round-trips."""
    out = to_indented_yaml(["a", {"b": [1]}])
    assert yaml.safe_load(out) == ["a", {"b": [1]}]


def test_handles_date_and_datetime_subclasses() -> None:
    """Tagged date/datetime subclasses (ansible-core 2.19+) serialize.

    YAML timestamps in a vars file arrive as date/datetime; data tagging wraps
    those too, and SafeDumper's exact-type representer lookup would raise.
    """

    class TaggedDate(datetime.date):
        pass

    class TaggedDateTime(datetime.datetime):
        pass

    out = to_indented_yaml(
        {
            "day": TaggedDate(2026, 6, 12),
            "at": TaggedDateTime(2026, 6, 12, 10, 30, 0),
        }
    )
    assert yaml.safe_load(out) == {
        "day": datetime.date(2026, 6, 12),
        "at": datetime.datetime(2026, 6, 12, 10, 30, 0),
    }
