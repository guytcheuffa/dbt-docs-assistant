"""Télécharge les extraits partagés (website/snippets) référencés par la doc dbt.

Deux mécanismes à résoudre :
  1. import X from '/snippets/_x.md'   puis   <X />
  2. <Snippet path="nom" />

Sortie : data/raw/dbt_snippets/<chemin relatif au dossier snippets>
Usage : python scripts/fetch_dbt_snippets.py
"""
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "raw" / "dbt_docs"
OUT = ROOT / "data" / "raw" / "dbt_snippets"
RAW = "https://raw.githubusercontent.com/dbt-labs/docs.getdbt.com/current/website/snippets/"

IMPORT_RE = re.compile(r"""^import\s+\w+\s+from\s+['"]/snippets/([^'"]+)['"]""", re.M)
SNIPPET_RE = re.compile(r"""<Snippet\s+path=["']([^"']+)["']""")


def referenced():
    names = set()
    for p in DOCS.rglob("*"):
        if p.suffix not in (".md", ".mdx"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        names.update(IMPORT_RE.findall(t))
        for n in SNIPPET_RE.findall(t):
            names.add(n)
    return sorted(names)


def fetch(name):
    name = name.replace("\\", "/").lstrip("/")
    candidates = [name] if name.endswith((".md", ".mdx")) else [name + ".md", name + ".mdx"]
    for c in candidates:
        try:
            with urllib.request.urlopen(RAW + c, timeout=30) as r:
                data = r.read()
            target = OUT / c
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return name, True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            time.sleep(1.5)
            return fetch_retry(name, c)
        except Exception:
            return fetch_retry(name, c)
    return name, False


def fetch_retry(name, c, tries=3):
    for _ in range(tries):
        time.sleep(1.5)
        try:
            with urllib.request.urlopen(RAW + c, timeout=30) as r:
                data = r.read()
            target = OUT / c
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return name, True
        except Exception:
            continue
    return name, False


def main():
    names = referenced()
    print(f"{len(names)} extraits référencés")
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(fetch, names))
    ok = [n for n, s in results if s]
    ko = [n for n, s in results if not s]
    print(f"{len(ok)} téléchargés, {len(ko)} introuvables")
    for n in ko:
        print("  introuvable :", n)


if __name__ == "__main__":
    main()
