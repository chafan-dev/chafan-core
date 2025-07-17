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

            pkgs.python312


          ];
        };
      }
    );

}
