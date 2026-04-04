from __future__ import annotations

import httpx
import pytest

import backend.api.app as app_mod


def _install_host_build(tmp_path):
    dist = tmp_path / "dist-host"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Jarvin mobile shell</body></html>", encoding="utf-8")
    (assets / "main.js").write_text("console.log('jarvin');", encoding="utf-8")
    return dist


@pytest.mark.asyncio
async def test_frontend_shell_serves_host_build(monkeypatch, tmp_path):
    dist = _install_host_build(tmp_path)
    monkeypatch.setattr(app_mod, "_desktop_shell_dist_dir", lambda: dist)
    monkeypatch.setattr(app_mod.cfg.settings, "llm_auto_provision", False, raising=False)
    monkeypatch.setattr(app_mod.cfg.settings, "start_listener_on_boot", False, raising=False)

    transport = httpx.ASGITransport(app=app_mod.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False) as client:
        redirect = await client.get("/app")
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/app/"

        index = await client.get("/app/")
        assert index.status_code == 200
        assert "Jarvin mobile shell" in index.text

        asset = await client.get("/app/assets/main.js")
        assert asset.status_code == 200
        assert "console.log('jarvin');" in asset.text


@pytest.mark.asyncio
async def test_frontend_shell_reports_missing_build(monkeypatch, tmp_path):
    missing_dist = tmp_path / "does-not-exist"
    monkeypatch.setattr(app_mod, "_desktop_shell_dist_dir", lambda: missing_dist)
    monkeypatch.setattr(app_mod.cfg.settings, "llm_auto_provision", False, raising=False)
    monkeypatch.setattr(app_mod.cfg.settings, "start_listener_on_boot", False, raising=False)

    transport = httpx.ASGITransport(app=app_mod.create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/app/")
        assert response.status_code == 503
        assert "npm run build:host" in response.text
