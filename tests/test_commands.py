from pathlib import Path
import random
import pytest
import re
from pndconf import commands
from pndconf.commands import Commands
from pndconf.config import read_md_file_with_header


def test_csl_subr_should_give_correct_csl_file():
    pass


def test_template_subr_should_give_correct_csl_file():
    pass


def test_commands_generates_only_for_given_filetypes(config):
    in_file = Path("./examples/article.md")
    text, pandoc_opts = read_md_file_with_header(in_file)
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = commands.build_commands()
    filetypes = ['blog', 'html', 'reveal', 'latex', 'tex', 'pdf', 'beamer']
    assert set(cmd.keys()) == set(filetypes)
    num_choices = random.randint(1, len(filetypes)-1)
    chosen = random.choices(filetypes, k=num_choices)
    config._filetypes = chosen
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = commands.build_commands()
    assert set(cmd.keys()) == set(chosen)


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
    text, pandoc_opts = read_md_file_with_header(in_file)
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
    text, pandoc_opts = read_md_file_with_header(in_file)
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = []
    pdfopts = commands.add_pdf_specific_options(cmd, "pdf")
    pdf_file = commands.pdf_out_file
    assert Path(pdf_file).name == "article.pdf"
    assert any("pdflatex" in x for x in pdfopts)


def test_commands_should_give_correct_pdf_generation_command_with_citeproc(config):
    in_file = Path("./examples/article.md")
    root_dir = config.output_dir
    stem = in_file.stem
    out_file = str(root_dir.joinpath(stem + "." + config.conf['pdf']['-o']))
    text, pandoc_opts = read_md_file_with_header(in_file)
    config._filetypes = ["pdf"]
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = commands.build_commands()
    pdf_cmd = cmd['pdf']['command']
    assert re.match(r"^" + str(config.pandoc_path), pdf_cmd[0])
    assert re.match(r".+--citeproc.+", pdf_cmd[0])
    assert re.match(r".+-o " + out_file, pdf_cmd[0])
    out_dir = f"{root_dir.joinpath(stem)}_files"
    assert pdf_cmd[1] == f"cd {root_dir} && mkdir -p {out_dir}"
    assert pdf_cmd[2] == f"rm {out_dir}/*"
    assert pdf_cmd[3] == f"cd {root_dir} && pdflatex -file-line-error -output-directory {out_dir} -interaction=nonstopmode --synctex=1 {out_file}"
    config.same_pdf_output_dir = True
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = commands.build_commands()
    pdf_cmd = cmd['pdf']['command']
    assert pdf_cmd[1].strip() == f"cd {in_file.parent.absolute()}"
    assert pdf_cmd[2] == f"cd {in_file.parent.absolute()} && pdflatex -file-line-error -interaction=nonstopmode --synctex=1 {in_file.parent.absolute().joinpath(Path(out_file).name)}"


def test_commands_should_give_correct_pdf_generation_command_with_bibtex(config):
    in_file = Path("./examples/article.md")
    root_dir = config.output_dir
    stem = in_file.stem
    out_file = str(root_dir.joinpath(stem + "." + config.conf['pdf']['-o']))
    text, pandoc_opts = read_md_file_with_header(in_file)
    config._filetypes = ["pdf"]
    config.no_citeproc = True
    commands = Commands(config, in_file, text, pandoc_opts)
    cmd = commands.build_commands()
    pdf_cmd = cmd['pdf']['command']
    assert re.match(r"^" + str(config.pandoc_path), pdf_cmd[0])
    assert re.match(r".+-o " + out_file, pdf_cmd[0])
    out_dir = f"{root_dir.joinpath(stem)}_files"
    assert pdf_cmd[1] == "sed -i 's/\\\\citep{/\\\\cite{/g' " + out_file
    assert pdf_cmd[2] == f"cd {root_dir} && mkdir -p {out_dir}"
    assert pdf_cmd[3] == f"rm {out_dir}/*"
    pdflatex = f"cd {root_dir} && pdflatex -file-line-error -output-directory {out_dir} -interaction=nonstopmode --synctex=1 {out_file}"
    assert pdf_cmd[4] == pdflatex
    bib_file = str(in_file.absolute()).replace(".md", ".bib")
    assert pdf_cmd[5] == f"cd {root_dir} && cp {bib_file} {out_dir}/"
    assert pdf_cmd[6] == f"cd {out_dir} && bibtex {stem}"
    final_pdflatex = f"cd {out_dir} && pdflatex -file-line-error -output-directory {out_dir} -interaction=nonstopmode --synctex=1 {out_file}".replace(f"{out_file}", f"../{Path(out_file).name}")
    assert pdf_cmd[7] == final_pdflatex
    assert pdf_cmd[8] == final_pdflatex
