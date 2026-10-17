{
  description = "math-aware-source-digest: verified source entries from research papers";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/55bfb4d7437bd4e09ab7cba58a43bd68eb310044";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
            pkgs.gh
            pkgs.poppler-utils
            pkgs.pandoc
          ];
          env = {
            UV_PYTHON = "${python}/bin/python3.12";
            UV_PYTHON_DOWNLOADS = "never";
          };
        };
      });
}
