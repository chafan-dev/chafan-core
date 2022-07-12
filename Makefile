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
	python app/tools/check.py
