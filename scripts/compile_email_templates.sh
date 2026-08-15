#!/usr/bin/env bash
# Compile the email templates from their .mjml sources.
#
# Needs `mjml`, which the nix devShell does not carry (nixpkgs dropped
# nodePackages.mjml): npm install -g mjml
#
# Only needed when a template changes -- the compiled HTML under build/ is
# committed, and that is what the app reads at runtime.
#
# MJML stays the authoring format for now, deliberately. Its whole job is to
# turn ~600 bytes of markup into the 5-8KB of nested tables and inline styles
# that mail clients actually render, and nobody here wants to maintain that by
# hand. The price is one global npm install for whoever edits a template, which
# is rare: these last changed in September 2024. If that ever stops being worth
# it, the move is to adopt build/*.html as the real source and delete
# src/*.mjml -- not to leave sources behind that nobody can compile.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

SRC=chafan_core/app/email-templates/src
OUT=chafan_core/app/email-templates/build

for name in reset_password verification_code notifications feedback_status_update; do
    mjml "$SRC/$name.mjml" -o "$OUT/$name.html"
done
