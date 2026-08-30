"""Phase C: Origin/Proxy fail-closed — X-Forwarded-Host nur mit Trust."""
from __future__ import annotations

from types import SimpleNamespace

import web.server as server


def _req(origin: str, host: str, forwarded: str = ""):
    headers = {"origin": origin, "host": host}
    if forwarded:
        headers["x-forwarded-host"] = forwarded
    return SimpleNamespace(headers=headers, method="POST")


def test_origin_passt_zu_host(monkeypatch):
    monkeypatch.delenv("SERO_TRUST_PROXY", raising=False)
    monkeypatch.setattr(server, "PUBLIC_BASE_URL", "")
    assert server._origin_erlaubt(_req("http://192.168.2.39:3000", "192.168.2.39:3000"))


def test_forwarded_host_ohne_trust_wirkt_nicht(monkeypatch):
    monkeypatch.delenv("SERO_TRUST_PROXY", raising=False)
    monkeypatch.setattr(server, "PUBLIC_BASE_URL", "")
    # Client fälscht X-Forwarded-Host auf erlaubte Origin — Host intern anders
    assert not server._origin_erlaubt(
        _req("https://evil.example", "127.0.0.1:3000", forwarded="evil.example"))


def test_forwarded_host_mit_trust(monkeypatch):
    monkeypatch.setenv("SERO_TRUST_PROXY", "1")
    monkeypatch.setattr(server, "PUBLIC_BASE_URL", "")
    assert server._origin_erlaubt(
        _req("https://sero.example", "127.0.0.1:3000", forwarded="sero.example"))


def test_public_base_url_allowlist(monkeypatch):
    monkeypatch.delenv("SERO_TRUST_PROXY", raising=False)
    monkeypatch.setattr(server, "PUBLIC_BASE_URL", "https://app.sero.example")
    assert server._origin_erlaubt(
        _req("https://app.sero.example", "127.0.0.1:3000"))
