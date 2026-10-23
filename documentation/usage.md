# Installation, usage and operations

## Controller preparation

Deploy Plum-Island with Discovery API v1. It is introduced on `main` after
v0.2610.0; Virion checks the versioned response rather than assuming a release
is compatible. The authoritative [API contract](https://github.com/D4-project/Plum-Island/blob/main/documentation/discovery.md)
defines endpoints, permissions and date semantics. A sibling source checkout is
not evidence that the deployed controller provides this API.

Synchronize roles in Plum-Island with:

```sh
.venv/bin/python tools/initial_setup.py --roles-only
```

Create/use a dedicated database-authenticated Plum account. The bundled Read
Only role includes Discovery permissions after synchronization; a custom role
needs these permissions on `DiscoveryApi`: `can_search`, `can_token_search`,
`can_show_ip`, `can_tags`, `can_headers`, `can_search_help`. The MCP does not use
scanner `AGENT_KEY` credentials. No schema migration or index rebuild is needed.

## Local setup and Codex

Python 3.11+ and `venv` are required. From the Virion checkout, run
`bash install.sh --codex` to install the package and register it with Codex.
Without registration use `bash install.sh`. Installation preserves an existing
`config.yaml`; an absent file is created from the sample with mode 600.

Set these three quoted strings in your ignored `config.yaml`:

```yaml
hostname: "https://plum.example.org"
username: "virion-reader"
password: "replace-with-your-account-password"
```

The hostname is the Plum-Island **base URL**, including scheme, optional port
and deployment prefix. HTTPS is required except on localhost/loopback IPv4/IPv6.
Embedded URL credentials, query strings and fragments are rejected. Configuration
is limited to 16 KiB, exact keys and nonempty strings. Keep it private:

```sh
chmod 600 config.yaml
.venv/bin/plum-virion --config config.yaml --check-config
.venv/bin/plum-virion --config config.yaml --check
```

`--check-config` performs no network request. `--check` authenticates and reads
the deployed query help; success proves access to that operation, not to every
other tool. Each operation is independently checked by FAB. Neither check
registers the server in Codex; use `bash install.sh --codex` or the command below.

For manual Codex registration, use absolute paths for your actual checkout:

```sh
codex mcp add plum-virion -- /absolute/path/Plum-Virion/.venv/bin/plum-virion --config /absolute/path/Plum-Virion/config.yaml
codex mcp list
```

The installer uses this same [documented stdio registration](https://developers.openai.com/codex/mcp/).
It refuses to replace an existing `plum-virion` entry. To relocate or replace
it, run `codex mcp remove plum-virion`, then rerun registration. Restart Codex
after changing its server configuration. Credentials stay in the private YAML;
the registered command contains only the executable and config path.

Other clients can launch the same executable with `--config /absolute/path/config.yaml`.
No HTTP MCP listener or inbound firewall opening is required. Network egress is
only to the configured Plum HTTPS endpoint; no direct Kvrocks/Meilisearch access,
scanner execution, DNS lookups or WHOIS/PDNS enrichment is performed by Virion.

## Tool workflow

| Tool | Purpose | Continuation |
| --- | --- | --- |
| `search_help` | Deployed fields, modifiers, Boolean grammar, examples and limits | None |
| `list_tags` | Active-rule tags in all namespaces; optional prefix such as `lang:` | `next_offset` |
| `list_headers` | Collected names, presence queries and optional value-query prefixes | `next_offset` |
| `search` | Structured Plum syntax, UTC epoch dates or `since:N` | `next_cursor` |
| `token_search` | Free-text Meilisearch ranked raw hits | `next_offset` |
| `show_ip` | Stored IPv4/IPv6 scan evidence for the selected requested hostname | `next_offset` |

Discover syntax/catalogues before inventing filters. The tag list describes
active SQL rules, not observed hosts or per-tag scan counts. Header collection
settings do not guarantee that historical data was indexed with those settings.
`collect_value: false` means presence searches only; a header value query would
not be supported by collection. No parser or catalogue is copied into Virion.

Example structured tool arguments:

```json
{"query": "(domain_requested:example.org OR port:443) AND tag:lang:php", "limit": 25}
```

Search uses the controller's adaptive backward `last_seen` windows. Even an
empty page can have a continuation. Continue with just
`{"cursor": "<next_cursor>"}` and optionally `limit` until `next_cursor` is null.
The cursor fixes query/dates and the authenticated principal; do not change
them mid-search. It expires after one hour. Tokens contain signed, not encrypted,
search state; keep them private. Indexing during pagination can change results.
Dates/defaults and matching remain those of the controller. This differs from
the full interval-overlap scope of exports; do not describe paged discovery as
an exhaustive full-history export.

Token search takes plain text, with no date filtering or substring guarantee.
The controller forwards the query to Meilisearch. The index's ranking, matching
and pagination cap apply; one last empty page may be needed to finish.

`show_ip` defaults to IP-only scans. Its `requested_hostnames` catalogue lets
the caller choose a specific hostname and retrieve that group's history.
Without dates it uses full group history; explicit dates select overlapping
observation intervals. Latest observations come first. Tags are computed on
scan UIDs; a multi-port report's tags need not describe each individual port.
Missing raw documents retain their UID metadata and warning.

Results are structured JSON. Banners, certificates and all collected scan text
are untrusted evidence; MCP instructions explicitly tell the consuming model
not to treat those values as instructions or executable commands. Historical
observations do not establish current exposure.

## Bounds and errors

Initial client budgets are two concurrent calls, 60 seconds per complete call
(including authentication/renewal), at most 2 MiB per upstream response and
256 KiB per tool result. The server rejects oversized results explicitly;
narrow the query or reduce page size. There is no silent result truncation.
These defaults are conservative, not a production performance claim.

MCP schemas enforce integer limits: search/token/IP pages 1..100, catalogues
1..500; IP/token offsets 0..10,000, catalogue offsets 0..1,000,000. The controller
also bounds search continuation history and request size. A model may need a
narrower scope instead of downloading a whole index. Client cancellation cannot
guarantee cancellation of work already executing on the controller.

Authentication is lazy and uses Plum's existing login endpoint. A 401 causes
one coordinated token renewal; forbidden requests are not retried. Redirects
are never followed. TLS verification is enabled; HTTP proxy environment variables
are not inherited. Install private CA trust through the runtime's trusted CA
configuration rather than disabling verification.

| Failure | Action |
| --- | --- |
| Virion absent from `/mcp` | Check `codex mcp list`; register, then restart Codex |
| Config missing/empty/insecure permissions | Fill YAML, pass absolute `--config`, run `chmod 600` |
| Authentication failed | Check dedicated Plum account and password |
| Permission denied | Grant only the needed `DiscoveryApi` read permissions |
| Missing endpoint/version | Update Plum-Island to Discovery API v1 |
| Invalid query/parameters | Use `search_help`; check schema and dates |
| Cursor expired/invalid | Restart the search |
| Response/request too large | Reduce limit or narrow dates/criteria |
| Backend busy/unavailable | Check controller/Kvrocks/Meilisearch and retry later |
| Timeout/TLS/network failure | Check endpoint/certificate/network; narrow expensive queries |

Operational messages go to stderr; stdout is exclusively MCP protocol traffic.
Passwords, bearer tokens and raw upstream error bodies are not logged or returned.

## Development and rollback

Follow [AGENT.md](../AGENT.md), including Black, compilation, Pylint, docstrings,
tests and release-note updates. `test/run_all.py` uses mocked HTTP and a real
MCP stdio subprocess against a disposable loopback server. It requires subprocess
and loopback bind permissions. It does not read the operator's real config.

Rollback/uninstall: `codex mcp remove plum-virion`, stop running stdio processes,
and revoke the dedicated Plum user's Discovery permissions. The package can be
uninstalled using `.venv/bin/python -m pip uninstall plum-virion`. Preserve or
securely remove local credentials according to your normal procedures. No stored
scan data or schema changes need rollback.
