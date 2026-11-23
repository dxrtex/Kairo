def test_push_position_message_once_per_day():
    from backend import push
    ps = {"asof": "2027-01-05", "sell": [{"t": "X", "why": ["stop"]}], "buy": [{"t": "A", "earn": True}]}
    sent = {}
    m = push.position_message("2027-01-05", sent, ps)
    assert len(m) == 1 and "Verkaufen: X (Stop)" in m[0]["body"] and "Kaufen: A ⚠︎Zahlen" in m[0]["body"]
    assert push.position_message("2027-01-05", sent, ps) == []
    assert push.position_message("2027-01-06", {}, {"asof": "2027-01-06", "sell": [], "buy": []}) == []
