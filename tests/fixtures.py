import pytest
from pndconf.config import Configuration
from pathlib import Path


@pytest.fixture
def config():
    config_file = Path("config.ini") if Path("config.ini").exists() else Path("tests/config.ini")
    config = Configuration(None, Path("."),
                           config_file=config_file,
                           pandoc_path=Path("/usr/bin/pandoc"),
                           pandoc_version="2.14.2",
                           no_citeproc=False,
                           csl_dir=Path("examples/csl"),
                           templates_dir=Path("examples/templates"),
                           post_processor=None,
                           same_pdf_output_dir=False,
                           dry_run=False)
    return config
