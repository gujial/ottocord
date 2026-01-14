{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    libopus
  ];

  LD_LIBRARY_PATH="${pkgs.libopus}/lib:$LD_LIBRARY_PATH";
}
