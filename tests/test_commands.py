from pathlib import Path
import pytest
from pndconf import commands
from pndconf.commands import Commands


def test_csl_subr_should_give_correct_csl_file():
    pass


def test_template_subr_should_give_correct_csl_file():
    pass


def test_update_in_file_paths_should_update_opts_correctly():
    opts = {"csl": "ieee", "template": "reveal"}
    csl_dir = Path("./examples/csl")
    templates_dir = Path("./examples/templates")
    in_file = Path("./examples/article.md")
    commands.update_in_file_paths(opts, csl_dir, templates_dir, in_file)
    assert Path(opts["csl"]) == Path("./examples/csl/ieee.csl")
    assert Path(opts["template"]) == Path("./examples/reveal.template")
    opts = {"csl": "ieee", "template": "some_template"}
    commands.update_in_file_paths(opts, csl_dir, templates_dir, in_file)
    assert opts["template"] == "some_template"


def test_commands_should_get_correct_bibliography_opts(config):
    in_file = Path("./examples/article.md")
    text, pandoc_opts = config.read_md_file(in_file)
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = []
    bibopts = commands.get_bibliography_opts(cmd)
    assert bibopts == ("", "", "")
    config.no_citeproc = True
    commands = Commands(config, in_file, text, pandoc_opts)
    bibopts = commands.get_bibliography_opts(cmd)
    article_path = str(Path(".").absolute().joinpath("article.tex"))
    assert bibopts == ('biblatex', 'bibtex', "sed -i 's/\\\\citep{/\\\\cite{/g' " + article_path)

def test_commands_should_generate_correct_pdf_options(config):
    in_file = Path("./examples/article.md")
    text, pandoc_opts = config.read_md_file(in_file)
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = []
    pdf_file, pdfopts = commands.add_pdf_specific_options(cmd, "pdf")
    assert Path(pdf_file).name == "article.pdf"
    assert any("pdflatex" in x for x in pdfopts)
