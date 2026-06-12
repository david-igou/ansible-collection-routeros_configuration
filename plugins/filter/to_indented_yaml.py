# Copyright (c) 2026, David Igou
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serialize data to YAML with indented block sequences (ansible-lint clean)."""

from __future__ import absolute_import, annotations, division, print_function


__metaclass__ = type  # pylint: disable=C0103

import datetime

import yaml

from ansible.errors import AnsibleFilterError


DOCUMENTATION = """
    name: to_indented_yaml
    author: David Igou (@david-igou)
    version_added: "0.0.8-alpha"
    short_description: Serialize data to YAML with indented block sequences.
    description:
      - Like C(to_nice_yaml), but block sequences are indented beneath their
        parent key instead of PyYAML's default flush (indentless) style.
      - The flush style trips ansible-lint's C(yaml[indentation]) rule on
        every list-bearing key, so files written with C(to_nice_yaml) fail
        lint above the C(min) profile. Output from this filter passes the
        default profile, making it suitable for vars files committed to a
        linted inventory repository (the C(export_vars) role uses it for its
        captures).
      - Keys are emitted sorted and unicode is preserved, matching
        C(to_nice_yaml) layout in everything except sequence indentation.
    options:
      _input:
        description: The data structure to serialize.
        type: raw
        required: true
      indent:
        description: Number of spaces per indentation level.
        type: int
        default: 2
"""

EXAMPLES = """
- name: Write a captured routeros_config as lint-clean YAML
  ansible.builtin.copy:
    content: "{{ {'routeros_config': routeros_config} | david_igou.routeros_configuration.to_indented_yaml }}"
    dest: "{{ inventory_dir }}/host_vars/{{ inventory_hostname }}.yml"
    mode: "0600"
"""

RETURN = """
  _value:
    description: The YAML document as a string, ending in a single newline.
    type: str
"""


class _IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences beneath their parent key.

    PyYAML emits block sequences indentless by default (the dash flush with
    the parent key); forcing indentless=False here produces the indented form
    yamllint's indentation rule expects.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _to_plain(value):
    """Recursively coerce tagged scalars/containers to plain Python types.

    Values arriving through Jinja templating on ansible-core 2.19+ are
    data-tagging subclasses of str/int/float (and Ansible's own wrappers on
    older cores). yaml.SafeDumper looks representers up by exact type, so any
    subclass raises RepresenterError — normalize to builtins first.
    """
    if isinstance(value, dict):
        return {_to_plain(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    # bool before int: bool is an int subclass.
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    # datetime before date: datetime is a date subclass.
    if isinstance(value, datetime.datetime):
        return datetime.datetime(*value.timetuple()[:6], value.microsecond, value.tzinfo)
    if isinstance(value, datetime.date):
        return datetime.date(value.year, value.month, value.day)
    if isinstance(value, bytes):
        return bytes(value)
    return value


def to_indented_yaml(data, indent=2):
    """Serialize data to YAML with indented block sequences.

    Args:
        data: the data structure to serialize.
        indent: spaces per indentation level (default 2).

    Returns:
        str: the YAML document, keys sorted, sequences indented.
    """
    try:
        return yaml.dump(
            _to_plain(data),
            Dumper=_IndentedDumper,
            indent=indent,
            allow_unicode=True,
            default_flow_style=False,
            # PyYAML's current default, but sorted keys are part of this
            # filter's documented contract — pin it.
            sort_keys=True,
        )
    except yaml.YAMLError as exc:
        raise AnsibleFilterError(
            "to_indented_yaml failed to serialize input: %s" % exc
        ) from exc


class FilterModule:
    """filter plugin."""

    def filters(self):
        """Map filter names to functions."""
        return {"to_indented_yaml": to_indented_yaml}
