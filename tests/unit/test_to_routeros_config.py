# Copyright (c) 2026, David Igou
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the to_routeros_config filter."""

import copy
import re

import pytest

from ansible_collections.david_igou.routeros_configuration.plugins.filter.to_routeros_config import (
    _is_sensitive,
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


def test_strips_volatile_fields_per_path() -> None:
    """Per-path volatile fields are removed, leaving real config."""
    out = to_routeros_config(
        [
            {
                "item": "/system/clock",
                "result": [
                    {
                        "date": "2026-06-08",
                        "time": "15:00:00",
                        "time-zone-name": "America/New_York",
                    }
                ],
            }
        ],
        volatile_fields={"/system/clock": ["date", "time"]},
    )
    assert out["/system/clock"]["data"] == [{"time-zone-name": "America/New_York"}]


def test_volatile_strip_can_empty_and_drop_path() -> None:
    """A path left empty after volatile stripping is omitted."""
    out = to_routeros_config(
        [{"item": "/system/clock", "result": [{"date": "2026-06-08", "time": "15:00:00"}]}],
        volatile_fields={"/system/clock": ["date", "time"]},
    )
    assert "/system/clock" not in out


def test_ordered_paths_get_order_and_purge() -> None:
    """Order-sensitive paths are emitted with order and purge true."""
    out = to_routeros_config(
        [
            {
                "item": "/ip/firewall/filter",
                "result": [{".id": "*1", "chain": "input", "action": "accept"}],
            }
        ],
        ordered_paths=["/ip/firewall/filter"],
    )
    assert out["/ip/firewall/filter"]["order"] is True
    assert out["/ip/firewall/filter"]["purge"] is True
    assert out["/ip/firewall/filter"]["data"] == [{"chain": "input", "action": "accept"}]


def test_ordered_paths_get_content_for_valid_round_trip() -> None:
    """Ordered paths carry content so configure's purge+order is api_modify-valid.

    api_modify rejects handle_absent_entries=remove (from purge) combined with
    handle_entries_content=ignore (configure's default) on these paths, so the
    capture MUST pin content or every ordered path is DOA against configure.
    """
    out = to_routeros_config(
        [{"item": "/ip/firewall/filter", "result": [{".id": "*1", "chain": "input"}]}],
        ordered_paths=["/ip/firewall/filter"],
    )
    assert out["/ip/firewall/filter"]["content"] == "remove_as_much_as_possible"


def test_ordered_content_is_configurable() -> None:
    """The emitted content value can be overridden."""
    out = to_routeros_config(
        [{"item": "/ip/firewall/filter", "result": [{"chain": "input"}]}],
        ordered_paths=["/ip/firewall/filter"],
        ordered_content="remove",
    )
    assert out["/ip/firewall/filter"]["content"] == "remove"


def test_unordered_paths_have_no_order_purge_or_content() -> None:
    """Paths not in ordered_paths carry none of order/purge/content."""
    out = to_routeros_config(
        [{"item": "/ip/address", "result": [{"address": "192.168.88.1/24"}]}],
        ordered_paths=["/ip/firewall/filter"],
    )
    assert "order" not in out["/ip/address"]
    assert "purge" not in out["/ip/address"]
    assert "content" not in out["/ip/address"]


def test_redact_covers_suffix_matched_fields() -> None:
    """Default redaction matches by suffix, not a fixed name list.

    pre-shared-key (WireGuard peers) and l2tp-secret-style names were missed
    by the original seven-name exact-match list.
    """
    out = to_routeros_config(
        [
            {
                "item": "/interface/wireguard/peers",
                "result": [
                    {"name": "peer1", "preshared-key": "PSK==", "public-key": "PUB=="}
                ],
            }
        ],
        redact=True,
    )
    peer = out["/interface/wireguard/peers"]["data"][0]
    assert peer["preshared-key"] == "REDACTED"
    # A peer's public key is required config, not key material — must survive
    # so the capture still round-trips.
    assert peer["public-key"] == "PUB=="


def test_input_not_mutated_by_redact() -> None:
    """Redaction works on copies; the registered results keep their values."""
    original = copy.deepcopy(RESULTS)
    to_routeros_config(RESULTS, redact=True)
    assert RESULTS == original


def test_rejects_non_list() -> None:
    """A non-list input raises AnsibleFilterError."""
    with pytest.raises(AnsibleFilterError):
        to_routeros_config("not-a-list")


def test_rejects_malformed_item() -> None:
    """A result item without an 'item' key raises, naming the element index."""
    with pytest.raises(AnsibleFilterError, match="result 1"):
        to_routeros_config([{"item": "/ip/address", "result": []}, {"result": []}])


def test_rejects_non_dict_entry() -> None:
    """A non-dict entry raises a clear error naming the path, not a traceback."""
    with pytest.raises(AnsibleFilterError, match="/ip/address"):
        to_routeros_config([{"item": "/ip/address", "result": ["not-a-dict"]}])


def test_rejects_duplicate_path() -> None:
    """A repeated path raises instead of silently overwriting the earlier capture."""
    with pytest.raises(AnsibleFilterError, match="repeats path"):
        to_routeros_config(
            [
                {"item": "/ip/address", "result": [{"address": "192.168.88.1/24"}]},
                {"item": "/ip/address", "result": [{"address": "10.0.0.1/24"}]},
            ]
        )


def test_default_redaction_pins_against_api_metadata() -> None:
    """Every secret-looking writable field in community.routeros is redacted.

    Enumerates field names from the installed community.routeros _api_data the
    same way test_rcfg_path_order pins writable paths: any field whose name
    contains key/secret/password/passphrase must either be matched by the
    default redaction heuristic or be explicitly listed here as a reviewed
    non-secret. A dependency bump that introduces a new secret field the
    heuristic misses fails here on purpose.
    """
    _api_data = pytest.importorskip(
        "ansible_collections.community.routeros.plugins.module_utils._api_data"
    )

    # Reviewed non-secrets: settings, sizes, intervals, identifiers and name
    # references that merely contain a secret-ish word.
    known_not_secret = {
        "aaa.password-format",  # /interface/wifi setting
        "allow-sharedkey",  # wireless boolean
        "ft-r0-key-lifetime",  # 802.11r timer
        "group-key-update",  # WPA rekey interval
        "host-key-size",  # SSH key size setting
        "key-chain",  # RIP key-chain name reference
        "key-id",  # NTP key identifier
        "key-size",  # certificate key size
        "key-usage",  # certificate usage flags
        "lacp-user-key",  # bonding LACP integer
        "minimum-password-length",  # /user settings policy
        "password-format",  # hotspot/wifi setting
        "public-key",  # WireGuard peer public key
        "security.ft-r0-key-lifetime",  # dotted wifi variant
        "security.group-key-update",  # dotted wifi variant
        "security.multi-passphrase-group",  # group name reference
    }

    field_names = set()
    for _path, api in _api_data.PATHS.items():
        specs = []
        if api.unversioned is not None:
            specs.append(api.unversioned)
        if api.versioned is not None:
            for _ver, _op, spec in api.versioned:
                if not isinstance(spec, str):
                    specs.append(spec)
        for spec in specs:
            if spec.fully_understood and spec.fields:
                field_names.update(spec.fields)

    secret_like = {
        name
        for name in field_names
        if re.search(r"key|secret|password|passphrase", name)
    }
    missed = sorted(
        name
        for name in secret_like - known_not_secret
        if not _is_sensitive(name, None)
    )
    assert not missed, (
        "secret-looking fields not covered by default redaction "
        "(add to the filter's sensitive sets or review into known_not_secret): %s"
        % missed
    )
