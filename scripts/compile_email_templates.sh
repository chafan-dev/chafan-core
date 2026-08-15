#!/usr/bin/env bash
# Compile the email templates from their .mjml sources.
#
# Needs `mjml`, which the nix devShell does not carry (nixpkgs dropped
# nodePackages.mjml): npm install -g mjml
#
# Only needed when a template changes -- the compiled HTML under build/ is
# committed, and that is what the app reads at runtime.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

SRC=chafan_core/app/email-templates/src
OUT=chafan_core/app/email-templates/build

for name in reset_password verification_code notifications feedback_status_update; do
    mjml "$SRC/$name.mjml" -o "$OUT/$name.html"
done
