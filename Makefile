LOCAL_DEV_PORT := 4582
LOCAL_DEV_HOST := dev.cha.fan

link-venv:
	ln -s $(shell poetry env info --path) .venv

requirements.txt: poetry.lock
	poetry export --without-hashes -f requirements.txt > requirements.txt

dev-requirements.txt: poetry.lock
	poetry export --without-hashes --dev -f requirements.txt > dev-requirements.txt

format:
	bash scripts/format-imports.sh
	bash scripts/format.sh

check:
	bash scripts/lint.sh
	python scripts/check.py

dev-run:
	uvicorn --host $(LOCAL_DEV_HOST) --port $(LOCAL_DEV_PORT) chafan_core.app.main:app --reload
