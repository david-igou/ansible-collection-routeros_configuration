"""Unit tests for the to_indented_yaml filter."""

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
