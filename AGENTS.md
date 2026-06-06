<!--# cspell: ignore SSOT CMDB llms mikrotik -->
# AGENTS.md

Ensure that all practices and instructions described by
<https://raw.githubusercontent.com/ansible/ansible-creator/refs/heads/main/docs/agents.md>
are followed.

## YAML style

All playbooks, snippets, and YAML in general must be **pure YAML** with no
embedded JSON, for human readability. Use YAML-native block style throughout:

- Use block mappings and block sequences, not JSON-style inline `{}` / `[]`
  (flow) collections.
- Write multi-line strings with block scalars (`|` / `>`) rather than escaped
  one-liners.
- This applies everywhere — task args, `vars`, defaults, examples in docs and
  `argument_specs`, and module return/data structures.

```yaml
# Good — pure YAML block style
routeros_command:
  commands:
    - /ip address print
    - /system identity print

# Avoid — embedded JSON / flow style
routeros_command:
  commands: ["/ip address print", "/system identity print"]
```

## RouterOS documentation (machine-readable)

The official MikroTik RouterOS manual is published in plain formats for
retrieval pipelines, assistants, and other automated tools — not only for the
browser. Use these endpoints when you need authoritative RouterOS
configuration reference or behavior details.

| Endpoint | Purpose |
| --- | --- |
| <https://manual.mikrotik.com/llms.txt> | Index of every page (short description + link each), following the [llmstxt.org](https://llmstxt.org) convention. Read this first to discover what exists. |
| <https://manual.mikrotik.com/llms-full.txt> | The entire manual concatenated into one plain-text file, for bulk ingestion or loading a full local copy. |
| Per-page Markdown | The raw source of any page. Append `.md` to a documentation address — e.g. `https://manual.mikrotik.com/docs/authentication-authorization-accounting/certificates.md`. (Links in `llms.txt` already point at the `.md` form.) |
| <https://manual.mikrotik.com/sitemap.xml> | Standard sitemap listing every page for crawlers and indexers. The site `robots.txt` permits standard and AI crawlers. |

Common pattern: read `llms.txt` first to find the relevant pages, then fetch
the individual `.md` pages you need for detail. To pull the complete corpus in
one piece, load `llms-full.txt` instead. These files are regenerated on every
build, so they stay in step with the published pages.
