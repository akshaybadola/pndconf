from typing import Dict, Union, List, Optional, Callable
import os
import re
from pathlib import Path
import configparser
import pprint
from glob import glob

import yaml
from common_pyutil.system import Semver
from common_pyutil.functional import unique

from .util import (update_command, get_csl_or_template, expandpath,
                   generate_bibtex, compress_space, load_user_module,
                   logd, loge, logi, logbi, logw)
from .compilers import markdown_compile


StrPath = Union[str, Path]


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


# CHECK: What should configuration hold?
#
# TODO: Pandoc input and output processing should be with a better helper and
#       separate from config maybe
# TODO: remove output dir from watch if same as watch dir
class Configuration:
    def __init__(self, watch_dir: Path, output_dir: Path,
                 config_file: Optional[Path],
                 pandoc_path: Path,
                 pandoc_version: str,
                 no_citeproc: Optional[bool],
                 csl_dir: Optional[Path] = None,
                 templates_dir: Optional[Path] = None,
                 post_processor: Optional[Callable] = None,
                 dry_run=False):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.pandoc_path = pandoc_path
        self.pandoc_version = Semver(pandoc_version)
        self.no_citeproc = no_citeproc
        self.csl_dir = csl_dir and Path(csl_dir).absolute()
        self.templates_dir = templates_dir and Path(templates_dir).absolute()
        self._config_file = config_file or Path(__file__).parent.joinpath("config_default.ini")
        self._post_processor = post_processor
        self._cmdline_opts: Dict[str, str] = {}
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read(self._config_file)
        self._excluded_regexp: List[str] = []
        self._excluded_extensions: List[str] = []
        self._excluded_folders: List[str] = []
        self._included_extensions: List[str] = []
        self._excluded_files: List[str] = []
        self.dry_run = dry_run
        # self._use_extra_opts = extra_opts
        # self._extra_opts = {"latex-preproc": None}
        self._debug_levels = ["error", "warning", "info", "debug"]

    @property
    def post_processor(self):
        "Return the post processor"
        return self._post_processor

    @post_processor.setter
    def post_processor(self, postproc_module):
        "Set the post processor"
        if isinstance(postproc_module, str):
            if os.path.exists(postproc_module):
                pass
        if postproc_module:
            try:
                # NOTE: Must contain symbol post_processor
                self.post_processor = load_user_module(postproc_module).post_processor
                loge(f"Post Processor module {postproc_module} successfully loaded")
            except Exception as e:
                loge(f"Error occured while loading module {postproc_module}, {e}")
                self.post_processor = None
        else:
            logw(f"No Post Processor module given")
            self.post_processor = None

    @property
    def watch_dir(self) -> Optional[Path]:
        return self._watch_dir

    @watch_dir.setter
    def watch_dir(self, x: StrPath):
        if x:
            x = Path(x).expanduser().absolute()
            if x.exists() and x.is_dir():
                self._watch_dir = x
            else:
                loge(f"Could not set watch_dir {x}. Directory doesn't exist")

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, x: StrPath) -> None:
        x = Path(x).expanduser().absolute()
        if not x.exists():
            os.makedirs(x)
            logbi(f"Directory didn't exist. Created {x}.")
        self._output_dir = x

    @property
    def pandoc_path(self) -> Path:
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x: StrPath):
        if not x:
            raise ValueError("pandoc path cannot be empty")
        x = Path(x).expanduser().absolute()
        if x.exists() and x.is_file():
            self._pandoc_path = x
        else:
            loge(f"Could not set new pandoc path {x}. File doesn't exist.")

    @property
    def log_level(self) -> int:
        return self._debug_level

    @log_level.setter
    def log_level(self, x: Union[int, str]) -> None:
        if isinstance(x, int) and x in [0, 1, 2, 3]:
            self._debug_level = x
        elif isinstance(x, str) and x in self._debug_levels:
            self._debug_level = self._debug_levels.index(x)
        else:
            self._debug_level = 0

    @property
    def cmdline_opts(self) -> Dict[str, str]:
        return self._cmdline_opts

    def set_cmdline_opts(self, filetypes: List[str], pandoc_options: List[str]) -> None:
        """Update the config :code:`self._conf` with options from command line.

        Args:
            filetypes: The filetypes for which required to generate
            pandoc_options: A list of pandoc options. These options will override
                            any options present in the config file
                            or those mentioned in the yaml header inside the file.

        However, if multiple options like \"--filter\" or \"-V\" are provided
        then they are merged with existing options. In effect filters can be
        added but not removed. This may change in future versions of this
        module.

        """
        self._filetypes = filetypes
        if pandoc_options:
            for section in filetypes:
                for i, opt in enumerate(pandoc_options):
                    if opt == "-V":
                        val = pandoc_options[i+1]
                        existing = self._conf[section].get(opt, "")
                        self._conf[section][opt] = ",".join([*existing.split(","), val])\
                            if existing else val
                        existing = self._cmdline_opts.get("-V", "")
                        self._cmdline_opts["-V"] = ",".join([*existing.split(","), val])\
                            if existing else val
                    elif opt.startswith('--') and "=" in opt:
                        opt_key, opt_value = opt.split('=')
                        if opt_key == "--filter":
                            self._conf[section][opt_key] = ",".join([self._conf[section][opt_key],
                                                                     opt_value])
                            self._cmdline_opts[opt_key] = ",".join([self._cmdline_opts[opt_key],
                                                                    opt_value])
                        else:
                            self._conf[section][opt_key] = opt_value
                            self._cmdline_opts[opt_key[2:]] = opt_value
                    elif opt.startswith("-"):
                        self._conf[section][opt] = ''

    @property
    def generation_opts(self) -> str:
        "Return the pretty printed generation options"
        return pprint.pformat([(f, dict(self._conf[f])) for f in self._filetypes])

    def add_filters(self, command, k, v):
        vals = unique(v.split(","))
        if vals[0]:
            for val in vals:
                command.append(f"--{k}={val}")

    # TODO: should be a better way to compile with pdflatex
    # TODO: User defined options should override the default ones and the file ones
    def get_commands(self, in_file: str) ->\
            Optional[Dict[str, Dict[str, Union[List[str], str]]]]:
        """Get pandoc commands for various output formats for input file `in_file`.

        Args:
            in_file: Input file name


        Pandoc options can be specified via:
        a. Configuration file
        b. In the optional yaml header inside the file
        c. Options on the command line

        For the options the following precedence holds:

        command_line > in_file > config

        That is, options in command line will overwrite those in yaml header and
        they'll overwrite those in configuration file.

        """
        # TODO: The following should be replaced with separate tests
        # assert in_file.endswith('.md')
        # assert self._filetypes
        try:
            with open(in_file, 'r') as f:
                splits = f.read().split('---', maxsplit=3)
                if len(splits) == 3:
                    in_file_pandoc_opts = yaml.load(splits[1], Loader=yaml.FullLoader)
                    in_file_text = splits[2]
                else:
                    in_file_pandoc_opts = {}
                    in_file_text = splits[0]
        except Exception as e:
            loge(f"Yaml parse error {e}. Will not compile.")
            return None
        commands = {}
        filename_no_ext = os.path.splitext(os.path.basename(in_file))[0]
        out_path_no_ext = str(self.output_dir.joinpath(filename_no_ext))
        pdflatex = 'pdflatex  -file-line-error -output-directory '\
                   + out_path_no_ext + '_files'\
                   + ' -interaction=nonstopmode '\
                   + '--synctex=1 ' + out_path_no_ext + '.tex'

        # TODO: The commands should be validated
        #
        #       E.g: Say "-V colors=true" is given from
        #       config and "V colors=false" is given from cmdline
        #       cmdline should override the earlier one.
        for ft in self._filetypes:
            command: List[str] = []
            update_in_file_paths(in_file_pandoc_opts, self.csl_dir, self.templates_dir, in_file)
            for k, v in self._conf[ft].items():
                if k == '-M':
                    msg = loge("Metadata field setting is not supported")
                    raise AttributeError(msg)
                elif k == '-V':
                    cmdline_template_keys = [x.split('=')[0]
                                             for x in self.cmdline_opts.get("-V", "").split(",")
                                             if x]
                    conf_template_keys = [x.split('=')[0]
                                          for x in self._conf[ft].get("-V", "").split(",")
                                          if x]
                    config_keys = set(conf_template_keys) - set(cmdline_template_keys)
                    template_vars = set()
                    for x in v.split(","):
                        val = f"-V {x.strip()}"
                        tvar = x.strip().split("=")[0]
                        if tvar in config_keys and tvar in in_file_pandoc_opts:
                            continue
                        if tvar in template_vars:
                            msg = f"{tvar} being overridden"
                            logw(msg)
                        template_vars.add(tvar)
                        if val not in command:
                            command.append(val)
                elif k.startswith('--'):
                    # pandoc options, warn if override
                    k = k[2:]
                    if k == "template":
                        v = template_subr(v, self.templates_dir, in_file)
                    elif k == "csl":
                        v = csl_subr(v, self.csl_dir, in_file)
                    if k == "filter":
                        self.add_filters(command, k, v)
                    else:
                        if k in in_file_pandoc_opts:
                            if k in self.cmdline_opts:
                                if k == "bibliography":
                                    v = str(Path(v).absolute())
                                update_command(command, k, v)
                        else:
                            command.append(f"--{k}={v}" if v else k)
                else:
                    if k == '-o':
                        out_file = out_path_no_ext + "." + v
                        command.append(f"{k} {out_file}")
                    else:
                        command.append(f"{k} {v}" if v else f"{k}")
            if self.no_citeproc and "--filter=pandoc-citeproc" in command:
                command.remove("--filter=pandoc-citeproc")
            else:
                if self.pandoc_version.geq("2.12") and "--filter=pandoc-citeproc" in command:
                    command.remove("--filter=pandoc-citeproc")
                    if not self.no_citeproc:
                        command.insert(0, "--citeproc")
            if self.no_citeproc:
                bib_cmds = {"--natbib": "bibtex", "--biblatex": "biblatex"}
                if not any([x in command for x in bib_cmds]):
                    msg = "Not using citeproc and no other citation processor given. " +\
                        "Will use bibtex as default."
                    logw(msg)
                    bib_cmd = "bibtex"
                else:
                    bib_cmd = [(k, v) for k, v in bib_cmds.items()][0][1]
                if bib_cmd == "bibtex":
                    command.append("--natbib")
                    sed_cmd = "sed -i 's/\\\\citep{/\\\\cite{/g' " +\
                        os.path.join(filename_no_ext) + ".tex"
                elif bib_cmd == "biblatex":
                    command.append("--biblatex")
                    sed_cmd = ""
                else:
                    raise ValueError(f"Unknown citation processor {bib_cmd}")
                if "references" in in_file_pandoc_opts:
                    bib_style = "biblatex" if bib_cmd == "biblatex" else "bibtex"
                    bib_file = generate_bibtex(Path(in_file), in_file_pandoc_opts, bib_style,
                                               in_file_text, self.pandoc_path)
            else:
                sed_cmd = ""
                bib_cmd = ""
            command_str = " ".join([str(self.pandoc_path), ' '.join(command)])
            command = []
            if ft == 'pdf':
                command = [command_str]
                if sed_cmd:
                    command.append(sed_cmd)
                if "-o" in self._conf[ft] and self._conf[ft]["-o"] != "pdf":
                    tex_files_dir = f"{out_path_no_ext}_files"
                    command.append(f"cd {self.output_dir} && mkdir -p {tex_files_dir}")
                    command.append(f"rm {tex_files_dir}/*")
                    command.append(f"cd {self.output_dir} && {pdflatex}")
                    # NOTE: biber and pdflatex again if no citeproc
                    if self.no_citeproc:
                        if bib_cmd == "biber":
                            biber = f"biber {tex_files_dir}/{filename_no_ext}.bcf"
                            command.append(f"cd {self.output_dir} && {biber}")
                            command.append(f"cd {self.output_dir} && {pdflatex}")
                        elif bib_cmd == "bibtex":
                            bibtex = f"bibtex {filename_no_ext}"
                            command.append(f"cd {self.output_dir} && cp {bib_file} {tex_files_dir}/")
                            command.append(f"cd {tex_files_dir} && {bibtex}")
                            # bibtex = f"bibtex {tex_files_dir}/{filename_no_ext}"
                            # command.append(f"cd {self.output_dir} && {bibtex}")
                            pdflatex = pdflatex.replace(f'{out_path_no_ext}.tex',
                                                        f'../{Path(out_path_no_ext).stem}.tex')
                            # NOTE: pdflatex has to be run twice after bibtex,
                            #       can't we just use biblatex?
                            command.append(f"cd {tex_files_dir} && {pdflatex}")
                            command.append(f"cd {tex_files_dir} && {pdflatex}")
                        else:
                            raise logw("No citation processor specified. References may not be defined correctly.")
                    out_file = str(Path(out_path_no_ext + '_files').joinpath(filename_no_ext + ".pdf"))
                else:
                    out_file = out_path_no_ext + ".pdf"
            cmd = [*map(compress_space, command)] if command else compress_space(command_str)
            commands[ft] = {"command": cmd,
                            "in_file": in_file,
                            "out_file": out_file,
                            "in_file_opts": in_file_pandoc_opts,
                            "text": in_file_text}
        return commands

    def set_included_extensions(self, included_file_extensions):
        self._included_extensions = included_file_extensions

    def set_excluded_extensions(self, excluded_file_extensions):
        self._excluded_extensions = excluded_file_extensions

    def set_excluded_regexp(self, e, ignore_case: bool):
        self._excluded_regexp = e
        self._exclude_ignore_case = ignore_case

    def set_excluded_files(self, excluded_files: List[str]):
        self._excluded_files = excluded_files

    def set_excluded_folders(self, excluded_folders: List[str]):
        self._excluded_folders = excluded_folders

    # is_watched requires full relative filepath
    def is_watched(self, filepath: str):
        watched = False
        for ext in self._included_extensions:
            if filepath.endswith(ext):
                watched = True
        for ext in self._excluded_extensions:
            if filepath.endswith(ext):
                watched = False
        for folder in self._excluded_folders:
            if folder in filepath:
                watched = False
        for fn in self._excluded_files:
            if fn in filepath:
                watched = False
        for regex in self._excluded_regexp:
            flags = re.IGNORECASE if self._exclude_ignore_case else 0
            reg = '.*' + regex + '.*'
            if re.findall(reg, filepath, flags=flags):
                watched = False
        return watched

    def set_watched(self, watched: List[Path]):
        pass

    # CHECK: Should be cached maybe?
    def get_watched(self) -> List[str]:
        if self.watch_dir:
            all_files = glob(str(self.watch_dir.joinpath('**')), recursive=True)
        else:
            raise AttributeError("Watch dir is not defined")
        elements = [f for f in all_files if self.is_watched(f)]
        return elements

    def compile_files(self, md_files: Union[str, List[str]]):
        """Compile files and call the post_processor if it exists.

        Args:
            md_files: The markdown files to compile

        """
        post: List[Dict[str, str]] = []
        commands = None

        def compile_or_warn(cmds, mdf, post):
            if self.dry_run:
                for k, v in cmds.items():
                    cmd = "\n\t".join(v['command']) if isinstance(v['command'], list)\
                        else v['command']
                    logbi(f"Not compiling {mdf} to {k} with \n\t{cmd}\nas dry run.")
            else:
                if self.log_level > 2:
                    logbi(f"Compiling: {mdf}")
                post.append(markdown_compile(cmds, mdf))

        if md_files and isinstance(md_files, str):
            commands = self.get_commands(md_files)
            if commands is not None:
                compile_or_warn(commands, md_files, post)
        elif isinstance(md_files, list):
            for md_file in md_files:
                commands = self.get_commands(md_file)
                if commands is not None:
                    compile_or_warn(commands, md_file, post)
        if commands and self.post_processor and post:
            if self.dry_run:
                logbi("Not calling post_processor as dry run.")
            else:
                logbi("Calling post_processor")
                self.post_processor(post)
