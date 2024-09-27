{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixpkgs-23.url = "github:nixos/nixpkgs/nixos-22.05";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils , nixpkgs-23}: {
    devShell.x86_64-linux =
        let
            pkgs = nixpkgs.legacyPackages.x86_64-linux;
            pkgs-old = nixpkgs-23.legacyPackages.x86_64-linux;
        in pkgs.mkShell {
            buildInputs = [
            pkgs.python312
#            pkgs.poetry
            pkgs.python312Packages.uvicorn
            pkgs.python312Packages.fastapi
            pkgs.python312Packages.python-dotenv
            pkgs.python312Packages.slowapi
            pkgs.python312Packages.shortuuid
            pkgs.python312Packages.starlette
            pkgs.python312Packages.sqlalchemy
            pkgs.python312Packages.pytz
            pkgs.python312Packages.python-jose
            pkgs.python312Packages.passlib
            pkgs.python312Packages.boto3
            # Sentry migrate
            # https://github.com/getsentry/sentry-python/commit/570307c946020e9fefdb22904585170cd6d2717d
            pkgs.python312Packages.sentry-sdk_2
            pkgs.python312Packages.dramatiq

            pkgs.python312Packages.pydantic
            pkgs.python312Packages.pydantic-settings
            pkgs.python312Packages.email-validator
#            pkgs.python312Packages.alembic
#
#
#            pkgs.postgresql
            ];
        };
  };




}
