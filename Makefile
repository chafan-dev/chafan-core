LOCAL_DEV_PORT := 4582
LOCAL_DEV_HOST := dev.cha.fan

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
	exit 1
	bash scripts/reset_app_state.sh
	bash scripts/run-unit-tests.sh
