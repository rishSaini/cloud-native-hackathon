def test_health_reports_es_up(client_with):
    resp = client_with([]).get("/health")
    assert resp.status_code == 200
    assert resp.json()["elasticsearch"] == "up"


def test_search_returns_hits(client_with):
    resp = client_with([{"title": "eBPF 101"}]).get("/api/search", params={"q": "ebpf"})
    body = resp.json()
    assert body["total"] == 1
    assert body["hits"][0]["title"] == "eBPF 101"


def test_search_rejects_empty_query(client_with):
    assert client_with([]).get("/api/search", params={"q": ""}).status_code == 422


def test_probes_do_not_need_elasticsearch(client_with):
    client = client_with([])
    assert client.get("/healthz").text == "ok\n"
    assert client.get("/readyz").text == "ok\n"


def test_page_shows_version(client_with, monkeypatch):
    monkeypatch.setattr("app.config.APP_VERSION", "abc1234")
    assert "version abc1234" in client_with([]).get("/").text


def test_static_serves_frontend_assets(client_with):
    resp = client_with([]).get("/static/css/tokens.css")
    assert resp.status_code == 200
    assert "--paper" in resp.text


def test_static_missing_file_is_404(client_with):
    client = client_with([])
    assert client.get("/static/nope.js").status_code == 404
    # Percent-encoded dots: httpx would strip plain "../" before sending, so this is
    # the form that actually reaches StaticFiles' containment check. The first line
    # proves it does: dots that stay inside the folder still serve the file.
    assert client.get("/static/css/%2e%2e/css/tokens.css").status_code == 200
    assert client.get("/static/%2e%2e/%2e%2e/backend/app/config.py").status_code == 404
    assert client.get("/static/css/%2e%2e/%2e%2e/%2e%2e/backend/app/config.py").status_code == 404


def test_rum_is_off_without_settings(client_with, monkeypatch):
    monkeypatch.setattr("app.config.DASH0_RUM_ENDPOINT", "")
    assert "off" in client_with([]).get("/rum.js").text


def test_rum_turns_on_with_settings(client_with, monkeypatch):
    monkeypatch.setattr("app.config.DASH0_RUM_ENDPOINT", "https://example.invalid/v1/traces")
    monkeypatch.setattr("app.config.DASH0_RUM_TOKEN", "token-for-test")
    body = client_with([]).get("/rum.js").text
    assert "dash0('init'" in body and "https://example.invalid/v1/traces" in body
