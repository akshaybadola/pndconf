from typing import Dict, Union, List, Optional, Callable
import os
import re
from pathlib import Path

from common_pyutil.functional import unique

from .util import (update_command, get_csl_or_template, expandpath,
                   generate_bibtex, compress_space, load_user_module,
                   logd, loge, logi, logbi, logw)


Pathlike = Union[str, Path]


def csl_subr(v: str, csl_dir: Optional[Path], in_file: str):
    """Subroutine to get file name from csl name.

    Args:
        v: String value representing CSL

    :code:`v` can be a full path, a relative path or simply a string sans
    extension. Its existence is checked in order:
    full_path > self.csl_dir > relative_path

    Where relative_path is the path relative to input file

    """
    if Path(v).exists():
        v = expandpath(v)
    elif csl_dir:
        v = get_csl_or_template("csl", v, csl_dir)
    elif "csl" in [x.name for x in Path(in_file).parent.iterdir()]:
        check_dir = Path(in_file).parent.joinpath("csl").absolute()
        v = get_csl_or_template("csl", v, check_dir)
    else:
        raise AttributeError(f"CSL file for {v} not found")
    return str(v)


def template_subr(v: str, templates_dir: Optional[Path], in_file: str):
    if Path(v).exists():
        v = expandpath(v)
    elif templates_dir:
        v = get_csl_or_template("template", v, templates_dir)
    elif "templates" in [x.name for x in Path(in_file).parent.iterdir()]:
        check_dir = Path(in_file).parent.joinpath("templates").absolute()
        v = get_csl_or_template("template", v, check_dir)
    else:
        raise AttributeError(f"Template file for {v} not found")
    return str(v)


def update_in_file_paths(in_file_pandoc_opts: Dict[str, str], csl_dir: Optional[Path],
                         templates_dir: Optional[Path], in_file: str):
    if "csl" in in_file_pandoc_opts:
        v = csl_subr(in_file_pandoc_opts["csl"], csl_dir, in_file)
        in_file_pandoc_opts["csl"] = v
    if "template" in in_file_pandoc_opts:
        v = template_subr(in_file_pandoc_opts["template"], templates_dir, in_file)
        in_file_pandoc_opts["template"] = v
    for k, v in in_file_pandoc_opts.items():
        if isinstance(v, str) and v.startswith("./"):
            in_file_pandoc_opts[k] = str(Path(in_file).parent.absolute().joinpath(v))



class Commands:
    """A Commands class to generate a pandoc or associated command for a given
    :mod:`pndconf` configuration and output filetypes

    Args:
        config: :mod:`pndconf` :class:`Configuration`
        in_file: Input file
        file_text: Text from the input file
        file_pandoc_opts: Pandoc options parsed from the input file yaml header

    """

    def __init__(self, config, in_file, file_text, file_pandoc_opts):
        self.config = config
        self.in_file = in_file
        self.output_dir = self.get_file_output_dir(in_file)
        self.filename_no_ext = os.path.splitext(os.path.basename(self.in_file))[0]
        self.out_path_no_ext = str(self.output_dir.joinpath(self.filename_no_ext))
        self.file_text = file_text
        self.file_pandoc_opts = file_pandoc_opts
        self.handlers = {"-M": self.handle_metadata_field,
                         "-V": self.handle_variable_field}

    @property
    def pdflatex(self) -> str:
        return 'pdflatex  -file-line-error ' +\
            (" " if self.config.same_output_dir else
             '-output-directory ' + self.out_path_no_ext + '_files') +\
             ' -interaction=nonstopmode --synctex=1 ' +\
             self.out_path_no_ext + '.tex'

    def handle_metadata_field(self):
        msg = loge("Metadata field setting is not supported")
        raise AttributeError(msg)


    def handle_variable_field(self, ft, value, command):
        cmdline_template_keys = [x.split('=')[0]
                                 for x in self.config.cmdline_opts.get("-V", "").split(",")
                                 if x]
        conf_template_keys = [x.split('=')[0]
                              for x in self.config.conf[ft].get("-V", "").split(",")
                              if x]
        config_keys = set(conf_template_keys) - set(cmdline_template_keys)
        template_vars = set()
        for x in value.split(","):
            val = f"-V {x.strip()}"
            tvar = x.strip().split("=")[0]
            if tvar in config_keys and tvar in self.file_pandoc_opts:
                continue
            if tvar in template_vars:
                msg = f"{tvar} being overridden"
                logw(msg)
            template_vars.add(tvar)
            if val not in command:
                command.append(val)

    def handle_pandoc_field(self, key, value, command):
        # pandoc options, warn if override
        k = key[2:]
        if k == "template":
            v = template_subr(value, self.config.templates_dir, self.in_file)
        elif k == "csl":
            v = csl_subr(value, self.config.csl_dir, self.in_file)
        else:
            v = value
        if k == "filter":
            self.add_filters(command, k, v)
        else:
            if k in self.file_pandoc_opts:
                if k in self.config.cmdline_opts:
                    if k == "bibliography":
                        v = str(Path(v).absolute())
                    update_command(command, k, v)
            else:
                command.append(f"--{k}={v}" if v else f"--{k}")

    def handle_outfile_field(self, value, command):
        out_file = self.out_path_no_ext + "." + value
        command.append(f"-o {out_file}")

    def add_filters(self, command, k, v):
        vals = unique(v.split(","))
        if vals[0]:
            for val in vals:
                command.append(f"--{k}={val}")

    def get_file_output_dir(self, filename: Pathlike) -> Path:
        if Path(filename).absolute():
            file_dir = Path(filename).parent
        if self.config.same_output_dir:
            output_dir = file_dir
            logw("Will output to same dir as input file.")
        else:
            output_dir = self.output_dir
        return output_dir

    def fix_command_for_pandoc_versions(self, command):
        if self.config.pandoc_version.geq("2.14.2") and "-S" in command:
            command.remove("-S")
            for i, c in enumerate(command):
                if "markdown+simple_tables" in c:
                    command[i] += "+smart"
        if self.config.no_citeproc and "--filter=pandoc-citeproc" in command:
            command.remove("--filter=pandoc-citeproc")
        else:
            if self.config.pandoc_version.geq("2.12") and "--filter=pandoc-citeproc" in command:
                command.remove("--filter=pandoc-citeproc")
                if not self.config.no_citeproc:
                    command.insert(0, "--citeproc")

    def add_bibliography_opts(self, command):
        if self.config.no_citeproc:
            bib_cmds = {"--natbib": "bibtex", "--biblatex": "biblatex"}
            if not any([x in command for x in bib_cmds]):
                msg = ("Not using citeproc and no other citation processor given. "
                       "Will use bibtex as default.")
                logw(msg)
                bib_cmd = "bibtex"
            else:
                bib_cmd = [(k, v) for k, v in bib_cmds.items()][0][1]
            if bib_cmd == "bibtex":
                command.append("--natbib")
                sed_cmd = "sed -i 's/\\\\citep{/\\\\cite{/g' " +\
                    os.path.join(self.output_dir, self.filename_no_ext) + ".tex"
            elif bib_cmd == "biblatex":
                command.append("--biblatex")
                sed_cmd = ""
            else:
                raise ValueError(f"Unknown citation processor {bib_cmd}")
            if "references" in self.file_pandoc_opts:
                bib_style = "biblatex" if bib_cmd == "biblatex" else "bibtex"
                # NOTE: always biblatex and then convert to bibtex like syntax (I think LOL)
                bib_style = "biblatex"
                bib_file = generate_bibtex(Path(self.in_file), self.file_pandoc_opts, bib_style,
                                           self.file_text, self.config.pandoc_path)
            else:
                bib_file = ""
        else:
            sed_cmd = ""
            bib_cmd = ""
        return bib_style, bib_file, bib_cmd, sed_cmd

    def add_pdf_specific_options(self, command, ft):
        bib_sytle, bib_file, bib_cmd, sed_cmd = self.add_bibliography_opts(command)
        pandoc_cmd = " ".join([str(self.config.pandoc_path), ' '.join(command)])
        command = [pandoc_cmd]
        if sed_cmd:
            command.append(sed_cmd)
        if "-o" in self.config.conf[ft] and self.config.conf[ft]["-o"] != "pdf":
            tex_files_dir = self.output_dir if self.config.same_output_dir else\
                f"{self.out_path_no_ext}_files"
            command.append(f"cd {self.output_dir}" +
                           (f"&& mkdir -p {tex_files_dir}"
                            if not self.output_dir == tex_files_dir else ""))
            if not self.config.no_cite_cmd and (not tex_files_dir == self.output_dir):
                # Don't clean output directory for tex if same_output_dir
                command.append(f"rm {tex_files_dir}/*")
            command.append(f"cd {self.output_dir} && {self.pdflatex}")
            # NOTE: biber and pdflatex again if no citeproc
            if self.config.no_cite_cmd:
                command.append(f"cd {self.output_dir} && {self.pdflatex}")
                logbi(f"Not running {bib_cmd} as asked.")
            if self.config.no_citeproc and not self.config.no_cite_cmd:
                if bib_cmd == "biber" and bib_file:
                    biber = f"biber {tex_files_dir}/{self.filename_no_ext}.bcf"
                    command.append(f"cd {self.output_dir} && {biber}")
                    command.append(f"cd {self.output_dir} && {self.pdflatex}")
                elif bib_cmd == "bibtex":
                    bibtex = f"bibtex {self.filename_no_ext}"
                    command.append(f"cd {self.output_dir} && cp {bib_file} {tex_files_dir}/")
                    command.append(f"cd {tex_files_dir} && {bibtex}")
                    if not self.config.same_output_dir:
                        pdflatex = self.pdflatex.replace(f'{self.out_path_no_ext}.tex',
                                                         f'../{Path(self.out_path_no_ext).stem}.tex')
                    else:
                        pdflatex = self.pdflatex
                    # NOTE: pdflatex has to be run twice after bibtex,
                    #       can't we just use biblatex?
                    command.append(f"cd {tex_files_dir} && {pdflatex}")
                    command.append(f"cd {tex_files_dir} && {pdflatex}")
                else:
                    raise logw("No citation processor specified. References may not be defined correctly.")
            out_file = str(Path(self.out_path_no_ext + '_files').
                           joinpath(self.filename_no_ext + ".pdf"))
        else:
            out_file = self.out_path_no_ext + ".pdf"
        return out_file, command

    def build_commands(self) -> Dict[str, Dict[str, Union[List[str], str]]]:
        commands = {}
        for ft in self.config.filetypes:
            command: List[str] = []
            update_in_file_paths(self.file_pandoc_opts, self.config.csl_dir,
                                 self.config.templates_dir, self.in_file)
            for k, v in self.config.conf[ft].items():
                if k == '-M':
                    self.handle_metadata_field()
                elif k == '-V':
                    self.handle_variable_field(ft, v, command)
                elif k.startswith('--'):
                    self.handle_pandoc_field(ft, v, command)
                elif k == '-o':
                    self.handle_outfile_field(v, command)
                else:
                    command.append(f"{k} {v}" if v else f"{k}")

            self.fix_command_for_pandoc_versions(command)

            if ft == 'pdf':
                out_file, command = self.add_pdf_specific_options(command, ft)

            command_str = " ".join([str(self.config.pandoc_path), ' '.join(command)])

            cmd = [*map(compress_space, command)] if command else compress_space(command_str)
            commands[ft] = {"command": cmd,
                            "in_file": self.in_file,
                            "out_file": out_file,
                            "in_file_opts": self.file_pandoc_opts,
                            "text": self.file_text}
        return commands
