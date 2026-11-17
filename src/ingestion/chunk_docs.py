"""Étape 2 : découpe les documents nettoyés en passages (chunks).

Règles :
- on coupe d'abord par titres Markdown (les '#' dans les blocs de code sont ignorés)
- un bloc de code n'est jamais coupé en plein milieu s'il tient dans la limite
  et reste collé à la phrase d'introduction qui le précède ("File: ...", "...:")
- taille cible ~MAX_TOKENS ; les petits passages sont fusionnés avec leur voisin
- chaque passage garde le chemin de titres, l'URL (avec ancre) et le titre de la page

Les tailles sont mesurées avec une estimation simple (mots + ponctuation), sans
dépendance externe. Elle est proche du nombre de tokens d'un modèle courant.

Usage : python -m src.ingestion.chunk_docs
"""
import json
import re
import statistics
from pathlib import Path

from src.ingestion.clean_docs import split_segments

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "processed" / "documents.jsonl"
OUT = ROOT / "data" / "processed" / "chunks.jsonl"

MAX_TOKENS = 420   # taille cible d'un passage
MIN_TOKENS = 60    # en dessous, on fusionne avec un voisin
HARD_MAX = 700     # au-delà, un bloc est coupé de force
MERGE_CEILING = 600
OVERLAP_MAX = 60   # recouvrement : dernier paragraphe de texte s'il est court

TOKEN_RE = re.compile(r"\w+|[^\w\s]")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
CUSTOM_ID_RE = re.compile(r"\s*\{#([\w\-]+)\}\s*$")
FENCE_OPEN_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})(.*)$")


def ntok(text):
    return len(TOKEN_RE.findall(text))


def slugify(title):
    s = re.sub(r"[`*_]", "", title).lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)
    return re.sub(r"[\s]+", "-", s).strip("-")


# ---------- 1. documents -> blocs --------------------------------------------

def to_blocks(text):
    """Transforme le texte en liste de blocs :
    ('heading', niveau, titre, ancre) | ('para', texte) | ('code', texte)"""
    blocks = []
    for is_code, seg in split_segments(text):
        if is_code:
            blocks.append(("code", seg.strip("\n")))
            continue
        for para in re.split(r"\n\s*\n", seg):
            para = para.strip("\n")
            if not para.strip():
                continue
            lines = para.split("\n")
            buf = []
            for line in lines:
                m = HEADING_RE.match(line)
                if m:
                    if buf:
                        blocks.append(("para", "\n".join(buf)))
                        buf = []
                    title = m.group(2)
                    cid = CUSTOM_ID_RE.search(title)
                    anchor = cid.group(1) if cid else None
                    title = CUSTOM_ID_RE.sub("", title).strip()
                    blocks.append(("heading", len(m.group(1)), title, anchor or slugify(title)))
                else:
                    buf.append(line)
            if buf:
                blocks.append(("para", "\n".join(buf)))
    return blocks


# ---------- 2. découpe des blocs trop gros ------------------------------------

def split_code(code, limit):
    """Coupe un bloc de code trop long aux lignes vides (ou à défaut aux lignes),
    en rouvrant la clôture avec le même langage."""
    lines = code.split("\n")
    first = lines[0]
    m = FENCE_OPEN_RE.match(first)
    indent, fence, info = (m.group(1), m.group(2), m.group(3)) if m else ("", "```", "")
    body = lines[1:-1] if len(lines) > 1 and lines[-1].strip().startswith(fence[0] * 3) else lines[1:]
    pieces, cur, cur_t = [], [], 0
    for line in body:
        t = ntok(line) + 1
        boundary = (line.strip() == "" and cur_t >= limit * 0.6)
        if cur and (cur_t + t > limit or boundary):
            pieces.append(cur)
            cur, cur_t = [], 0
            if boundary:
                continue
        cur.append(line)
        cur_t += t
    if cur:
        pieces.append(cur)
    return ["\n".join([f"{indent}{fence}{info}"] + p + [f"{indent}{fence}"]) for p in pieces]


def split_prose(text, limit):
    """Coupe un paragraphe trop long : par lignes, puis par phrases."""
    lines = text.split("\n")
    units = []
    for line in lines:
        if ntok(line) > limit:
            units.extend(re.split(r"(?<=[.!?])\s+", line))
        else:
            units.append(line)
    pieces, cur, cur_t = [], [], 0
    for u in units:
        t = ntok(u)
        if cur and cur_t + t > limit:
            pieces.append("\n".join(cur))
            cur, cur_t = [], 0
        cur.append(u)
        cur_t += t
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def is_intro(text):
    """Paragraphe d'introduction d'un bloc de code (à garder collé au code)."""
    t = text.strip()
    return t.startswith("File:") or t.endswith(":") or (ntok(t) <= 40 and t.endswith(("below", "following")))


def to_units(section_blocks):
    """Regroupe les blocs d'une section en unités insécables (intro + code)."""
    units, i = [], 0
    while i < len(section_blocks):
        kind, text = section_blocks[i]
        if kind == "para" and i + 1 < len(section_blocks) and section_blocks[i + 1][0] == "code" and is_intro(text):
            units.append([("para", text), ("code", section_blocks[i + 1][1])])
            i += 2
        else:
            units.append([(kind, text)])
            i += 1
    # une unité trop grosse est découpée
    out = []
    for u in units:
        t = sum(ntok(x[1]) for x in u)
        if t <= HARD_MAX:
            out.append(u)
            continue
        for kind, text in u:
            if ntok(text) <= HARD_MAX:
                out.append([(kind, text)])
            elif kind == "code":
                out.extend([[("code", p)] for p in split_code(text, MAX_TOKENS)])
            else:
                out.extend([[("para", p)] for p in split_prose(text, MAX_TOKENS)])
    return out


# ---------- 3. sections -> passages -------------------------------------------

def build_sections(blocks):
    """[(chemin_de_titres, ancre, [blocs])] en suivant la hiérarchie des titres."""
    sections, stack = [], []   # stack : [(niveau, titre, ancre)]
    cur_blocks, cur_path, cur_anchor = [], [], ""
    for b in blocks:
        if b[0] == "heading":
            if cur_blocks:
                sections.append((cur_path, cur_anchor, cur_blocks))
            _, level, title, anchor = b
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title, anchor))
            cur_path = [s[1] for s in stack]
            cur_anchor = anchor
            cur_blocks = []
        else:
            cur_blocks.append(b)
    if cur_blocks:
        sections.append((cur_path, cur_anchor, cur_blocks))
    return sections


def chunk_section(path, anchor, blocks):
    units = to_units(blocks)
    chunks, cur, cur_t, last_prose = [], [], 0, None
    for u in units:
        ut = sum(ntok(x[1]) for x in u)
        if cur and cur_t + ut > MAX_TOKENS:
            chunks.append("\n\n".join(cur))
            cur, cur_t = [], 0
            if last_prose and ntok(last_prose) <= OVERLAP_MAX and u[0][0] == "para":
                cur, cur_t = [last_prose], ntok(last_prose)   # recouvrement
        for kind, text in u:
            cur.append(text)
        cur_t += ut
        prose = [x[1] for x in u if x[0] == "para"]
        last_prose = prose[-1] if prose and u[-1][0] == "para" else None
    if cur:
        chunks.append("\n\n".join(cur))
    return [{"heading_path": path, "anchor": anchor, "text": c} for c in chunks]


def merge_small(chunks):
    """Fusionne les passages trop petits avec le précédent (ou le suivant)."""
    out = []
    for c in chunks:
        c["n_tokens"] = ntok(c["text"])
        if out and c["n_tokens"] < MIN_TOKENS and out[-1]["n_tokens"] + c["n_tokens"] <= MERGE_CEILING:
            prev = out[-1]
            label = c["heading_path"][-1] if c["heading_path"] and c["heading_path"] != prev["heading_path"] else ""
            sep = f"\n\n#### {label}\n\n" if label else "\n\n"
            prev["text"] += sep + c["text"]
            prev["n_tokens"] = ntok(prev["text"])
        else:
            out.append(c)
    # un tout premier passage minuscule est fusionné avec le suivant
    if len(out) >= 2 and out[0]["n_tokens"] < MIN_TOKENS and out[0]["n_tokens"] + out[1]["n_tokens"] <= MERGE_CEILING:
        nxt = out[1]
        label = nxt["heading_path"][-1] if nxt["heading_path"] and nxt["heading_path"] != out[0]["heading_path"] else ""
        sep = f"\n\n#### {label}\n\n" if label else "\n\n"
        out[0]["text"] += sep + nxt["text"]
        out[0]["n_tokens"] = ntok(out[0]["text"])
        out[0]["anchor"] = out[0]["anchor"]
        del out[1]
    return out


def chunk_document(doc):
    blocks = to_blocks(doc["text"])
    chunks = []
    for path, anchor, sec_blocks in build_sections(blocks):
        chunks.extend(chunk_section(path, anchor, sec_blocks))
    chunks = merge_small(chunks)
    result = []
    for i, c in enumerate(chunks):
        header = " > ".join([doc["title"]] + c["heading_path"])
        url = doc["url"] + (f"#{c['anchor']}" if c["anchor"] else "")
        result.append({
            "chunk_id": f"{doc['doc_id']}::{i:03d}",
            "doc_id": doc["doc_id"],
            "url": url,
            "title": doc["title"],
            "section": doc["section"],
            "subsection": doc["subsection"],
            "heading_path": c["heading_path"],
            "text": c["text"],
            "text_for_embedding": f"{header}\n\n{c['text']}",
            "n_tokens": c["n_tokens"],
            "has_code": "```" in c["text"] or "~~~" in c["text"],
        })
    return result


def main():
    n_docs, all_chunks = 0, []
    with IN.open(encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            n_docs += 1
            all_chunks.extend(chunk_document(doc))
    # dédoublonnage : un même texte (extraits réutilisés) n'est indexé qu'une fois,
    # on garde la liste des autres pages qui le contiennent
    seen, unique = {}, []
    for c in all_chunks:
        key = c["text"].strip()
        if key in seen:
            if c["url"] not in seen[key]["also_at"] and len(seen[key]["also_at"]) < 10:
                seen[key]["also_at"].append(c["url"])
            continue
        c["also_at"] = []
        seen[key] = c
        unique.append(c)
    print(f"doublons retirés : {len(all_chunks) - len(unique)}")
    all_chunks = unique
    with OUT.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    sizes = sorted(c["n_tokens"] for c in all_chunks)
    q = lambda p: sizes[min(len(sizes) - 1, int(len(sizes) * p))]
    print(f"{n_docs} documents -> {len(all_chunks)} passages dans {OUT}")
    print(f"taille (estim. tokens) : médiane {statistics.median(sizes):.0f}, "
          f"p10 {q(0.10)}, p90 {q(0.90)}, p99 {q(0.99)}, max {sizes[-1]}")
    print(f"avec code : {sum(c['has_code'] for c in all_chunks)}")


if __name__ == "__main__":
    main()
