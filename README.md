# Plum-Virion

Read-only MCP interface for [Plum-Island](https://github.com/D4-project/Plum-Island).

Exposes stored host observations to Codex and other MCP clients over stdio.
Requires Python 3.11+ and a Plum-Island controller with **Discovery API v1**
(added on `main` after v0.2610.0). Earlier releases alone do not provide this API.

## Architecture

```text
LLM / MCP client
       |
Plum-Virion (separate process and repository)
       |
Authenticated Plum-Island JSON API
       |
Shared Plum-Island search and IP-detail services
       |
Kvrocks / Meilisearch
```

Tools:

- `show_ip`: inspect IPv4/IPv6 observations, ports, tags and dates, with requested-hostname selection.
- `search`: use Plum's structured keyword syntax, dates and pagination.
- `token_search`: use Plum's free-text Meilisearch search.
- `list_tags`: discover active-rule tags in all namespaces and their query terms.
- `list_headers`: discover collected HTTP headers and which support value searches.
- `search_help`: retrieve current keywords, syntax, examples and limits from Plum.

Plum-Island owns query semantics, validation, authorization and access to stored
scan data. Virion adapts those APIs to MCP; it must not duplicate search logic,
scrape HTML, import the controller application or access its databases directly.
The API contract is maintained in Plum-Island's
[Discovery guide](https://github.com/D4-project/Plum-Island/blob/main/documentation/discovery.md).

## Install and register in Codex

Clone the repository and register it:

```sh
git clone https://github.com/D4-project/Plum-Virion.git
cd Plum-Virion
bash install.sh --codex
```

This creates `.venv`, installs the package, creates a private placeholder config
if absent and registers `plum-virion` using absolute executable/config paths.
Existing local configuration and existing Codex registration are preserved;
the installer stops if that registration already exists. No credentials are put
in Codex's configuration. Without Codex registration, run `bash install.sh`.

Fill `config.yaml`, then validate it and check controller access:

```sh
.venv/bin/plum-virion --config config.yaml --check-config
.venv/bin/plum-virion --config config.yaml --check
codex mcp list
```

`--check` verifies controller access; it does not register the MCP. Use
`--codex` or manual registration from the usage guide. Check `codex mcp list`,
restart Codex and open `/mcp` to confirm availability. Example request:

> Use Plum-Virion to list PHP-related tags and searchable HTTP headers, find
> matching hosts in example.org, then inspect the latest evidence for one IP.

Codex CLI registration follows the [official MCP documentation](https://developers.openai.com/codex/mcp/).
See [installation, usage and troubleshooting](documentation/usage.md) for manual
registration, controller permissions, pagination and removal.

## Configuration

Use a local `config.yaml` beside this README:

```yaml
hostname: "https://plum.example.invalid"
username: ""
password: ""
```

`hostname` is the full **Plum-Island base URL**, including scheme and optional
port, not the MCP listener address. The credentials belong to a dedicated
Plum-Island account with only the required read permissions; they are not
credentials for authenticating clients to an HTTP MCP server.

`config.yaml.sample` is tracked; `config.yaml` is ignored. The initial local
configuration contains placeholders only. For a fresh checkout, copy the sample
without overwriting an existing configuration:

```sh
cp -n config.yaml.sample config.yaml
chmod 600 config.yaml
```

Quote credentials as YAML strings. Never commit credentials or bearer tokens.
The loader rejects empty credentials, unsafe URLs and group/world-readable
configuration on POSIX. It uses safe YAML parsing and requires HTTPS except for
loopback development. TLS verification stays enabled and redirects are refused.
The MCP transport is stdio; the launching local process controls client access.

## Development

Read [AGENT.md](AGENT.md) before modifying code. The authoritative API contract
belongs in Plum-Island; see its [repository guidance](https://github.com/D4-project/Plum-Island/blob/main/AGENT.md)
and [search internals](https://github.com/D4-project/Plum-Island/blob/main/documentation/sysinternal/search_engine.md).

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python test/run_all.py
.venv/bin/black --workers 1 plum_virion test
.venv/bin/python -m compileall -q plum_virion test
PYLINTHOME=/tmp/pylint .venv/bin/pylint plum_virion test
```

Tests use mocked HTTP and a disposable loopback controller, including an actual
MCP stdio subprocess. They require permission to bind loopback sockets and
launch subprocesses; they never use the local configuration or production data.
