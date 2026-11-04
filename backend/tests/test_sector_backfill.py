from backend.sector_backfill import todo


def test_todo_largest_first_without_branch():
    rows = [{"t": "A", "mc": 5}, {"t": "B", "mc": 9}, {"t": "C", "mc": 1, "ig": "JETS"}, {"t": "D", "mc": 7}, {"t": "E"}]
    senti = {"D": {"ind": "Airlines"}}               # Branche schon bekannt → nicht erneut abfragen
    assert todo(rows, senti) == ["B", "A", "E"]
