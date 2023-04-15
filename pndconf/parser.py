from typing import List, Optional, Tuple

import sys
import shlex
from pathlib import Path
from subprocess import Popen, PIPE
import argparse

from .config import Configuration
from .util import which, logd, loge, logi, logbi, logw
from .functions import watch, convert
from .const import gentypes, log_levels
from . import __version__


usage = """
    pndconf [global_opts] CMD [opts] [pandoc_opts]

    Pandoc options must be entered in '--opt=value' format.

    See individual CMD help for usage of that command.

    \"pndconf -h/--help\" to print help

    \"pndconf --long-help\" to print all global options
"""


def pandoc_version_and_path(pandoc_path: Optional[Path]):
    pandoc_path = Path(pandoc_path or which("pandoc"))
    if not (pandoc_path.exists() and pandoc_path.is_file()):
        loge("'pandoc' executable not available.\n"
             "Please install pandoc. Exiting!")
        sys.exit(1)
    try:
        pandoc_version = Popen(shlex.split(f"{pandoc_path} --version"), stdout=PIPE).\
            communicate()[0].decode("utf-8").split()[1]
    except Exception as e:
        loge(f"Error checking pandoc version {e}")
        sys.exit(1)
    return pandoc_path, pandoc_version


def get_pandoc_help_output(pandoc_path):
    return Popen([str(pandoc_path), "--help"], stdout=PIPE, stderr=PIPE).communicate()


def print_pandoc_opts(stdout, stderr):
    if stderr:
        loge(f"Pandoc exited with error {stderr.decode('utf-8')}")
    else:
        loge(f"Pandoc options are \n{stdout.decode('utf-8')}")


def print_generation_opts(args, config):
    for ft in filter(None, args.generation.split(",")):  # type: ignore
        opts = config.conf[ft]
        if opts:
            logi(f"Generation options for {ft} are:\n\t{[*opts.items()]}")
        else:
            loge(f"No generation options for {ft}")


def maybe_exit_for_unknown_generation_type(args):
    diff = set(args.generation.split(",")) - set(gentypes)
    if diff:
        loge(f"Unknown generation type {diff}")
        loge(f"Choose from {gentypes}")
        sys.exit(1)


def set_log_levels_and_maybe_log_pandoc_output(args, config, out):
    config.log_level = args.log_level
    if config.log_level > 2:
        logi("\n".join(out.decode().split("\n")[:3]))
        logi("-" * len(out.decode().split("\n")[2]))
    if args.log_file:
        config._log_file = args.log_file
        logw("Log file isn't implemented yet. Will output to stdout")


# TODO: Need Better checks
# NOTE: These options will override pandoc options in all the sections of
#       the config file
def validate_extra_args(extra):
    for i, arg in enumerate(extra):
        if not arg.startswith('-') and not (i >= 1 and extra[i-1] == "-V"):
            loge(f"Unknown pdfconf option {arg}.\n"
                 f"If it's a pandoc option {arg}, it must be preceded with -"
                 f", e.g. -{arg} or --{arg}=some_val")
            sys.exit(1)
        if arg.startswith('--') and '=' not in arg:
            loge(f"Unknown pdfconf option {arg}.\n"
                 f"If it's a pandoc option {arg}, it must be joined with \"=\". "
                 f"e.g. {arg}=some_val")
            sys.exit(1)


# CHECK: Since the options like these are really commmon options and not usually
#        specified in the config.ini (which only contains generation) options
#        anyway. Perhaps they should be moved to separate config classes.
def get_config_and_pandoc_output(args: argparse.Namespace)\
        -> Tuple[Configuration, Tuple[str, str]]:
    pandoc_path, pandoc_version = pandoc_version_and_path(args.pandoc_path)
    out, err = get_pandoc_help_output(pandoc_path)
    logi(f"Pandoc path is {pandoc_path}\n")
    # NOTE: This one is only watch specific
    watch_dir = getattr(args, "watch_dir", None)
    # NOTE: these options are common and added by subcommand parsers
    output_dir = Path(getattr(args, "output_dir", "."))
    no_citeproc = getattr(args, "no_citeproc", None)
    same_pdf_output_dir = getattr(args, "same_pdf_output_dir", False)
    config = Configuration(watch_dir=watch_dir,
                           output_dir=output_dir,
                           config_file=args.config_file,
                           pandoc_path=pandoc_path,
                           pandoc_version=pandoc_version,
                           no_citeproc=no_citeproc,
                           csl_dir=args.csl_dir,
                           templates_dir=args.templates_dir,
                           post_processor=args.post_processor,
                           same_pdf_output_dir=same_pdf_output_dir,
                           dry_run=args.dry_run)
    set_log_levels_and_maybe_log_pandoc_output(args, config, out)
    return config, (out, err)


def add_common_args(parser):
    parser.add_argument("-o", "--output-dir",
                        dest="output_dir", default=".",
                        help="Directory for output files. Defaults to current directory")
    parser.add_argument("--no-citeproc", action="store_true", dest="no_citeproc",
                        help="Whether to process the citations via citeproc.")
    parser.add_argument("--shell-pdflatex", action="store_true", dest="shell_pdflatex",
                        help="Use pdflatex via shell command instead of pandoc interface.\n"
                        "pandoc's internal compilation system with pdflatex doesn't ignore")
    parser.add_argument("-g", "--generation",
                        dest="generation", default="pdf",
                        help=f"Which formats to output. Can be [{', '.join(gentypes)}].\n"
                        "Defaults to pdf. You can choose multiple generation at once.\n"
                        "E.g., 'pndconf -g pdf,html' or 'pndconf -g beamer,reveal'")
    parser.add_argument("--same-pdf-output-dir", action="store_true", dest="same_pdf_output_dir",
                        help="Output tex files and pdf to same dir as markdown file.\n"
                        "Default is to create a separate folder with a \"_files\" suffix")


def common_args_parser():
    """Hacky common args parser.

    Only to generate default arguments before actual commands are called, all
    because I didn't want to put the generation/output etc. opts before the
    commands.

    """
    parser = MyParser(allow_abbrev=False,
                      add_help=False,
                      formatter_class=argparse.RawTextHelpFormatter)
    add_common_args(parser)
    return parser


def add_convert_parser(subparsers):
    description = "Convert files with pandoc"
    convert_usage = """
    pndconf [global_opts] convert [opts] [pandoc_opts]

    Example:
        # To convert a single file yourfile.md to yourfile.pdf
        pndconf convert -g pdf yourfile.md

        # To convert a multiple files
        pndconf convert -g pdf yourfile.md,otherfile.md

        # To convert to multiple formats

        pndconf convert -g pdf,html yourfile.md
"""
    parser = subparsers.add_parser("convert",
                                   usage=convert_usage,
                                   description=description,
                                   allow_abbrev=False,
                                   formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input_files", help="Comma separated list of input files.")
    parser.add_argument("--no-cite-cmd",
                        action="store_true",
                        help="Don't run extra bibtex or biber commands for citations.\n"
                        "Helpful when pdflatex is run with bibtex etc."
                        "and references need not be updated.")
    add_common_args(parser)


def add_watch_parser(subparsers):
    description = "Watch files for changes and convert with pandoc"
    watch_usage = """
    pndconf [global_opts] watch [opts] [pandoc_opts]

    Example:
        # To watch in current directory and generate pdf and html outputs
        pndconf watch -g pdf,html

        # To watch in some input directory and generate pdf and beamer outputs
        # to some other output directory
        pndconf watch -g pdf,beamer -w /path/to/watch_dir -o output_dir
"""
    parser = subparsers.add_parser("watch",
                                   description=description,
                                   allow_abbrev=False,
                                   usage=watch_usage,
                                   formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-i", "--input-files", default="",
                              help="Comma separated list of input files.\n"
                              "If given, only these files are watched.")
    parser.add_argument("-w", "--watch-dir", default=".", dest="watch_dir",
                              help="Directory to watch. Watch current directory if not specified.")
    parser.add_argument("--ignore-extensions", dest="exclusions",
                              default=".pdf,.tex,doc,bin,common", required=False,
                              help="The extensions (.pdf for pdf files) or the folders to"
                              " exclude from watch operations separated with commas")
    parser.add_argument("--watch-extensions", dest="inclusions",
                              default=".md", required=False,
                              help="The extensions to watch. Only markdown (.md) is supported for now")
    parser.add_argument("--exclude-regexp", dest="exclude_regexp",
                              default="#,~,readme.md,changelog.md", required=False,
                              help="Files with specific regex to exclude. Should not contain ','")
    parser.add_argument("--no-exclude-ignore-case", action="store_false",
                              dest="exclude_ignore_case",
                              help="Whether the exclude regexp should ignore case or not.")
    parser.add_argument("--exclude-files", dest="excluded_files",
                              default="",
                              help="Specific files to exclude from watching")
    add_common_args(parser)


def check_and_dispatch_command(args, extra, short_help):
    config, out_err = get_config_and_pandoc_output(args)

    common_args, _ = common_args_parser().parse_known_args()

    if args.dump_default_config:
        with open(Path(__file__).parent.joinpath("config_default.ini")) as f:
            print(f.read())
        sys.exit(0)
    if args.print_pandoc_opts:
        print_pandoc_opts(*out_err)
        sys.exit(0)
    if args.print_generation_opts:
        print_generation_opts(common_args, config)
        sys.exit(0)
    if not args.command:
        loge("No command given. Issue a command or a switch.\n")
        print(short_help)
        sys.exit(1)
    if not common_args.generation:
        loge("Generation options cannot be empty")
        sys.exit(1)

    maybe_exit_for_unknown_generation_type(args)
    validate_extra_args(extra)
    logbi(f"Will generate for {args.generation.upper()}")
    logbi(f"Extra pandoc args are {extra}")

    # Update generation options, it'll generate everything by default
    config.update_generation_options(args.generation.split(','), extra)

    if args.command == "watch":
        watch(args, config)
    elif args.command == "convert":
        convert(args, config)


class MyParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def error(self, message):
        loge(message)
        print("")
        self.print_usage(sys.stderr)
        sys.exit(1)


def main():
    description = "pndconf: Pandoc Configuration Manager and File Watcher"
    # parser = argparse.ArgumentParser(description,
    parser = MyParser(description,
                      usage=usage,
                      allow_abbrev=False,
                      add_help=False,
                      formatter_class=argparse.RawTextHelpFormatter)
    shorter_help = parser.format_help()
    parser.add_argument("-h", "--help", action="store_true",
                        help="Display help and exit")
    parser.add_argument("--long-help", action="store_true",
                        help="Display all the global options")
    parser.add_argument("-c", "--config-file", dest="config_file",
                        help="Config file to read. "
                        "A default configuration is provided with the distribution.\n"
                        "Print \"pndconf --dump-default-config\" to view the default config.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("-vv", "--loud", action="store_true",
                        help="More verbose")
    parser.add_argument("-vvv", "--shout", action="store_true",
                        help="Even more verbose")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Dry run. Don't actually do anything.")
    parser.add_argument("--dump-default-config", action="store_true",
                        help="Dump given config or default config.")
    short_help = parser.format_help()
    parser.add_argument("--pandoc-path", dest="pandoc_path",
                        default="/usr/bin/pandoc",
                        help="Provide custom pandoc path. Must be full path to executable")
    parser.add_argument("-po", "--print-pandoc-opts", dest="print_pandoc_opts",
                        action="store_true",
                        help="Print pandoc options and exit")
    parser.add_argument("-p", "--post-processor",
                        dest="post_processor", default="",
                        help="python module (or filename, must be in path) from which to load\n"
                        "post_processor function should be named \"post_processor\"")
    parser.add_argument("--templates-dir",
                        help="Directory where templates are placed")
    parser.add_argument("--csl-dir",
                        help="Directory where csl files are placed")
    parser.add_argument("-pg", "--print-generation-opts",
                        action="store_true",
                        help="Print pandoc options for filetype (e.g., for 'pdf') and exit")
    parser.add_argument("-L", "--log-file",
                        dest="log_file", default="",
                        help="Log file to output instead of stdout. Optional")
    parser.add_argument("-l", "--log-level",
                        dest="log_level", default="warning",
                        choices=log_levels,
                        help="Debug Level")
    parser.add_argument("--version",
                        action="store_true",
                        help="Print version and exit")
    long_help = parser.format_help()
    subparsers = parser.add_subparsers(help="Sub Commands", dest="command")
    add_watch_parser(subparsers)
    add_convert_parser(subparsers)
    args, extra = parser.parse_known_args()
    if args.help:
        print(description)
        print("\n", short_help)
        sys.exit(0)
    if args.long_help:
        print(description, "\n")
        print("Global options:\n" + long_help.replace(shorter_help, ""))
        sys.exit(0)
    if args.version:
        print(f"pndconf version {__version__}")
        sys.exit(0)
    check_and_dispatch_command(args, extra, short_help)


if __name__ == '__main__':
    main()
