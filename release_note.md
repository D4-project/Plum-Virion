# Unreleased

- Initial read-only stdio MCP server with structured search, token search and
  IPv4/IPv6 scan evidence, plus deployed tag/header catalogues and query help.
- Require Plum Discovery API v1; preserve controller query and hostname scopes.
- Add private YAML configuration, authenticated HTTP with one token renewal,
  bounded calls/results and explicit errors. No credentials in Codex config.
- Add `bash install.sh --codex` and CLI connection/config checks; document
  explicit registration and troubleshooting when Virion is absent from `/mcp`.
- Adopt Plum-Island coding/documentation requirements and protocol/auth/installer tests.
