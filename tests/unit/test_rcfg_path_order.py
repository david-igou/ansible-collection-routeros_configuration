# Copyright (c) 2026, David Igou
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for the configure role's ``rcfg_path_order``.

``rcfg_path_order`` (``roles/configure/vars/main.yml``) is the canonical apply
order the ``configure`` role feeds to ``community.routeros.api_modify``, and the
set ``export_vars`` filters its captures through. ``api_modify`` rejects any
``path:`` that is not one of its argspec choices, so a single non-writable entry
(a read-only / ``api_info``-only container or status path) makes every captured
baseline that includes it abort on apply with
``value of path must be one of: ...``.

This pins the invariant: every entry must be writable by ``api_modify``.

The writable set is computed from the *installed* ``community.routeros`` exactly
the way ``api_modify`` builds its ``path`` choices, so the check tracks whatever
version this collection resolves against (``galaxy.yml`` floors it at ``>=3.0.0``).
A dependency bump that turns a path read-only will fail here on purpose — that is
a real drift that needs a re-audit, not a flaky test. The test skips cleanly where
``community.routeros`` is not installed rather than failing spuriously.
"""

from pathlib import Path

import pytest
import yaml

# api_modify's path-choice computation lives in community.routeros; skip (don't
# fail) when the dependency is absent.
_api_data = pytest.importorskip(
    "ansible_collections.community.routeros.plugins.module_utils._api_data"
)
_api_modify = pytest.importorskip(
    "ansible_collections.community.routeros.plugins.modules.api_modify"
)

VARS_FILE = (
    Path(__file__).resolve().parents[2]
    / "roles"
    / "configure"
    / "vars"
    / "main.yml"
)


def _api_modify_writable_paths():
    """The exact set api_modify accepts as ``path:`` (api_modify.py argspec)."""
    return {
        _api_data.join_path(path)
        for path, versioned_path_info in _api_data.PATHS.items()
        if _api_modify.has_backend(versioned_path_info)
    }


def _rcfg_path_order():
    return yaml.safe_load(VARS_FILE.read_text())["rcfg_path_order"]


def _to_api_modify(path):
    """``/interface/bridge`` -> ``interface bridge`` (api_modify's path form)."""
    return path.lstrip("/").replace("/", " ")


def test_every_rcfg_path_is_api_modify_writable():
    """No read-only / api_info-only path may sit in rcfg_path_order."""
    writable = _api_modify_writable_paths()
    non_writable = [
        path for path in _rcfg_path_order() if _to_api_modify(path) not in writable
    ]
    assert non_writable == [], (
        "rcfg_path_order contains paths community.routeros.api_modify cannot write "
        "(read-only / api_info-only); every export that captures one aborts on apply. "
        f"Drop them from roles/configure/vars/main.yml: {non_writable}"
    )


def test_rcfg_path_order_has_no_duplicates():
    """Duplicate entries would apply the same path twice in the wrong order."""
    rcfg = _rcfg_path_order()
    dupes = sorted({path for path in rcfg if rcfg.count(path) > 1})
    assert dupes == [], f"duplicate entries in rcfg_path_order: {dupes}"
