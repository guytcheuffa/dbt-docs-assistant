"""Pose une question à l'assistant : python scripts/ask.py "how do I make an incremental model?" """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.generation.answer import Assistant

if len(sys.argv) < 2:
    sys.exit('Usage : python scripts/ask.py "votre question"')

assistant = Assistant()
res = assistant.answer(" ".join(sys.argv[1:]))
print("\n" + res["answer"])
if res["refused"]:
    print("\n(refus : les passages ne suffisent pas)")
else:
    print("\nSources :")
    for s in res["sources"]:
        print(f"  [{s['n']}] {s['url']}")
print(f"\n({res['usage']['input_tokens']} tokens en entrée, {res['usage']['output_tokens']} en sortie"
      f"{', réponse en cache' if res['cached'] else ''})")
print(f"(total consommé : {assistant.tokens_spent()} tokens sur un plafond de {config.TOKEN_BUDGET})")
