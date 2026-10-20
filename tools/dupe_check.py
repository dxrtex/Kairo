"""Prüft site/index.html auf doppelt deklarierte Funktionen (eine spätere überschreibt still die frühere)."""
import re
import sys
from pathlib import Path

s = (Path(__file__).resolve().parents[1] / "site" / "index.html").read_text(encoding="utf-8")
js = max(re.findall(r"<script(?: [^>]*)?>(.*?)</script>", s, re.S), key=len)
names = re.findall(r"^(?:async )?function (\w+)\s*\(", js, re.M)
dupes = sorted({n for n in names if names.count(n) > 1})
print("Doppelte Funktionen:", ", ".join(dupes) if dupes else "keine")
sys.exit(1 if dupes else 0)
