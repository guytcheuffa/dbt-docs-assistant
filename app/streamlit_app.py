"""Étape 7 : interface locale de l'assistant.

Lancement (depuis C:\\RAG) : streamlit run app/streamlit_app.py
"""
import re
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

ROBOT = str(ROOT / "app" / "assets" / "robot.svg")

MODES = {
    "hybrid_rerank": "Hybrid + rerank",
    "hybrid": "Hybrid",
    "dense": "Semantic",
    "bm25": "Keyword",
}
SUGGESTIONS = {
    # questions du jeu d'évaluation : réponses déjà en cache, donc instantanées et gratuites
    ":material/sync: Incremental models": "How do I create an incremental model?",
    ":material/key: unique_key": "What does the unique_key config do for incremental models?",
    ":material/difference: Changed models only": "How do I run only the models that changed compared to production?",
    ":material/table_view: View vs table": "What is the difference between a view and a table materialization?",
}

st.set_page_config(page_title="dbt docs assistant", page_icon=ROBOT, layout="centered")


# --- Chargement (une seule fois par session serveur) ---------------------------------------
@st.cache_resource(show_spinner="Loading the search index…")
def load_assistant():
    from src.generation.answer import Assistant
    return Assistant()


# --- Mise en forme ----------------------------------------------------------------------------
def safe_url(url):
    """Certaines URL de la doc contiennent des espaces, qui cassent les liens Markdown."""
    return url.replace(" ", "%20")


def link_citations(text, hits):
    """Transforme [n] en lien vers la section citée, sans toucher aux blocs de code."""
    def repl(m):
        n = int(m.group(1))
        return f"[[{n}]]({safe_url(hits[n - 1]['url'])})" if 1 <= n <= len(hits) else m.group(0)

    parts = re.split(r"(```.*?```)", text, flags=re.S)
    return "".join(p if p.startswith("```") else re.sub(r"\[(\d+)\](?!\()", repl, p) for p in parts)


def section_of(hit):
    return " › ".join(hit["heading_path"]) if hit["heading_path"] else hit["title"]


def render_answer(msg):
    res = msg["res"]
    hits = res["passages"]
    if res["refused"]:
        detail = res["answer"].replace(config.REFUSAL_PHRASE, "").strip()
        st.warning(detail or "Try rephrasing, or ask about a dbt feature by name.",
                   title="The documentation doesn't cover this", icon=":material/search_off:")
    else:
        st.markdown(link_citations(res["answer"], hits))
        with st.container(border=True, gap="small"):
            st.caption("Sources")
            for s in res["sources"]:
                hit = hits[s["n"] - 1]
                st.markdown(f"`{s['n']}` [{hit['title']}]({safe_url(s['url'])}) · :gray[{section_of(hit)}]")

    with st.expander(f"{len(hits)} passages retrieved", icon=":material/description:"):
        for i, hit in enumerate(hits, 1):
            st.markdown(f"`{i}` **{hit['title']}** · :gray[{section_of(hit)}]")
            st.code(hit["text"], language="markdown", wrap_lines=True)

    usage = res["usage"]
    info = [f"{msg['seconds']:.1f} s", f"{usage['input_tokens'] + usage['output_tokens']:,} tokens",
            MODES[msg["mode"]]]
    if res["cached"]:
        info.append("from cache")
    st.caption(" · ".join(info))


# --- État -------------------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []


def new_conversation():
    st.session_state.messages = []


# --- Barre latérale ---------------------------------------------------------------------------
with st.sidebar:
    st.image(ROBOT, width=64, alt="Assistant robot")
    st.subheader("dbt docs assistant")
    st.caption("Answers questions about dbt from the official documentation, links every claim "
               "to its source and tells you when the docs don't cover something.")

    st.button("New conversation", icon=":material/edit_square:", width="stretch",
              on_click=new_conversation)

    st.space("small")
    mode = st.segmented_control("Search", list(MODES), format_func=MODES.get,
                                default="hybrid_rerank", key="mode") or "hybrid_rerank"
    k = st.slider("Passages given to the model", 3, 8, config.TOP_K_CONTEXT, key="k")

    st.space("small")
    st.caption("Evaluation · 90 questions")
    with st.container(horizontal=True):
        st.metric("Right page in top 5", "94%", border=True)
        st.metric("Correct refusals", "12/12", border=True)
    with st.container(horizontal=True):
        st.metric("Grounded answers", "75/76", border=True)
        st.metric("Expected page cited", "91%", border=True)
    st.caption("Docs: docs.getdbt.com · 1,171 pages · 8,485 passages")


# --- En-tête ----------------------------------------------------------------------------------
try:
    assistant = load_assistant()
except SystemExit as e:  # clé API manquante ou index obsolète
    st.error(str(e), title="The assistant can't start", icon=":material/error:")
    st.stop()

prompt = st.chat_input("Ask anything about dbt…", submit_mode="disable")

if not st.session_state.messages:
    with st.container(horizontal_alignment="center", gap="small"):
        st.space("medium")
        st.image(ROBOT, width=96, alt="Assistant robot")
        st.markdown("## What do you want to know about dbt?", text_alignment="center")
        st.markdown(":gray[Models, tests, materializations, the CLI, configs… Answers come straight "
                    "from docs.getdbt.com, with links to the exact section.]", text_alignment="center")
        st.space("small")
    suggestions = st.empty()
    picked = suggestions.pills("Try asking", list(SUGGESTIONS), label_visibility="collapsed")
    if picked:
        prompt = SUGGESTIONS[picked]
    if prompt:
        suggestions.empty()

# --- Historique -------------------------------------------------------------------------------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar=ROBOT):
            render_answer(msg)

# --- Nouvelle question ------------------------------------------------------------------------
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ROBOT):
        start = time.perf_counter()
        try:
            with st.status(":shimmer[Reading the docs]", type="compact") as status:
                with st.status("Searching the documentation", type="step") as step:
                    hits = assistant.retriever.retrieve(prompt, k=k, mode=mode)
                    pages = list(dict.fromkeys(h["title"] for h in hits))
                    st.caption(" · ".join(pages))
                    step.update(label=f"Found {len(hits)} relevant passages", state="complete")
                with st.status("Writing the answer", type="step") as step:
                    res = assistant.answer(prompt, hits=hits)
                    st.caption("Using only the passages above")
                    step.update(label="Answer written", state="complete")
                seconds = time.perf_counter() - start
                status.update(label=f"Read {len(set(pages))} pages in {seconds:.1f} s", state="complete")
        except SystemExit as e:  # plafond de tokens atteint
            st.error(str(e), icon=":material/error:")
            st.stop()
        except Exception as e:  # erreur réseau ou API
            st.error(f"Something went wrong while answering: {e}", icon=":material/error:")
            st.stop()

        msg = {"role": "assistant", "res": res, "seconds": seconds, "mode": mode}
        render_answer(msg)
    st.session_state.messages.append(msg)
