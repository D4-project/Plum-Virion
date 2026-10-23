"""Bounded authenticated HTTP client for the Plum Discovery API v1."""

import asyncio
import json

import httpx

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CALL_TIMEOUT = 60
OPERATIONS = frozenset(
    {"search", "token_search", "show_ip", "tags", "headers", "search_help"}
)


class PlumError(Exception):
    """Safe external failure; no server traceback, credential or raw response."""


class PlumClient:
    """One account per stdio process; credentials/tokens never leave this client."""

    def __init__(self, config, *, transport=None):
        self.config = config
        self._token = None
        self._login_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(2)
        self._http = httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            timeout=CALL_TIMEOUT,
            limits=httpx.Limits(max_connections=2),
            transport=transport,
        )

    async def close(self):
        """Release pooled connections at server shutdown."""
        await self._http.aclose()

    async def _request(self, method, path, *, data=None, token=None):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        async with self._http.stream(
            method, self.config.hostname + path, json=data, headers=headers
        ) as response:
            if response.status_code != 200:
                return response.status_code, None
            body = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=65536):
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise PlumError(
                        "Response too large; reduce limit or narrow the search"
                    )
                body.extend(chunk)
            try:
                value = json.loads(body)
            except (ValueError, UnicodeError) as error:
                raise PlumError(
                    "Plum returned invalid JSON; check the controller URL and version"
                ) from error
            if not isinstance(value, dict):
                raise PlumError("Plum returned an unsupported response")
            return response.status_code, value

    async def _authenticate(self, rejected_token=None):
        async with self._login_lock:
            if self._token is not None and self._token != rejected_token:
                return self._token
            status, data = await self._request(
                "POST",
                "/api/v1/security/login",
                data={
                    "username": self.config.username,
                    "password": self.config.password,
                    "provider": "db",
                },
            )
            token = data.get("access_token") if data else None
            if status != 200 or not isinstance(token, str) or not token:
                self._token = None
                raise PlumError(
                    "Plum authentication failed; check the dedicated account in config.yaml"
                )
            self._token = token
            return token

    async def call(self, operation, parameters=None):
        """Allowlisted read operations, one re-login on expiry, no redirects."""
        if operation not in OPERATIONS:
            raise PlumError("Unsupported operation")
        try:
            async with asyncio.timeout(CALL_TIMEOUT), self._slots:
                token = await self._authenticate()
                for attempt in range(2):
                    status, data = await self._request(
                        "GET" if operation == "search_help" else "POST",
                        "/api/v1/discovery/" + operation,
                        data=parameters if operation != "search_help" else None,
                        token=token,
                    )
                    if status == 401 and attempt == 0:
                        token = await self._authenticate(rejected_token=token)
                        continue
                    errors = {
                        400: (
                            "Invalid search or parameters; consult search_help and "
                            "use the same cursor without changing query/dates"
                        ),
                        401: "Plum authentication failed after renewal",
                        403: (
                            "Plum permission denied; check DiscoveryApi role "
                            "permissions or cursor ownership"
                        ),
                        404: (
                            "Not found; check the IP/hostname and that Plum "
                            "provides Discovery API v1"
                        ),
                        410: "Search cursor expired or invalid; restart the search",
                        413: "Request/result budget exceeded; reduce limit or narrow the search",
                        429: "Plum rate limit reached; retry later",
                        503: "Plum discovery backend unavailable or busy; retry later",
                    }
                    if status != 200:
                        raise PlumError(
                            errors.get(
                                status,
                                "Plum request failed; redirects are not followed",
                            )
                        )
                    if data.get("api_version") != 1 or not isinstance(
                        data.get("result"), dict
                    ):
                        raise PlumError(
                            "Unsupported Plum API; install a controller with Discovery API v1"
                        )
                    return data["result"]
        except (TimeoutError, httpx.TimeoutException) as error:
            raise PlumError(
                "Plum request timed out; narrow query or retry later"
            ) from error
        except httpx.HTTPError as error:
            raise PlumError(
                "Cannot connect securely to Plum; check URL, network and TLS certificate"
            ) from error
        raise PlumError("Plum request failed")
