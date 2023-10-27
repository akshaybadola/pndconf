from typing import Dict, Union, List, Optional, Callable
import os
import re
from pathlib import Path
import configparser
import pprint
from glob import glob

from common_pyutil.system import Semver

from .util import load_user_module, logd, loge, logi, logbi, logw, read_md_file_with_header
from .compilers import markdown_compile
from .commands import Commands


Pathlike = Union[str, Path]


# TODO: remove output dir from watch if same as watch dir
# TODO: Config should be yaml instead of config.ini. Yaml is more flexible
class Configuration:
    def __init__(self, watch_dir: Optional[Path], output_dir: Path,
                 config_file: Optional[Path],
                 pandoc_path: Path,
                 pandoc_version: str,
                 no_citeproc: Optional[bool],
                 csl_dir: Optional[Path] = None,
                 templates_dir: Optional[Path] = None,
                 post_processor: Optional[Callable] = None,
                 same_pdf_output_dir: bool = False,
                 dry_run: bool = False):
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
        self.conf.optionxform = lambda option: option  # type: ignore
        self.conf.read(self._config_file)
        self._filetypes = [k for k in self._conf if k not in {"options", "DEFAULT"}]
        self._excluded_regexp: List[str] = []
        self._excluded_extensions: List[str] = []
        self._excluded_folders: List[str] = []
        self._included_extensions: List[str] = []
        self._excluded_files: List[str] = []
        self.same_pdf_output_dir = same_pdf_output_dir
        self._bib_transforms: List[str] = []
        self.dry_run = dry_run
        self._log_file = None
        # self._use_extra_opts = extra_opts
        # self._extra_opts = {"latex-preproc": None}
        self._debug_levels = ["error", "warning", "info", "debug"]
        # NOTE: Some new arguments
        self.no_cite_cmd = False
        self.parse_options()

    def parse_options(self):
        if "options" in self.conf:
            if self.conf["options"]["transforms"]:
                self._bib_transforms = [*map(str.strip, self.conf["options"]["transforms"].split(","))]
            else:
                self._bib_transforms = []
            if "csl_dir" in self.conf["options"]:
                self.csl_dir = self.csl_dir or Path(self.conf["options"]["csl_dir"])
            if "templates_dir" in self.conf["options"]:
                self.templates_dir = self.templates_dir or Path(self.conf["options"]["templates_dir"])
            self.same_pdf_output_dir = self.same_pdf_output_dir or\
                self.conf["options"]["same_pdf_output_dir"]

    @property
    def filetypes(self):
        return self._filetypes

    @property
    def conf(self):
        return self._conf

    @property
    def bib_transforms(self) -> List[str]:
        return self._bib_transforms

    @property
    def post_processor(self):
        "Return the post processor"
        return self._post_processor

    @post_processor.setter
    def post_processor(self, postproc_module):
        "Set the post processor"
        # FIXME: Why's this here?
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
            logw("No Post Processor module given")
            self.post_processor = None

    @property
    def watch_dir(self) -> Optional[Path]:
        return self._watch_dir

    @watch_dir.setter
    def watch_dir(self, x: Pathlike):
        if x:
            x = Path(x).expanduser().absolute()
            if x.exists() and x.is_dir():
                self._watch_dir = x
            else:
                loge(f"Could not set watch_dir {x}. Directory doesn't exist")

    @property
    def output_dir(self) -> Path:
        """The directory to generate the compilation outputs.

        If :attr:`same_pdf_output_dir` is true, then PDFs and associated
        generated files are compiled to the same directory.

        """
        return self._output_dir

    @output_dir.setter
    def output_dir(self, x: Pathlike) -> None:
        x = Path(x).expanduser().absolute()
        if not x.exists():
            os.makedirs(x)
            logbi(f"Directory didn't exist. Created {x}.")
        self._output_dir = x

    @property
    def pandoc_path(self) -> Path:
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x: Pathlike):
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

    def update_generation_options(self, filetypes: List[str], pandoc_options: List[str]) -> None:
        """Update the generation config :code:`self._conf` with options from command line.

        Args:
            filetypes: The filetypes for which required to generate
            pandoc_options: A list of pandoc options. These options will override
                            any options present in the config file
                            or those mentioned in the yaml header inside the file.

        Called externally from the main process.

        If multiple options like \"--filter\" or \"-V\" are provided
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

    # TODO: should be a better way to compile with pdflatex
    # TODO: User defined options should override the default ones and the file ones
    # TODO: This functions is wayyy too complicated now. Split this is up
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

        In addition, pdflatex can be used to compile the latex output with
        bibtex and biblatex etc. citation preprocessors. The seqence of steps
        then becomes input_file > tex output > pdflatex commands > pdf output

        "pdflatex commands" can include multiple invocations of pdflatex along
        with bibtex or biber.

        """
        retval = read_md_file_with_header(in_file)
        if retval is None:
            return None
        else:
            in_file_text, in_file_pandoc_opts = retval

        commands = Commands(self, Path(in_file), in_file_text, in_file_pandoc_opts)
        return commands.build_commands()

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

    def compile_or_warn(self, cmds, mdf, post):
        if self.dry_run:
            for k, v in cmds.items():
                cmd = "\n\t".join(v['command']) if isinstance(v['command'], list)\
                    else v['command']
                logbi(f"Not compiling {mdf} to {k} with \n\t{cmd}\nas dry run.")
        else:
            if self.log_level > 2:
                logbi(f"Compiling: {mdf}")
            post.append(markdown_compile(cmds, mdf))

    def compile_files(self, md_files: Union[str, List[str]]):
        """Compile files and call the post_processor if it exists.

        Args:
            md_files: The markdown files to compile

        """
        post: List[Dict[str, str]] = []
        commands = None

        if md_files and isinstance(md_files, str):
            commands = self.get_commands(md_files)
            if commands is not None:
                self.compile_or_warn(commands, md_files, post)
        elif isinstance(md_files, list):
            for md_file in md_files:
                commands = self.get_commands(md_file)
                if commands is not None:
                    self.compile_or_warn(commands, md_file, post)
        logbi("Done compiling!")
        if commands and self.post_processor and post:
            if self.dry_run:
                logbi("Not calling post_processor as dry run.")
            else:
                logbi("Calling post_processor")
                self.post_processor(post)
