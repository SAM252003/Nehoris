.PHONY: dev install run test lint format precommit-install hooks

# Installe les dépendances Python
install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

# Alias pratique
dev: install

# Lance le backend FastAPI en dev
run:
	. .venv/bin/activate && uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# Tests (pytest)
test:
	. .venv/bin/activate && pytest -q

# Vérifications de style (ne modifie rien)
lint:
	. .venv/bin/activate && ruff check . && black --check . && isort --check-only .

# Formatage auto (modifie les fichiers)
format:
	. .venv/bin/activate && ruff check . --fix && black . && isort .

# Installe pre-commit localement
precommit-install:
	. .venv/bin/activate && pip install pre-commit && pre-commit install

# Exécute les hooks sur tout le repo (optionnel)
hooks:
	. .venv/bin/activate && pre-commit run --all-files
