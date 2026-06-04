#!/usr/bin/env python3
"""Discover which community.routeros api_modify paths a live CHR supports.

Connects to the molecule CHR's binary API (the SLIRP hostfwd at 127.0.0.1:8728,
admin/molecule, plaintext) and tries to read every path in the api_modify
registry. A path that reads is present on this CHR; one that errors needs a
feature/hardware/license the CHR lacks.

Classifies present paths as configurable (the registry gives them a write
mechanism: primary_keys / single_value / fixed_entries / stratify_keys) vs
read-only/status. Writes /tmp/chr_paths.json:

    {"configurable": [...], "readonly": [...], "absent": [...]}

This is a one-time discovery aid for authoring the configure_full scenario, not
part of the test suite. Run after `molecule create -s default && molecule
prepare -s default`.
"""
import json
import sys

sys.path.insert(0, "/home/igou/.ansible/collections")
from ansible_collections.community.routeros.plugins.module_utils import _api_data as m  # noqa: E402
from librouteros import connect  # noqa: E402


def writable(vd):
    return bool(
        getattr(vd, "primary_keys", None)
        or getattr(vd, "single_value", False)
        or getattr(vd, "fixed_entries", False)
        or getattr(vd, "stratify_keys", None)
    )


def main():
    api = connect(username="admin", password="molecule", host="127.0.0.1", port=8728)
    configurable, readonly, absent = [], [], []
    for tup in sorted(m.PATHS):
        path = " ".join(tup)
        vd = m.PATHS[tup].unversioned
        try:
            tuple(api.path(*tup))  # read it
        except Exception:
            absent.append(path)
            continue
        (configurable if vd and writable(vd) else readonly).append(path)
    out = {"configurable": configurable, "readonly": readonly, "absent": absent}
    with open("/tmp/chr_paths.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(
        f"configurable={len(configurable)} readonly={len(readonly)} "
        f"absent={len(absent)} (total={len(m.PATHS)}) -> /tmp/chr_paths.json"
    )


if __name__ == "__main__":
    main()
