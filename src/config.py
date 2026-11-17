"""Réglages centraux du projet."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
VECTORSTORE = ROOT / "vectorstore"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"          # 384 dimensions, rapide sur CPU
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-12-v2"     # alternatives : BAAI/bge-reranker-base, jinaai/jina-reranker-v1-turbo-en

BATCH_SIZE = 32
PART_SIZE = 500          # nombre de passages par fichier de sauvegarde (reprise possible)
CANDIDATES_PER_RETRIEVER = 30   # candidats gardés par recherche avant fusion
RERANK_TOP = 20        # nombre de candidats envoyés au reranker
# Fournisseur du LLM (API compatible OpenAI, ex. Qwen via Alibaba Cloud Model Studio).
# Les valeurs réelles se règlent dans .env : LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
DEFAULT_LLM_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_LLM_MODEL = "qwen3.8-flash"   # nom versionné (reproductible), contrairement à l'alias "qwen-flash"
PROMPT_VERSION = "v2"     # consigne de génération (voir SYSTEM_PROMPTS dans src/generation/answer.py)
ENABLE_THINKING = False  # Qwen3.x réfléchit par défaut : coûte des tokens sans utilité pour une réponse courte et sourcée
GENERATION_MAX_TOKENS = 1000
ANSWER_CACHE = ROOT / "eval" / "results" / "answer_cache.jsonl"   # évite de repayer une même réponse
TOKEN_BUDGET = 3_000_000  # plafond de tokens facturés (entrée + sortie), compté depuis le cache ; au-delà, on refuse d'appeler l'API
TOP_K_CONTEXT = 5                      # nombre de passages envoyés au modèle
REFUSAL_PHRASE = "I don't know based on the documentation."
RRF_K = 60              # constante de la fusion Reciprocal Rank Fusion
