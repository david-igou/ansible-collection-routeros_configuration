"""Unit tests for the to_routeros_config filter."""

import pytest

from ansible_collections.david_igou.routeros_configuration.plugins.filter.to_routeros_config import (
    to_routeros_config,
)
from ansible.errors import AnsibleFilterError


RESULTS = [
    {
        "item": "/ip/address",
        "result": [{".id": "*1", "address": "192.168.88.1/24", "interface": "ether1"}],
    },
    {
        "item": "/interface/wireguard",
        "result": [{".id": "*2", "name": "wg0", "private-key": "SECRETKEY=="}],
    },
    {"item": "/ip/pool", "result": []},
    {"item": "/ip/dns", "skipped": True},
]


def test_shapes_into_routeros_config() -> None:
    """Each non-empty path becomes {path: {data: [...]}}."""
    out = to_routeros_config(RESULTS)
    assert out["/ip/address"] == {
        "data": [{"address": "192.168.88.1/24", "interface": "ether1"}]
    }


def test_strips_dot_id() -> None:
    """The internal .id is removed from every entry."""
    out = to_routeros_config(RESULTS)
    assert ".id" not in out["/ip/address"]["data"][0]


def test_omits_empty_and_skipped_paths() -> None:
    """Paths with no entries (or skipped) are not emitted."""
    out = to_routeros_config(RESULTS)
    assert "/ip/pool" not in out
    assert "/ip/dns" not in out


def test_secrets_included_by_default() -> None:
    """Service secrets round-trip unless redaction is requested."""
    out = to_routeros_config(RESULTS)
    assert out["/interface/wireguard"]["data"][0]["private-key"] == "SECRETKEY=="


def test_redact_blanks_sensitive_fields() -> None:
    """redact=True replaces sensitive field values."""
    out = to_routeros_config(RESULTS, redact=True)
    assert out["/interface/wireguard"]["data"][0]["private-key"] == "REDACTED"


def test_custom_sensitive_fields() -> None:
    """A caller-supplied sensitive_fields list is honoured."""
    out = to_routeros_config(RESULTS, redact=True, sensitive_fields=["interface"])
    assert out["/ip/address"]["data"][0]["interface"] == "REDACTED"
    assert out["/interface/wireguard"]["data"][0]["private-key"] == "SECRETKEY=="


def test_drops_empty_entries_keeps_real_ones() -> None:
    """Entries that normalise to nothing are dropped; real entries remain."""
    out = to_routeros_config(
        [
            {
                "item": "/ip/address",
                "result": [
                    {".id": "*1", "address": "192.168.88.1/24", "interface": "ether1"},
                    {},  # all-unset entry (api_info handle_disabled: omit)
                ],
            },
        ]
    )
    assert len(out["/ip/address"]["data"]) == 1
    assert out["/ip/address"]["data"][0]["address"] == "192.168.88.1/24"


def test_omits_paths_whose_entries_are_all_empty() -> None:
    """A path left with no real entries is omitted (e.g. all-default singleton)."""
    out = to_routeros_config(
        [
            {"item": "/system/watchdog", "result": [{}]},  # all defaults -> {}
            {"item": "/ip/pool", "result": [{".id": "*9"}]},  # only .id -> {}
        ]
    )
    assert "/system/watchdog" not in out
    assert "/ip/pool" not in out


def test_rejects_non_list() -> None:
    """A non-list input raises AnsibleFilterError."""
    with pytest.raises(AnsibleFilterError):
        to_routeros_config("not-a-list")


def test_rejects_malformed_item() -> None:
    """A result item without an 'item' key raises AnsibleFilterError."""
    with pytest.raises(AnsibleFilterError):
        to_routeros_config([{"result": []}])
