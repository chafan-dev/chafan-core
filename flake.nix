{
  inputs = {
    nixpkgs-25.url = "github:nixos/nixpkgs/nixos-25.05";
    #nixpkgs-24.url = "github:nixos/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs =
    {
      self,
      nixpkgs-25,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs-25.legacyPackages.${system};
        pythonEnv = pkgs.python312.withPackages (ps: [
          ps.alembic
          ps.uvicorn
          ps.fastapi
          ps.python-dotenv
          ps.apscheduler
          ps.slowapi
          ps.shortuuid
          ps.starlette
          ps.pytz
          ps.python-jose
          ps.passlib
          ps.boto3 # S3 client
          ps.bcrypt
          ps.dramatiq
          ps.sentry-sdk

          ps.pydantic
          ps.pydantic-settings
          ps.email-validator

          ps.requests
          ps.arrow
          ps.redis
          ps.html2text
          ps.jinja2

          ps.jieba
          ps.whoosh

          ps.sqlalchemy
          ps.psycopg2

          ps.python-multipart
          ps.parsel

          ps.websockets
          ps.feedgen

          # Required for unit test
          ps.pytest
          ps.pytest-mock
          ps.pytest-trio
          ps.httpx

          # Required for static analysis (lint)
          ps.mypy
          ps.flake8
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          LOCALE_ARCHIVE =
            if pkgs.stdenv.isLinux then "${pkgs.glibcLocales}/lib/locale/locale-archive" else "";
          buildInputs = [
            pkgs.locale
            pkgs.glibcLocales

            pkgs.cloudflared

            pkgs.redis

            pkgs.postgresql_14

            pythonEnv

            pkgs.black
            pkgs.isort
          ];
        };
      }
    );

}
