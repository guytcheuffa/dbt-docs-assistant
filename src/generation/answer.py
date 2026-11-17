"""Étape 5 : réponse à une question à partir des passages retrouvés, avec citations et refus.

answer(question) -> {"answer", "refused", "sources", "passages", "usage"}
Le modèle cite ses sources avec [1], [2]... ; on les convertit en URL.
Quand les passages ne suffisent pas, il commence sa réponse par REFUSAL_PHRASE.

Le LLM est appelé via une API compatible OpenAI (Qwen par défaut). Réglages dans .env :
LLM_API_KEY, LLM_BASE_URL (optionnel), LLM_MODEL (optionnel).
Les réponses sont mises en cache sur disque : une même question avec les mêmes passages
n'est facturée qu'une fois.
"""
import hashlib
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from src import config

load_dotenv(config.ROOT / ".env")

_RULES = f"""You answer questions about dbt using ONLY the numbered documentation passages provided in the user message.

Rules:
- Use only information found in the passages. Do not use outside knowledge, even if you know the answer.
- Cite the passages that support each claim with their number in square brackets, e.g. [1] or [2][3].
- Reproduce code exactly as it appears in the passages, in fenced code blocks.
- If the passages do not contain enough information to answer, reply with exactly: "{config.REFUSAL_PHRASE}" and, optionally, one short sentence saying what is missing. Do not guess and do not cite anything in that case.
- If the passages only answer part of the question, answer that part and say what is missing.
"""
# v1 : première version ("concise") ; v2 : demande des réponses complètes (v1 rendait qwen3.8-flash trop bref)
SYSTEM_PROMPTS = {
    "v1": _RULES + "- Be concise and answer in the language of the question.",
    "v2": _RULES + ("- Answer completely: cover every part of the question and include the relevant details "
                    "found in the passages (options, defaults, examples, how to change the behavior), "
                    "without padding or repetition.\n- Answer in the language of the question."),
}
SYSTEM_PROMPT = SYSTEM_PROMPTS[config.PROMPT_VERSION]


def format_passages(hits):
    blocks = []
    for n, h in enumerate(hits, 1):
        section = " > ".join(h["heading_path"]) if h["heading_path"] else h["title"]
        blocks.append(f"[{n}] {h['title']} — {section}\nURL: {h['url']}\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def build_user_message(question, hits):
    return f"Documentation passages:\n\n{format_passages(hits)}\n\n=====\nQuestion: {question}"


class Assistant:
    def __init__(self, retriever=None, use_cache=True):
        key = os.getenv("LLM_API_KEY")
        if not key:
            raise SystemExit("LLM_API_KEY manquante : renseigne-la dans le fichier .env (voir .env.example).")
        self.model = os.getenv("LLM_MODEL", config.DEFAULT_LLM_MODEL)
        self.client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL", config.DEFAULT_LLM_BASE_URL))
        self.use_cache = use_cache
        self.cache = {}
        if use_cache and config.ANSWER_CACHE.exists():
            with config.ANSWER_CACHE.open(encoding="utf-8") as f:
                self.cache = {r["key"]: r for r in map(json.loads, f)}
        if retriever is None:
            from src.retrieval.search import Retriever
            retriever = Retriever()
        self.retriever = retriever

    def tokens_spent(self):
        """Total des tokens facturés jusqu'ici (tous les appels réels sont enregistrés dans le cache)."""
        return sum(r["usage"]["input_tokens"] + r["usage"]["output_tokens"] for r in self.cache.values())

    def chat(self, system, message, label="", model=None):
        """Appel au LLM, avec cache disque et plafond de tokens. Renvoie (texte, usage, depuis_le_cache).
        Sert à la génération des réponses et au juge de l'évaluation ; `model` remplace le modèle par défaut."""
        model = model or self.model
        key = hashlib.sha256(json.dumps([model, system, message]).encode()).hexdigest()
        if self.use_cache and key in self.cache:
            r = self.cache[key]
            return r["text"], r["usage"], True
        spent = self.tokens_spent()
        if spent >= config.TOKEN_BUDGET:
            raise SystemExit(f"Budget atteint : {spent} tokens consommés (plafond TOKEN_BUDGET = "
                             f"{config.TOKEN_BUDGET} dans config.py). Aucun appel envoyé.")
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=config.GENERATION_MAX_TOKENS,
            temperature=0,
            extra_body={"enable_thinking": config.ENABLE_THINKING},   # paramètre propre à l'API Qwen (DashScope)
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": message}],
        )
        text = (response.choices[0].message.content or "").strip()
        usage = {"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens}
        if self.use_cache:
            config.ANSWER_CACHE.parent.mkdir(parents=True, exist_ok=True)
            record = {"key": key, "model": model, "label": label, "text": text, "usage": usage}
            with config.ANSWER_CACHE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.cache[key] = record
        return text, usage, False

    def answer(self, question, mode="hybrid_rerank", k=config.TOP_K_CONTEXT, hits=None, model=None, prompt=None):
        """`hits` permet de fournir des passages déjà retrouvés ; `model` et `prompt` (v1, v2) servent à l'évaluation."""
        if hits is None:
            hits = self.retriever.retrieve(question, k=k, mode=mode)
        system = SYSTEM_PROMPTS[prompt] if prompt else SYSTEM_PROMPT
        text, usage, cached = self.chat(system, build_user_message(question, hits), label=question, model=model)
        if not text:
            text = config.REFUSAL_PHRASE + " (empty model response)"
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 1 <= int(n) <= len(hits)})
        # refus = réponse qui commence par la phrase de refus (même suivie d'une explication citée),
        # ou qui la contient sans aucune citation (le modèle la place parfois après une explication)
        refused = text.startswith(config.REFUSAL_PHRASE) or (config.REFUSAL_PHRASE in text and not cited)
        sources = [] if refused else [{"n": n, "url": hits[n - 1]["url"], "title": hits[n - 1]["title"]}
                                      for n in cited]
        return {"question": question, "answer": text, "refused": refused, "sources": sources,
                "passages": hits, "usage": usage, "cached": cached}
