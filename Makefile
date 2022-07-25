LOCAL_DEV_PORT := 4582
LOCAL_DEV_HOST := dev.cha.fan

link-venv:
	ln -s $(shell poetry env info --path) .venv

requirements.txt: poetry.lock
	poetry export --without-hashes -f requirements.txt > requirements.txt

dev-requirements.txt: poetry.lock
	poetry export --without-hashes --dev -f requirements.txt > dev-requirements.txt

format:
	bash scripts/format.sh

check:
	bash scripts/lint.sh
	python scripts/check.py

dev-run:
	uvicorn --host $(LOCAL_DEV_HOST) --port $(LOCAL_DEV_PORT) chafan_core.app.main:app --reload

# npm install mjml -g
compile-email-templates:
	mjml chafan_core/app/email-templates/src/reset_password.mjml -o chafan_core/app/email-templates/build/reset_password.html
	mjml chafan_core/app/email-templates/src/verification_code.mjml -o chafan_core/app/email-templates/build/verification_code.html
	mjml chafan_core/app/email-templates/src/notifications.mjml -o chafan_core/app/email-templates/build/notifications.html
	mjml chafan_core/app/email-templates/src/feedback_status_update.mjml -o chafan_core/app/email-templates/build/feedback_status_update.html

reset-and-run-unit-tests:
	bash scripts/reset_app_state.sh
	bash scripts/run-unit-tests.sh

check-no-pending-change:
	git diff --exit-code
	git diff HEAD --exit-code

staging-pr: requirements.txt dev-requirements.txt check-no-pending-change
	git fetch origin
	git rebase origin/stag
	git push -f origin main
	gh pr create --base stag --title "Update stag" --fill
