import socket

import pytest

from btx_omni.providers.research import http


@pytest.mark.parametrize("url", ["http://example.com", "https://user:secret@example.com", "https://example.com:8443", "https://localhost", "https://a.internal", "https://example.com\\@127.0.0.1", "https://example.com/\r\nheader", "https://[fe80::1%25en0]"])
def test_public_url_rejects_unsafe_shapes(url):
    with pytest.raises(http.PublicFetchError):
        http.public_target(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "::1", "fc00::1", "fe80::1", "::ffff:127.0.0.1", "224.0.0.1"])
def test_every_resolved_address_must_be_public(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    with pytest.raises(http.PublicFetchError, match="NONPUBLIC_ADDRESS"):
        http.public_addresses("public-name.example")


class Response:
    def __init__(self, status=200, headers=None, body=b"document"):
        self.status = status
        self.headers = headers or {}
        self.body = body

    def getheaders(self):
        return self.headers.items()

    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


def transport(monkeypatch, responses):
    calls = []
    monkeypatch.setattr(http, "public_addresses", lambda host: ((socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),))

    class Connection:
        sock = None

        def __init__(self, host, addresses, deadline):
            self.host = host

        def request(self, method, path, **kwargs):
            calls.append({"host": self.host, "method": method, "path": path, **kwargs})

        def getresponse(self):
            return responses.pop(0)

        def close(self):
            pass

    monkeypatch.setattr(http, "_PinnedHTTPS", Connection)
    return calls


def test_cross_origin_redirect_drops_credentials_and_cookies(monkeypatch):
    calls = transport(monkeypatch, [Response(302, {"Location": "https://other.example/article"}), Response()])
    result = http.public_request("https://first.example", headers={"Authorization": "private", "X-API-Key": "private", "Cookie": "private", "User-Agent": "test"})
    assert result.body == b"document" and result.redirect_count == 1
    assert result.final_url == "https://other.example/article"
    assert "Cookie" not in calls[0]["headers"]
    assert calls[1]["headers"] == {"User-Agent": "test", "Accept-Encoding": "identity"}


def test_redirect_to_private_dns_is_checked_before_connect(monkeypatch):
    calls = transport(monkeypatch, [Response(302, {"Location": "https://private.example"})])

    def resolve(host):
        if host == "private.example":
            raise http.PublicFetchError("NONPUBLIC_ADDRESS")
        return ()

    monkeypatch.setattr(http, "public_addresses", resolve)
    with pytest.raises(http.PublicFetchError, match="NONPUBLIC_ADDRESS"):
        http.public_request("https://public.example")
    assert len(calls) == 1


@pytest.mark.parametrize("response", [Response(body=b"x" * 12), Response(headers={"Content-Length": "12"}), Response(headers={"Content-Encoding": "gzip"})])
def test_size_and_encoding_budgets_fail_closed(monkeypatch, response):
    transport(monkeypatch, [response])
    with pytest.raises(http.PublicFetchError):
        http.public_request("https://public.example", max_bytes=10)


def test_post_and_redirect_limit_never_repeat_a_request_body(monkeypatch):
    calls = transport(monkeypatch, [Response(307, {"Location": "/next"})])
    with pytest.raises(http.PublicFetchError, match="PUBLIC_REDIRECT_LIMIT"):
        http.public_request("https://public.example", body=b"query")
    assert len(calls) == 1


def test_pinned_connect_uses_validated_numeric_sockaddr_and_hostname_tls(monkeypatch):
    connected = []

    class Sock:
        def settimeout(self, value):
            assert value > 0

        def connect(self, address):
            connected.append(address)

        def close(self):
            pass

    class TLS:
        def wrap_socket(self, sock, *, server_hostname):
            assert server_hostname == "public.example"
            return sock

    monkeypatch.setattr(socket, "socket", lambda *args: Sock())
    connection = http._PinnedHTTPS("public.example", ((socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),), http.monotonic() + 5)
    connection._context = TLS()
    connection.connect()
    assert connected == [("93.184.216.34", 443)]
    connection.close()
