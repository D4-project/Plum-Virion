# Plum-Virion

Read-only MCP interface for [Plum-Island](https://github.com/D4-project/Plum-Island).

## Status

Repository initialized with architecture guidance and configuration templates.
The MCP server, API client and configuration loader are not implemented yet.
No connection to Plum-Island is made by this scaffold.

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

Planned tools:

- `show_ip`: inspect IPv4/IPv6 observations, ports, tags and dates, with requested-hostname selection.
- `search`: use Plum's structured keyword syntax, dates and pagination.
- `token_search`: use Plum's free-text Meilisearch search.

Plum-Island owns query semantics, validation, authorization and access to stored
scan data. Virion adapts those APIs to MCP; it must not duplicate search logic,
scrape HTML, import the controller application or access its databases directly.
Required JSON endpoints and shared services may need work in Plum-Island first.
Transport choice and supported API versions remain to be agreed before implementation.

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
The future loader must reject empty credentials, use safe YAML parsing and
require HTTPS except for local loopback development. These rules are a contract,
not implemented checks at this stage. Remote MCP client authentication is a
separate design decision; these credentials must never be used as a public
shared administrator login.

## Development

Read [AGENT.md](AGENT.md) before implementation. The authoritative API contract
belongs in Plum-Island; see its [repository guidance](https://github.com/D4-project/Plum-Island/blob/main/AGENT.md)
and [search internals](https://github.com/D4-project/Plum-Island/blob/main/documentation/sysinternal/search_engine.md).
No compatible release or runnable server is claimed yet.
