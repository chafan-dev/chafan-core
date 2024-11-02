{
  inputs = {
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    #nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    #nixpkgs-23.url = "github:nixos/nixpkgs/nixos-22.05";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs-unstable, flake-utils}: {
    devShell.x86_64-linux =
        let
            pkgs = nixpkgs-unstable.legacyPackages.x86_64-linux;
        in pkgs.mkShell {
            LOCALE_ARCHIVE = if pkgs.stdenv.isLinux then "${pkgs.glibcLocales}/lib/locale/locale-archive" else "";
            buildInputs = [
	    pkgs.locale
	    pkgs.glibcLocales

            pkgs.python312
#            pkgs.poetry
            pkgs.python312Packages.uvicorn
            pkgs.python312Packages.fastapi
            pkgs.python312Packages.python-dotenv
            pkgs.python312Packages.slowapi
            pkgs.python312Packages.shortuuid
            pkgs.python312Packages.starlette
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

            pkgs.python312Packages.requests
            pkgs.python312Packages.arrow
            pkgs.python312Packages.redis
            pkgs.python312Packages.html2text
            pkgs.python312Packages.jinja2
            pkgs.python312Packages.pymongo
            pkgs.python312Packages.alembic
            pkgs.redis

            pkgs.python312Packages.jieba
            pkgs.python312Packages.whoosh

            pkgs.python312Packages.sqlalchemy
            pkgs.python312Packages.psycopg2

            pkgs.python312Packages.pika
            pkgs.python312Packages.python-multipart
            pkgs.python312Packages.parsel

            pkgs.python312Packages.websockets

            pkgs.postgresql_14
           # pkgs.pgadmin4
            ];
        };
  };




}
