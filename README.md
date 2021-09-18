# pandocwatch

Pandoc configuration manager, file watcher and document generator.

Automatic conversion of markdown to various formats with pre defined settings
via templates and folder watch with preview.

## Usage

- `pndconf -i ".md" -g pdf,html,reveal` watches all
  directories and subdirectories for `.md` files and
  compiles if it notices any changes to `pdf`, `html` and `reveal` format.
- `pandoc` is used for generation and should be in the current path. `pandoc`
  switches for the formats are stored in a configuration file in `ini` format.
- If no config file is provided then a default config is used.
- See `pndconf --help` for a list of options.

## Pandoc installation

- You can either install `pandoc` through your distribution
  - `apt-get install pandoc,{-citeproc,-data}` for debian/ubuntu
  - `dnf install pandoc,{-citeproc,-common}` for fedora
  See your distribution packages for others.
- You can also install via `cabal-install` for the latest version
  - `pandoc-2.14.2` has citeproc inbuilt and has some extra features which are quite useful
  - While installing via `cabal-install` it's preferable to update
    your haskell compiler first to the latest version.
  - For GHC use at least `8.8.2`
    - Then do `cabal update cabal-install` first
    - Then `cabal update pandoc`

## Templates and CSL

`pandoc` comes with default templates which can be used for simple document
generation. However if you need to customize it you can search for other
templates. Path to the templates directory can be specified via
`--templates-dir` option.

A compendium of citation styles is available at [styles](https://github.com/citation-style-language/styles "Citation Styles").
You can either clone the repository or download the required style
files to a directory and give the path to `pndconf` with `--csl-dir`.

## Todo

- [X] Remove the settings folder from the repo. It should be standalone.
- [X] Remove blog generator as that's a separate repo now.
- [ ] Clean the code up
- [ ] Issue warning when incompatible options are used --biblatex and
  pandoc-citeproc conflict e.g.

