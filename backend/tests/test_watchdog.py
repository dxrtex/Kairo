from backend import watchdog


def test_message_names():
    assert "Täglicher Scan" in watchdog.message("Täglicher Scan", "u")["title"]
    assert "Papier-Handel" in watchdog.message("Papier-Handel Kairo / S19 / S20 / Momentum / DM (ohne echte Orders)", "u")["title"]
    assert watchdog.message("X", "https://x")["url"] == "https://x"


def test_without_secrets(monkeypatch):
    monkeypatch.delenv("PUSH_SUBS", raising=False)
    assert watchdog.main(["Täglicher Scan", "u"]) == 0


def test_message_published_without_browser_test():
    m = watchdog.message("Täglicher Scan (ohne Browser-Test veröffentlicht)", "u")
    assert "ohne App-Test" in m["title"] and "fehlgeschlagen" not in m["title"]
