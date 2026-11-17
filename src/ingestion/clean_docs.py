"""Étape 1 : nettoie la doc dbt brute (MDX) et produit data/processed/documents.jsonl.

Ce qu'on fait :
- lit le frontmatter (titre, description, mots-clés)
- supprime les imports et les composants JSX qui polluent le texte
- garde le contenu utile des composants (onglets, blocs de version, fichiers d'exemple)
- ne touche jamais au contenu des blocs de code
- écrit un document par page, avec ses métadonnées

Usage : python -m src.ingestion.clean_docs
"""
import json
import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "dbt_docs"
SNIPPETS = ROOT / "data" / "raw" / "dbt_snippets"
OUT = ROOT / "data" / "processed" / "documents.jsonl"
BASE_URL = "https://docs.getdbt.com/"
MIN_CHARS = 200

# Noms lisibles des constantes <Constant name="..." />. À affiner si besoin.
CONSTANTS = {  # source : website/constants.js du dépôt officiel
    "git": "Git",
    "dbt_platform": "dbt platform",
    "core": "dbt v1",
    "core_v1": "dbt v1",
    "core_v2": "dbt v2",
    "fusion": "dbt v2",
    "fusion_engine": "dbt v2",
    "dbt": "dbt",
    "platform_cli": "dbt platform CLI",
    "catalog": "Catalog",
    "canvas": "Canvas",
    "insights": "Insights",
    "studio_ide": "Studio IDE",
    "mesh": "Mesh",
    "orchestrator": "Orchestrator",
    "wizard": "dbt Wizard",
    "semantic_layer": "Semantic Layer",
    "legacy_deprecation_date": "January 31, 2027",
}

SNIPPET_IMPORT = re.compile(r"""^import\s+(\w+)\s+from\s+['"]/snippets/([^'"]+)['"]""", re.M)
SNIPPET_TAG = re.compile(r"""<Snippet\s+path=["']([^"']+)["'][^>]*?/>""")
MAX_DEPTH = 3
STATS = Counter()
_snippet_cache = {}

FENCE = re.compile(r"(^```.*?^```[^\n]*$)", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]+`")
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def split_frontmatter(text):
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def version_note(attrs):
    first = re.search(r'firstVersion=["\']([^"\']+)["\']', attrs)
    last = re.search(r'lastVersion=["\']([^"\']+)["\']', attrs)
    parts = []
    if first:
        parts.append(f"dbt version {first.group(1)} and later")
    if last:
        parts.append(f"dbt version {last.group(1)} and earlier")
    return "[Applies to " + ", ".join(parts) + "]" if parts else ""


def clean_prose(seg, imports=None, refs=None):
    """Nettoie un segment HORS bloc de code.
    imports : {NomComposant: chemin_snippet} ; refs : liste des snippets à réinjecter."""
    imports = imports or {}
    refs = refs if refs is not None else []
    # protège le code en ligne
    protected = []

    def _protect(m):
        protected.append(m.group(0))
        return f"\x00{len(protected) - 1}\x00"

    seg = INLINE_CODE.sub(_protect, seg)

    def _ref(path):
        refs.append(path)
        return f"\x01{len(refs) - 1}\x01"

    for name, path in imports.items():
        seg = re.sub(rf"<{name}\b[^<>]*?/>", lambda m, pth=path: _ref(pth), seg)
    seg = SNIPPET_TAG.sub(lambda m: _ref(m.group(1)), seg)

    seg = re.sub(r"^import .*?;?\s*$", "", seg, flags=re.M)
    seg = re.sub(r"<!--.*?-->", "", seg, flags=re.S)

    # constantes
    seg = re.sub(
        r'<Constant\s+name=["\']([^"\']+)["\']\s*/>',
        lambda m: CONSTANTS.get(m.group(1), m.group(1).replace("_", " ")),
        seg,
    )
    # termes du glossaire
    seg = re.sub(r'<Term\s+id=["\']([^"\']+)["\'][^>]*?/>', lambda m: m.group(1).replace("-", " "), seg)
    seg = re.sub(r"<Term\b[^>/]*>(.*?)</Term>", r"\1", seg, flags=re.S)

    # cartes de navigation : "- titre : description (lien)"
    def _card(m):
        a = m.group(1)
        g = lambda k: (re.search(k + r'="(.*?)"\s*(?=\w+=|/?$)', a, re.S) or [None, ""])[1]
        title, body, link = g("title"), g("body"), g("link")
        body = re.sub(r"</?code>", "`", body)
        line = f"- {title}: {body}".strip()
        return line + (f" ({link})" if link else "")

    seg = re.sub(r"<Card\b(.*?)/>", _card, seg, flags=re.S)
    seg = re.sub(r"</?(div|br|span|center)\b[^>]*?/?>", "", seg)

    # fichiers d'exemple : "File: chemin" avant le code
    seg = re.sub(r'<File\s+name=["\']([^"\']+)["\'][^>]*?/>', r"File: \1", seg)
    seg = re.sub(r'<File\s+name=["\']([^"\']+)["\'][^>]*?>', r"File: \1", seg)
    seg = seg.replace("</File>", "")

    # images
    seg = re.sub(r'<Lightbox\b[^>]*?title=["\']([^"\']*)["\'][^>]*?/>', r"[Image: \1]", seg)
    seg = re.sub(r"<Lightbox\b[^>]*?/>", "", seg)

    seg = re.sub(r"<TabItem\b[^>]*?label=\{<>(.*?)</>\}[^>]*>", r"**\1**", seg, flags=re.S)

    # blocs de version : on garde le contenu et on note la portée
    seg = re.sub(
        r"<VersionBlock\b([^>]*)>",
        lambda m: version_note(m.group(1)),
        seg,
    )
    seg = seg.replace("</VersionBlock>", "")

    # sections dépliables et onglets
    seg = re.sub(
        r'<Expandable\b[^>]*?alt_header=["\']([^"\']*)["\'][^>]*>', r"**\1**", seg
    )
    seg = re.sub(r"<DetailsToggle\b[^>]*?alt_header=[\"']([^\"']*)[\"'][^>]*>", r"**\1**", seg)
    seg = re.sub(r'<TabItem\b[^>]*?label=["\']([^"\']*)["\'][^>]*>', r"**\1**", seg)

    # composants qui renvoient à d'autres fichiers (non résolus)
    seg = re.sub(r"<(Snippet|FAQ)\b[^>]*?/>", "", seg)

    # admonitions Docusaurus
    seg = re.sub(
        r"^[ \t]*:::(\w+)[ \t]*(.*)$",
        lambda m: f"**{m.group(1).capitalize()}{(': ' + m.group(2)) if m.group(2) else ''}**",
        seg,
        flags=re.M,
    )
    seg = re.sub(r"^[ \t]*:::\s*$", "", seg, flags=re.M)

    # composants PascalCase restants : on retire la balise, on garde le contenu
    seg = re.sub(r"</?[A-Z][a-z][A-Za-z0-9]*\b[^<>]*?/?>", "", seg)

    # gabarits JSX non résolus (pages d'adaptateurs) : on supprime ces paragraphes
    paras = re.split(r"\n\s*\n", seg)
    paras = [p for p in paras if "{props." not in p and "{!props" not in p]
    seg = "\n\n".join(paras)
    seg = re.sub(r"^[ \t]*(<>|</>|\)\}|\})[ \t]*$", "", seg, flags=re.M)

    # espaces
    seg = re.sub(r"[ \t]+\n", "\n", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)

    for i, p in enumerate(protected):
        seg = seg.replace(f"\x00{i}\x00", p)
    return seg


FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def split_segments(body):
    """Découpe en segments (est_code, texte) avec un automate ligne par ligne.
    Tolère les blocs de code indentés (listes) et les fences à 4 backticks."""
    segments, buf, in_code, marker = [], [], False, ""
    for line in body.split("\n"):
        m = FENCE_LINE.match(line)
        if not in_code and m:
            if buf:
                segments.append((False, "\n".join(buf)))
            buf, in_code, marker = [line], True, m.group(1)
        elif in_code and m and m.group(1)[0] == marker[0] and len(m.group(1)) >= len(marker) \
                and line.strip() == m.group(1):
            buf.append(line)
            segments.append((True, "\n".join(buf)))
            buf, in_code = [], False
        else:
            buf.append(line)
    if buf:
        segments.append((in_code, "\n".join(buf)))
    return segments


def load_snippet(path, depth):
    """Retourne le texte nettoyé d'un snippet (ou '' s'il est introuvable)."""
    path = path.replace("\\", "/").lstrip("/")
    key = (path, depth)
    if key in _snippet_cache:
        return _snippet_cache[key]
    candidates = [path] if path.endswith((".md", ".mdx")) else [path + ".md", path + ".mdx"]
    text = ""
    for c in candidates:
        f = SNIPPETS / c
        if f.exists():
            _, body = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            text = clean_body(body, depth + 1)
            STATS["snippets_injectes"] += 1
            break
    else:
        STATS["snippets_introuvables"] += 1
    _snippet_cache[key] = text
    return text


def clean_body(body, depth=0):
    imports = {n: p for n, p in SNIPPET_IMPORT.findall(body)}
    refs = []
    out = []
    for is_code, seg in split_segments(body):
        out.append(seg if is_code else clean_prose(seg, imports, refs))
    text = "\n".join(out)
    if depth < MAX_DEPTH:
        for i, path in enumerate(refs):
            text = text.replace(f"\x01{i}\x01", "\n\n" + load_snippet(path, depth) + "\n\n")
    else:
        for i in range(len(refs)):
            text = text.replace(f"\x01{i}\x01", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def url_for(rel):
    p = rel.with_suffix("").as_posix()
    if p.endswith("/index"):
        p = p[: -len("/index")]
    return BASE_URL + p


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    kept, skipped = 0, Counter()
    with OUT.open("w", encoding="utf-8") as f:
        for path in sorted(RAW.rglob("*")):
            if path.suffix not in (".md", ".mdx"):
                continue
            rel = path.relative_to(RAW)
            raw = path.read_text(encoding="utf-8", errors="replace")
            meta, body = split_frontmatter(raw)
            text = clean_body(body)
            if len(text) < MIN_CHARS:
                skipped["trop_court"] += 1
                continue
            parts = rel.parts
            doc = {
                "doc_id": rel.with_suffix("").as_posix(),
                "path": rel.as_posix(),
                "url": url_for(rel),
                "title": str(meta.get("title") or rel.stem.replace("-", " ")),
                "description": str(meta.get("description") or ""),
                "keywords": meta.get("keywords") if isinstance(meta.get("keywords"), list) else [],
                "section": parts[0],
                "subsection": parts[1] if len(parts) > 2 else "",
                "text": text,
                "n_chars": len(text),
            }
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            kept += 1
    print(f"{kept} documents écrits dans {OUT}")
    print(f"Ignorés : {dict(skipped)}")
    print(f"Snippets : {dict(STATS)}")


if __name__ == "__main__":
    main()
