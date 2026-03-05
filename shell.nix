{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell rec {
  buildInputs = [
    pkgs.SDL2
    pkgs.SDL2_ttf
    pkgs.zlib
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath buildInputs}:$LD_LIBRARY_PATH"
    export LD_PRELOAD="${pkgs.SDL2}/lib/libSDL2-2.0.so.0"
  '';
}
