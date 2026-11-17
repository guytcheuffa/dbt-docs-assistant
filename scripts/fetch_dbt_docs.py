"""Télécharge la documentation dbt (dépôt dbt-labs/docs.getdbt.com)
et copie les fichiers Markdown dans data/raw/dbt_docs/.

Prérequis : git installé.
Usage : python scripts/fetch_dbt_docs.py
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/dbt-labs/docs.getdbt.com.git"
DOCS_DIR = "website/docs"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "dbt_docs"


def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "repo"
        print("Clonage partiel du dépôt (sans les images)...")
        run(["git", "clone", "--depth", "1", "--filter=blob:none",
             "--sparse", REPO_URL, str(clone)])
        run(["git", "sparse-checkout", "set", DOCS_DIR], cwd=clone)

        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)

        src = clone / DOCS_DIR
        count = 0
        for path in src.rglob("*"):
            if path.suffix in (".md", ".mdx"):
                target = OUT / path.relative_to(src)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                count += 1
        print(f"{count} fichiers Markdown copiés dans {OUT}")


if __name__ == "__main__":
    main()