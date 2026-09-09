"""Bounded public HTTPS transport shared by collection and document research.

No environment proxies, cookies, automatic redirects or second DNS lookup at
connect time. TLS still verifies the original hostname, not the pinned address.
The worker's outer deadline also bounds OS DNS resolution, which socket timeouts
alone cannot interrupt. Errors deliberately omit URLs, headers and credentials.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit


class PublicFetchError(ValueError):
    pass


@dataclass(frozen=True)
class PublicResponse:
    status: int
    body: bytes
    headers: dict[str, str]
    final_url: str
    redirect_count: int


def public_target(url: str) -> tuple[str, str, str]:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(char) <= 32 or ord(char) == 127 for char in url) or "\\" in url:
        raise PublicFetchError("INVALID_PUBLIC_URL")
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            raise PublicFetchError("HTTPS_PUBLIC_TARGET_REQUIRED")
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii")
        if not host or "%" in host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise PublicFetchError("NONPUBLIC_TARGET")
        authority = f"[{host}]" if ":" in host else host
        canonical = urlunsplit(("https", authority, parsed.path or "/", parsed.query, ""))
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        return host, path, canonical
    except (UnicodeError, ValueError) as error:
        if isinstance(error, PublicFetchError):
            raise
        raise PublicFetchError("INVALID_PUBLIC_URL") from None


def public_addresses(host: str) -> tuple[tuple, ...]:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except TimeoutError:
        raise
    except OSError:
        raise PublicFetchError("PUBLIC_DNS_FAILED") from None
    if not addresses:
        raise PublicFetchError("PUBLIC_DNS_EMPTY")
    for _family, _kind, _protocol, _name, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise PublicFetchError("NONPUBLIC_ADDRESS")
    return tuple(addresses)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, addresses: tuple[tuple, ...], deadline: float):
        super().__init__(host, port=443, timeout=max(0.01, deadline - monotonic()), context=ssl.create_default_context())
        self.addresses = addresses
        self.deadline = deadline

    def connect(self) -> None:
        for family, kind, protocol, _name, address in self.addresses:
            remaining = self.deadline - monotonic()
            if remaining <= 0:
                raise PublicFetchError("PUBLIC_FETCH_DEADLINE")
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(remaining)
                sock.connect(address)  # validated numeric sockaddr; no DNS rebinding
                remaining = self.deadline - monotonic()
                if remaining <= 0:
                    sock.close()
                    raise PublicFetchError("PUBLIC_FETCH_DEADLINE")
                sock.settimeout(remaining)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except TimeoutError:
                sock.close()
                raise
            except OSError:
                sock.close()
        raise PublicFetchError("PUBLIC_CONNECT_FAILED")


def public_request(url: str, *, headers: dict[str, str] | None = None,
                   body: bytes | None = None, timeout: float = 15,
                   max_bytes: int = 2_000_000, max_redirects: int = 3) -> PublicResponse:
    if not 0 < timeout <= 30 or not 0 < max_bytes <= 5_000_000 or not 0 <= max_redirects <= 3:
        raise PublicFetchError("INVALID_FETCH_BUDGET")
    deadline = monotonic() + timeout
    outgoing = {key: value for key, value in (headers or {}).items() if key.lower() not in {"host", "cookie", "connection", "accept-encoding"}}
    outgoing["Accept-Encoding"] = "identity"
    previous_host = None
    for redirects in range(max_redirects + 1):
        host, path, canonical = public_target(url)
        if previous_host and previous_host != host:
            outgoing = {key: value for key, value in outgoing.items() if key.lower() in {"accept", "accept-encoding", "user-agent"}}
        addresses = public_addresses(host)
        if monotonic() >= deadline:
            raise PublicFetchError("PUBLIC_FETCH_DEADLINE")
        connection = _PinnedHTTPS(host, addresses, deadline)
        try:
            connection.request("POST" if body is not None else "GET", path, body=body, headers=outgoing)
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise PublicFetchError("PUBLIC_FETCH_DEADLINE")
            if connection.sock:
                connection.sock.settimeout(remaining)
            response = connection.getresponse()
            response_headers = {key.lower(): value for key, value in response.getheaders()}
            if response.status in {301, 302, 303, 307, 308}:
                if body is not None or redirects == max_redirects or not response_headers.get("location"):
                    raise PublicFetchError("PUBLIC_REDIRECT_LIMIT")
                previous_host = host
                url = urljoin(canonical, response_headers["location"])
                continue  # next target gets full protocol, DNS and address gates
            if response_headers.get("content-encoding", "identity").lower() not in {"identity", ""}:
                raise PublicFetchError("UNSUPPORTED_CONTENT_ENCODING")
            length = response_headers.get("content-length")
            if length and (not length.isdigit() or int(length) > max_bytes):
                raise PublicFetchError("PUBLIC_RESPONSE_TOO_LARGE")
            chunks = []
            size = 0
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise PublicFetchError("PUBLIC_FETCH_DEADLINE")
                if connection.sock:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise PublicFetchError("PUBLIC_RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            return PublicResponse(response.status, b"".join(chunks), response_headers, canonical, redirects)
        except TimeoutError:
            raise
        except (OSError, http.client.HTTPException):
            raise PublicFetchError("PUBLIC_TRANSPORT_FAILED") from None
        finally:
            connection.close()
    raise PublicFetchError("PUBLIC_REDIRECT_LIMIT")
