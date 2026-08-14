LOCAL_DEV_PORT := 4582
LOCAL_DEV_HOST := dev.cha.fan

format:
	bash scripts/format.sh

check:
	bash scripts/static_analysis/lint.sh
	python scripts/check.py

# Report karma that disagrees with the rules in chafan_core/app/rules.py.
# Clean output means every karma-earning action is being tracked.
refresh-karmas:
	python scripts/refresh_karmas.py

refresh-karmas-apply:
	python scripts/refresh_karmas.py --apply

# Report uploaded images that no body references any more. Nothing is deleted.
upload-report:
	python scripts/upload_report.py

dev-run:
	uvicorn --host $(LOCAL_DEV_HOST) --port $(LOCAL_DEV_PORT) chafan_core.app.main:app --reload

# npm install mjml -g
compile-email-templates:
	mjml chafan_core/app/email-templates/src/reset_password.mjml -o chafan_core/app/email-templates/build/reset_password.html
	mjml chafan_core/app/email-templates/src/verification_code.mjml -o chafan_core/app/email-templates/build/verification_code.html
	mjml chafan_core/app/email-templates/src/notifications.mjml -o chafan_core/app/email-templates/build/notifications.html
	mjml chafan_core/app/email-templates/src/feedback_status_update.mjml -o chafan_core/app/email-templates/build/feedback_status_update.html
