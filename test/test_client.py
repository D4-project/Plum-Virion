"""Private configuration and authentication against mocked HTTP only."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from plum_virion.client import PlumClient, PlumError
from plum_virion.config import Config, ConfigError, load_config

CONFIG = Config("https://plum.example.invalid", "reader", "test-secret")


class ConfigTest(unittest.TestCase):
    """Validate URL and credentials without echoing their contents."""

    def test_private_config_urls_and_redaction(self):
        """Accept HTTPS and loopback development; keep passwords out of repr."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.yaml"
            for hostname in (
                CONFIG.hostname,
                "https://plum.example.invalid/prefix/",
                "http://localhost:5001",
                "http://127.0.0.1:5000",
                "http://[::1]:5001",
            ):
                path.write_text(
                    json.dumps(
                        {
                            "hostname": hostname,
                            "username": "reader",
                            "password": "test-secret",
                        }
                    )
                )
                path.chmod(0o600)
                config = load_config(path)
                self.assertEqual(config.hostname, hostname.rstrip("/"))
                self.assertNotIn("test-secret", repr(config))

    def test_invalid_config_rejected_without_echoing_secrets(self):
        """Reject executable YAML, bad types/URLs and group-readable secrets."""
        cases = [
            "!!python/object/apply:os.system [echo test-secret]",
            "[]",
            "not: [valid",
            "x" * 16385,
        ]
        for url in (
            "http://remote.example",
            "https://reader:test-secret@plum.example",
            "file:///tmp/a",
            "https://plum.example/?token=test-secret",
            "https://plum.example/#test-secret",
            "https://plum.example:bad",
            "http://10.0.0.1",
            "https://plum.example/with space",
        ):
            cases.append(
                json.dumps(
                    {"hostname": url, "username": "reader", "password": "test-secret"}
                )
            )
        cases.extend(
            [
                json.dumps(
                    {"hostname": CONFIG.hostname, "username": "reader", "password": 123}
                ),
                json.dumps(
                    {
                        "hostname": CONFIG.hostname,
                        "username": "",
                        "password": "test-secret",
                    }
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.yaml"
            for raw in cases:
                path.write_text(raw)
                path.chmod(0o600)
                with self.assertRaises(ConfigError) as error:
                    load_config(path)
                self.assertNotIn("test-secret", str(error.exception))
            if os.name == "posix":
                path.chmod(0o644)
                with self.assertRaisesRegex(ConfigError, "chmod 600"):
                    load_config(path)
        with self.assertRaisesRegex(ConfigError, "--config"):
            load_config("/nonexistent/virion-test.yaml")


class ClientTest(unittest.IsolatedAsyncioTestCase):
    """Use the real auth state machine with HTTPX MockTransport."""

    def make_client(self, handler):
        """Close connections even after failed assertions."""
        client = PlumClient(CONFIG, transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.close)
        return client

    async def test_forwarding_login_reuse_and_expiry(self):
        """Keep syntax intact and renew once on 401, never on permission denial."""
        calls, logins = [], []

        def handler(request):
            calls.append(request)
            if request.url.path.endswith("/login"):
                logins.append(1)
                self.assertEqual(json.loads(request.content)["password"], "test-secret")
                return httpx.Response(200, json={"access_token": str(len(logins))})
            return httpx.Response(200, json={"api_version": 1, "result": {"ok": True}})

        client = self.make_client(handler)
        query = "(port:443 OR port:80) AND tag:lang:php"
        await client.call("search", {"query": query, "from_ts": 100, "to_ts": 200})
        await client.call("search_help")
        self.assertEqual(len(logins), 1)
        self.assertEqual(json.loads(calls[1].content)["query"], query)
        self.assertEqual(calls[1].headers["Authorization"], "Bearer 1")
        reads = []

        def expired(request):
            if request.url.path.endswith("/login"):
                return httpx.Response(200, json={"access_token": "renewed"})
            reads.append(request.headers["Authorization"])
            return httpx.Response(
                401 if len(reads) == 1 else 403, json={"message": "test-secret"}
            )

        with self.assertRaisesRegex(PlumError, "permission denied"):
            await self.make_client(expired).call("show_ip", {"ip": "2001:db8::1"})
        self.assertEqual(len(reads), 2)

    async def test_concurrent_calls_share_login(self):
        """Prevent concurrent initial tool calls from creating a login stampede."""
        logins = []

        async def handler(request):
            if request.url.path.endswith("/login"):
                logins.append(1)
                await asyncio.sleep(0)
                return httpx.Response(200, json={"access_token": "shared"})
            return httpx.Response(200, json={"api_version": 1, "result": {}})

        client = self.make_client(handler)
        await asyncio.gather(*(client.call("search_help") for _ in range(5)))
        self.assertEqual(len(logins), 1)

    async def test_errors_redirection_and_contract_validation(self):
        """Discard raw upstream errors and never forward auth to redirects."""

        def status_handler(response_status):
            seen = []

            def handler(request):
                seen.append(str(request.url))
                if request.url.path.endswith("/login"):
                    return httpx.Response(200, json={"access_token": "token"})
                return httpx.Response(
                    response_status,
                    headers={"Location": "https://evil.invalid"},
                    json={"message": "test-secret"},
                )

            return handler, seen

        for code in (400, 401, 403, 404, 410, 413, 429, 500, 503, 302):
            handler, seen = status_handler(code)

            with self.assertRaises(PlumError) as error:
                await self.make_client(handler).call("search_help")
            self.assertNotIn("test-secret", str(error.exception))
            self.assertTrue(all("evil.invalid" not in url for url in seen))
        for response in (
            httpx.Response(200, content=b"bad JSON"),
            httpx.Response(200, json=[]),
            httpx.Response(200, json={"api_version": 2, "result": {}}),
        ):

            def malformed_handler(request, response=response):
                return (
                    httpx.Response(200, json={"access_token": "token"})
                    if request.url.path.endswith("/login")
                    else response
                )

            with self.assertRaises(PlumError):
                await self.make_client(malformed_handler).call("search_help")

    async def test_timeout_budget_and_allowlist(self):
        """Reject arbitrary paths and large transfers; show safe timeout errors."""

        def timeout(request):
            raise httpx.ReadTimeout("test-secret", request=request)

        with self.assertRaisesRegex(PlumError, "timed out"):
            await self.make_client(timeout).call("search_help")

        def handler(request):
            return (
                httpx.Response(200, json={"access_token": "token"})
                if request.url.path.endswith("/login")
                else httpx.Response(200, content=b"x" * 101)
            )

        client = self.make_client(handler)
        with self.assertRaisesRegex(PlumError, "Unsupported operation"):
            await client.call("/targets_api/bulk_import")
        with (
            patch("plum_virion.client.MAX_RESPONSE_BYTES", 100),
            self.assertRaisesRegex(PlumError, "too large"),
        ):
            await client.call("search_help")
