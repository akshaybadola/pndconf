from typing import Dict, Union, List, Optional, Callable, Tuple
import os
from pathlib import Path

from common_pyutil.functional import unique

from .util import (update_command, get_csl_or_template, expandpath,
                   compress_space, logd, loge, logi, logbi, logw)
from .bibliography import generate_bibtex

Pathlike = Union[str, Path]


def get_template_or_csl_subr(argtype: str, csl_or_template: str,
                             search_dir: Optional[Path], in_file: Pathlike):
    """Subroutine to get possible file name from csl or template name.

    Args:
        argtype: Type of files to search, one of "csl" Or "template"
        csl_or_template: String value representing CSL or Pandoc Template
        search_dir: The path where possible file candidates are stored
        in_file: The input file path

    :code:`csl_or_template` can be a full path, a relative path or simply a string sans
    extension. Its existence is checked in order:
    full_path > self.csl_dir > relative_path

    Where relative_path is the path relative to input file

    """
    if Path(csl_or_template).exists():
        maybe_file = expandpath(csl_or_template)
    elif search_dir:
        maybe_file = get_csl_or_template(argtype, csl_or_template, search_dir)
    if Path(maybe_file).exists():
        return str(maybe_file)
    if argtype in [x.name for x in Path(in_file).parent.iterdir()]:
        check_dir = Path(in_file).parent.joinpath(argtype).absolute()
        maybe_file = get_csl_or_template(argtype, csl_or_template, check_dir)
    if Path(maybe_file).exists():
        return str(maybe_file)
    else:
        check_dir = Path(in_file).parent
        maybe_file = get_csl_or_template(argtype, csl_or_template, check_dir)
        if Path(maybe_file).exists():
            return str(maybe_file)
        else:
            logw(f"{argtype} file for \"{csl_or_template}\" not found. "
                 "This will default to pandoc template if it exists")
            return str(maybe_file)


def update_in_file_paths(in_file_pandoc_opts: Dict[str, str], csl_dir: Optional[Path],
                         templates_dir: Optional[Path], in_file: Pathlike):
    if "csl" in in_file_pandoc_opts:
        v = get_template_or_csl_subr("csl", in_file_pandoc_opts["csl"], csl_dir, in_file)
        # v = csl_subr(in_file_pandoc_opts["csl"], csl_dir, in_file)
        in_file_pandoc_opts["csl"] = v
    if "template" in in_file_pandoc_opts:
        v = get_template_or_csl_subr("template", in_file_pandoc_opts["template"],
                                     templates_dir, in_file)
        # v = template_subr(in_file_pandoc_opts["template"], templates_dir, in_file)
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

    def __init__(self, config: "Configuration", in_file: Path,
                 file_text: str, file_pandoc_opts: Dict):
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
            (" " if self.config.same_pdf_output_dir else
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

    def handle_pandoc_field_(self, key, value, command):
        # pandoc options, warn if override
        k = key[2:]
        maybe_in_cmdline_or_file = self.config.cmdline_opts.get(k, None) or\
            self.file_pandoc_opts.get(k, None)
        if k in {"template", "csl"}:
            v = maybe_in_cmdline_or_file or\
                get_template_or_csl_subr(k, value, self.config.templates_dir, self.in_file)
        else:
            v = maybe_in_cmdline_or_file or value
        if k == "filter":
            self.add_filters(command, k, v)
        elif k in self.file_pandoc_opts:
            if k in self.config.cmdline_opts:
                if k == "bibliography":
                    v = str(Path(v).absolute())
                update_command(command, k, v)
        else:
            command.append(f"--{k}={v}" if v else f"--{k}")

    def update_bibliography_in_file_opts(self, value):
        """Update bibliography by appending any new file given by :code:`value`

        Args:
            value: bibliography file

        """
        if "bibliography" in self.file_pandoc_opts:
            if isinstance(self.file_pandoc_opts["bibliography"], str):
                self.file_pandoc_opts["bibliography"] = [self.file_pandoc_opts["bibliography"],
                                                         str(Path(value).absolute())]
            else:
                self.file_pandoc_opts["bibliography"].append(str(Path(value).absolute()))

    def handle_pandoc_field(self, key: str, value: str, command: List[str]):
        """Handle pandoc field of type --k v or --k=v

        Args:
            key: Name of pandoc field
            value: Value of pandoc field
            command: The existing command


        The precedence is cmdline > in_file_opts > config_opts.
        Bibliography files are appended to any existing files in config or in_file metadata.
        Templates and CSL files are always added to command line as, sometimes
        pandoc doesn't respect the field in the file metadata.

        Filters are added in sequence from config > in_file > cmdline

        Otherwise if the same key is present in the file metadata and command line
        then the command line one is respected.

        """
        k = key[2:]
        maybe_in_cmdline_or_file = self.config.cmdline_opts.get(k, None) or\
            self.file_pandoc_opts.get(k, None)
        if k in {"template", "csl"}:
            v = maybe_in_cmdline_or_file or\
                get_template_or_csl_subr(k, value, self.config.templates_dir, self.in_file)
        else:
            v = maybe_in_cmdline_or_file or value
        if k == "filter":
            logd(f"Adding filter {v}")
            self.add_filters(command, k, v)
        elif k == "bibliography":
            logd(f"Updating bibliography {v}")
            self.update_bibliography_in_file_opts(v)
        elif k in self.file_pandoc_opts and k in self.config.cmdline_opts:
            logd(f"Updating value for {k}. Was {self.file_pandoc_opts[k]}, will be {v}")
            update_command(command, k, v)
        else:
            logd(f"Adding option {k} {v}")
            command.append(f"--{k}={v}" if v else f"--{k}")

    def handle_outfile_field(self, value, command):
        out_file = self.out_path_no_ext + "." + value
        command.append(f"-o {out_file}")
        return out_file

    def add_filters(self, command, k, v):
        vals = unique(v.split(","))
        if vals[0]:
            for val in vals:
                command.append(f"--{k}={val}")

    def get_file_output_dir(self, filename: Pathlike) -> Path:
        if Path(filename).absolute():
            file_dir = Path(filename).parent.absolute()
        if self.config.same_pdf_output_dir:
            output_dir = file_dir
            logw("Will output to same dir as input file.")
        else:
            output_dir = self.config.output_dir
        return output_dir

    def fix_command_for_pandoc_versions(self, command):
        if self.config.pandoc_version.geq("2.14.2") and "-S" in command:
            command.remove("-S")
            logd("Removed option -S")
            for i, c in enumerate(command):
                if "markdown+simple_tables" in c:
                    command[i] += "+smart"
        if self.config.no_citeproc and "--filter=pandoc-citeproc" in command:
            logd("Removed filter pandoc-citeproc as no-citeproc is given")
            command.remove("--filter=pandoc-citeproc")
        else:
            if self.config.pandoc_version.geq("2.12") and "--filter=pandoc-citeproc" in command:
                logd("Removed filter pandoc-citeproc as pandoc version > 2.12")
                command.remove("--filter=pandoc-citeproc")
                if not self.config.no_citeproc:
                    command.insert(0, "--citeproc")
                    logd("Added --citeproc instead of pandoc-citeproc")

    # FIXME: The bibliography part is a bit of a mess. The correct precedence of
    #        option parsing has to be validated
    def get_bibliography_opts(self, command):
        """Get the appropriate bibliography options.

        Both configuration and file specific options are (SHOULD BE) checked.
        """

        if self.config.no_citeproc:
            bib_cmds = {"--natbib": "bibtex", "--biblatex": "biblatex"}
            if not any(x in command for x in bib_cmds):
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
                # FIXME: practically unreachable code
                raise ValueError(f"Unknown citation processor {bib_cmd}")
            # if "references" in self.file_pandoc_opts:
            #     bib_style = "biblatex" if bib_cmd == "biblatex" else "bibtex"
            # else:
            #     bib_style = ""
            # NOTE: always biblatex and then convert to bibtex like syntax (I think LOL)
            bib_style = "biblatex" if "references" in self.file_pandoc_opts else ""
        else:
            bib_style = ""
            sed_cmd = ""
            bib_cmd = ""
        return bib_style, bib_cmd, sed_cmd

    def pdf_cmd_switch_to_output_dir(self, mk_tex_files_dir):
        return f"cd {self.output_dir} {mk_tex_files_dir}"

    def get_pdf_output_dir(self) -> Tuple[str, str]:
        if self.config.same_pdf_output_dir:
            tex_files_dir: Pathlike = self.output_dir
            mk_tex_files_dir = ""
        else:
            tex_files_dir = f"{self.out_path_no_ext}_files"
            mk_tex_files_dir = f"&& mkdir -p {tex_files_dir}"
        return str(tex_files_dir), mk_tex_files_dir

    def pdflatex_with_target_file_in_parent_dir(self, pdflatex):
        return pdflatex.replace(f'{self.out_path_no_ext}.tex',
                                f'../{Path(self.out_path_no_ext).stem}.tex')

    def pdflatex_with_target_file_in_tex_files_dir(self, pdflatex, tex_files_dir):
        return pdflatex.replace(f'{self.out_path_no_ext}.tex',
                                f'../{Path(self.out_path_no_ext).stem}.tex')\
                       .replace(f'cd {self.output_dir}', f'cd {tex_files_dir}')

    def add_bibtex_cmd(self, bib_file, tex_files_dir, pdflatex):
        cmd = []
        bibtex = f"bibtex {self.filename_no_ext}"
        copy_bibtex = "" if self.config.same_pdf_output_dir\
            else f"&& cp {bib_file.absolute()} {tex_files_dir}/"
        cmd.append(f"cd {self.output_dir} {copy_bibtex}")
        cmd.append(f"cd {tex_files_dir} && {bibtex}")
        if not self.config.same_pdf_output_dir:
            pdflatex = self.pdflatex_with_target_file_in_tex_files_dir(pdflatex, tex_files_dir)
        cmd.append(pdflatex)
        cmd.append(pdflatex)
        return cmd

    # FIXME: This may not be correct
    def add_biber_cmd(self, bib_file, tex_files_dir: str, pdflatex: str):
        cmd = []
        biber = f"biber {tex_files_dir}/{self.filename_no_ext}.bcf"
        cmd.append(f"cd {self.output_dir} && {biber}")
        cmd.append(pdflatex)
        return cmd

    def get_bib_commands(self, bib_cmd, bib_file, tex_files_dir, pdflatex):
        if bib_cmd == "biber" and bib_file:
            bib_commands = self.add_biber_cmd(bib_file, tex_files_dir, pdflatex)
        elif bib_cmd == "bibtex":
            bib_commands = self.add_bibtex_cmd(bib_file, tex_files_dir, pdflatex)
        else:
            bib_commands = []
            logw("No citation processor specified. References may not be defined correctly.")
        return bib_commands

    @property
    def pdf_out_file(self) -> str:
        if self.config.same_pdf_output_dir:
            out_file = self.out_path_no_ext + ".pdf"
        else:
            out_file = str(Path(self.out_path_no_ext + '_files').
                           joinpath(self.filename_no_ext + ".pdf"))
        return out_file

    def add_pdf_specific_options(self, command, ft) -> List[str]:
        # CHECK: If we don't use pdflatex explicitly but still use bibtex/biblatex
        #        for bibliography, can we still use pandoc with that?
        #        I think we can specify bibliography files but I don't need these
        #        commands then
        bib_style, bib_cmd, sed_cmd = self.get_bibliography_opts(command)
        if bib_cmd and bib_style and not self.config.no_cite_cmd:
            bib_file = generate_bibtex(Path(self.in_file), self.file_pandoc_opts, bib_style,
                                       self.file_text, self.config.pandoc_path,
                                       self.config.bib_transforms)
        pdf_cmd = []
        if sed_cmd:
            pdf_cmd.append(sed_cmd)

        # NOTE: Output filetype was PDF but generation was tex in config
        #       OR use explicit pdflatex for pdf instead of pandoc's engine
        # FIXME: This should be more explicit somewhere
        gentype = self.config.conf[ft].get("-o", None)
        if gentype in {"tex", "latex"}:
            logw(f"Asked to generate pdf but configuration says to generate {gentype}. "
                 "Will generate via pdflatex.")
            tex_files_dir, mk_tex_files_dir = self.get_pdf_output_dir()
            # NOTE: cd {self.output_dir} is crucial for correct directory
            #       selection
            pdflatex = f"cd {self.output_dir} && {self.pdflatex}"
            pdf_cmd.append(self.pdf_cmd_switch_to_output_dir(mk_tex_files_dir))
            if self.config.no_cite_cmd or not self.config.same_pdf_output_dir:
                pdf_cmd.append(f"rm {tex_files_dir}/*")
            pdf_cmd.append(pdflatex)

            if not self.config.same_pdf_output_dir:
                pdflatex = self.pdflatex_with_target_file_in_parent_dir(pdflatex)
            if self.config.no_cite_cmd:
                logbi(f"Not running bibtex command {bib_cmd} as asked.")
            elif self.config.no_citeproc:
                bib_commands = self.get_bib_commands(bib_cmd, bib_file, tex_files_dir, pdflatex)
                pdf_cmd.extend(bib_commands)
        return pdf_cmd

    def build_commands(self) -> Dict[str, Dict[str, Union[List[str], str]]]:
        """Build the command line from various options for given filetypes

        The filetypes are parsed and then queried from configuration :class:`Configuration`
        alongwith other parameters like :code:`output_directory`, pandoc configuration
        etc.

        The commands is a :class:`dict` with filetypes as keys and for each
        filetype, the commands of each are accumulated in a list in place.

        """
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
                    self.handle_pandoc_field(k, v, command)
                elif k == '-o':
                    out_file = self.handle_outfile_field(v, command)
                else:
                    command.append(f"{k} {v}" if v else f"{k}")

            self.fix_command_for_pandoc_versions(command)

            # TODO: Add EXPLICIT option in config for pdf generation via
            #       pdflatex
            if ft == 'pdf':
                pdf_cmd = self.add_pdf_specific_options(command, ft)
                out_file = self.pdf_out_file
            else:
                pdf_cmd = ""

            pandoc_cmd = " ".join([str(self.config.pandoc_path), ' '.join([*command])])

            cmd = [*map(compress_space, [pandoc_cmd, *pdf_cmd])]\
                if pdf_cmd else compress_space(pandoc_cmd)
            commands[ft] = {"command": cmd,
                            "in_file": self.in_file,
                            "out_file": out_file,
                            "in_file_opts": self.file_pandoc_opts,
                            "text": self.file_text}
        return commands
