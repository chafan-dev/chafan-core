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
      in
      {
        devShells.default = pkgs.mkShell {
          LOCALE_ARCHIVE =
            if pkgs.stdenv.isLinux then "${pkgs.glibcLocales}/lib/locale/locale-archive" else "";
          buildInputs = [
            pkgs.locale
            pkgs.glibcLocales

            pkgs.python312Packages.pymongo # TODO remove

            pkgs.cloudflared

            pkgs.redis

            pkgs.postgresql_14
            pkgs.python312Packages.alembic

            pkgs.python312
            pkgs.python312Packages.uvicorn
            pkgs.python312Packages.fastapi
            pkgs.python312Packages.python-dotenv
            pkgs.python312Packages.apscheduler
            pkgs.python312Packages.slowapi
            pkgs.python312Packages.shortuuid
            pkgs.python312Packages.starlette
            pkgs.python312Packages.pytz
            pkgs.python312Packages.python-jose
            pkgs.python312Packages.passlib
            pkgs.python312Packages.boto3 # S3 client
	        pkgs.python312Packages.bcrypt
            # Sentry migrate
            # https://github.com/getsentry/sentry-python/commit/570307c946020e9fefdb22904585170cd6d2717d
            pkgs.python312Packages.sentry-sdk_2
            pkgs.python312Packages.dramatiq

            pkgs.python312Packages.pydantic
            pkgs.python312Packages.pydantic-settings
            pkgs.python312Packages.email-validator

            pkgs.python312Packages.requests
            pkgs.python312Packages.arrow
            pkgs.python312Packages.redis
            pkgs.python312Packages.html2text
            pkgs.python312Packages.jinja2

            pkgs.python312Packages.jieba
            pkgs.python312Packages.whoosh

            pkgs.python312Packages.sqlalchemy
            pkgs.python312Packages.psycopg2

            pkgs.python312Packages.python-multipart
            pkgs.python312Packages.parsel

            pkgs.python312Packages.websockets
            pkgs.python312Packages.feedgen

            #pkgs.python312Packages.trio



# Required for unit test
            pkgs.python312Packages.pytest
            pkgs.python312Packages.pytest-mock
            pkgs.python312Packages.pytest-trio
            pkgs.python312Packages.httpx

# Required for static analysis (lint)
            pkgs.mypy
            pkgs.python312Packages.mypy
            pkgs.black
            pkgs.isort
            pkgs.python312Packages.flake8
          ];
        };
      }
    );

}
