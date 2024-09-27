{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }: {
    devShell.x86_64-linux =
        let
            pkgs = nixpkgs.legacyPackages.x86_64-linux;
        in pkgs.mkShell {
            buildInputs = [
            pkgs.python311
#            pkgs.poetry
            pkgs.python311Packages.uvicorn
            pkgs.python311Packages.fastapi
            pkgs.python311Packages.python-dotenv
            pkgs.python311Packages.sentry-sdk
            pkgs.python311Packages.slowapi
            pkgs.python311Packages.shortuuid
            pkgs.python311Packages.starlette
            pkgs.python311Packages.sqlalchemy
            pkgs.python311Packages.pytz
            pkgs.python311Packages.python-jose
            pkgs.python311Packages.passlib
            pkgs.python311Packages.boto3
            pkgs.python311Packages.sentry-sdk
            pkgs.python311Packages.dramatiq


            pkgs.python311Packages.pydantic
            pkgs.python311Packages.email-validator
#            pkgs.python312Packages.alembic
#
#
#            pkgs.postgresql
            ];
        };
  };




}
