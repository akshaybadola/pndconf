# pypanprocess
Automatic conversion of markdown to various formats with pre defined settings via templates and folder watch with preview

--------

The templates in the settings/templates directory are derived from the repository <https://github.com/cgroll/pandoc_slides>

--------
## Usage

- `./pandocwatch.py -i ".md,.template" -g pdf,blog,reveal` watches all
  directories and subdirectories for `.md` and `.template` files and
  compiles if it notices any changes to `pdf`, `blog` and `reveal` format.
- `pandoc` is used for generation and should be in the current
  path. `pandoc` switches for the formats are stored in `config.ini`.
- The settings folder contains empty directories which should be populated with respective modules.
- charts.js file in settings should be replaced with the correct file.
- `csl` files, according to the styles required should be procured and put in the settings/csl directory.
- See `pandocwatch --help` for a list of options.
- Requires `live-server` from `nodejs` for automatic reloading of the current directory in the browser.
- Basically `live-server` injects js code which refreshes the page automatically.
- Will add more options and explanations later, with perhaps a python based version of `live-server` as it shouldn't be too difficult to implement.
- **Still need to fix the paths so there may be issues right now**
