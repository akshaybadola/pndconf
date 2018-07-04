# pypanprocess
Automatic conversion of markdown to various formats with pre defined settings via templates and folder watch with preview

--------

The templates in the settings/templates directory are derived from the repository <https://github.com/cgroll/pandoc_slides>

--------
## Usage

- The settings folder contains empty directories which should be populated with respective modules.
- charts.js file in settings should be replaced with the correct file.
- See `pandocwatch --help` for a list of options.
- Requires `live-server` from `nodejs` for automatic reloading of the current directory in the browser.
- Basically `live-server` injects js code which refreshes the page automatically.
- Will add more options and explanations later, with perhaps a python based version of `live-server` as it shouldn't be too difficult to implement.
