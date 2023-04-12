import pytest
from pndconf.config import Configuration
from pathlib import Path


@pytest.fixture
def config():
    config_file = Path("config.ini") if Path("config.ini").exists() else Path("tests/config.ini")
    config = Configuration(".", ".", config_file=config_file,
                           pandoc_path="/usr/bin/pandoc", pandoc_version="2.14.2", no_citeproc=False,
                           csl_dir="examples/csl", templates_dir="examples/templates",
                           post_processor=None, same_output_dir=False, dry_run=False)
    return config
