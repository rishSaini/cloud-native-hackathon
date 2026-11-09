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


def test_rum_is_off_without_settings(client_with, monkeypatch):
    monkeypatch.setattr("app.config.DASH0_RUM_ENDPOINT", "")
    assert "off" in client_with([]).get("/rum.js").text


def test_rum_turns_on_with_settings(client_with, monkeypatch):
    monkeypatch.setattr("app.config.DASH0_RUM_ENDPOINT", "https://example.invalid/v1/traces")
    monkeypatch.setattr("app.config.DASH0_RUM_TOKEN", "token-for-test")
    body = client_with([]).get("/rum.js").text
    assert "dash0('init'" in body and "https://example.invalid/v1/traces" in body
