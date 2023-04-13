from typing import List, Optional

import os
import sys
import time
import shlex
from pathlib import Path
from subprocess import Popen, PIPE
import argparse
from watchdog.observers import Observer

from common_pyutil.system import hierarchical_parser

from .config import Configuration
from .watcher import ChangeHandler
from .util import which, logd, loge, logi, logbi, logw
from . import __version__

usage = """
    pndconf [global_opts] CMD [opts] [pandoc_opts]

    Pandoc options must be entered in '--opt=value' format.

    See individual CMD help for usage of that command.

    \"pndconf -h/--help\" to print help

    \"pndconf --long-help\" to print all global options
"""
gentypes = ["html", "pdf", "reveal", "beamer", "latex"]


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
    sys.exit(0)


def print_generation_opts(args, config):
    for ft in filter(None, args.generation.split(",")):  # type: ignore
        opts = config.conf[ft]
        if opts:
            logi(f"Generation options for {ft} are:\n\t{[*opts.items()]}")
        else:
            loge(f"No generation options for {ft}")
    sys.exit(0)


def set_exclude_regexps(args, config):
    logi("Excluding files for given filters",
         str(args.exclude_regexp.split(',')))
    config.set_excluded_regexp(args.exclude_regexp.split(','),
                               args.exclude_ignore_case)


def set_inclusions(args, config):
    inclusions = args.inclusions
    inclusions = inclusions.split(",")
    config.set_included_extensions(
        [value for value in inclusions if value.startswith(".")])
    if args.excluded_files:
        for ef in args.excluded_files.split(','):
            assert type(ef) == str
        config.set_excluded_files(args.excluded_files.split(','))


def set_exclusions(args, config):
    exclusions = args.exclusions
    exclusions = exclusions.split(",")
    excluded_extensions = [value for value in exclusions if value.startswith(".")]
    excluded_folders = list(set(exclusions) - set(excluded_extensions))
    config.set_excluded_extensions(excluded_extensions)
    config.set_excluded_folders(excluded_folders)


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


def validate_extra_args(extra):
    # TODO: Need Better checks
    # NOTE: These options will override pandoc options in all the sections of
    #       the config file
    for i, arg in enumerate(extra):
        if not arg.startswith('-') and not (i >= 1 and extra[i-1] == "-V"):
            loge(f"Unknown pdfconf option {arg}.\n"
                 f"If it's a pandoc option {arg}, it must be preceded with -"
                 f", e.g. -{arg} or --{arg}=some_val")
            sys.exit(1)
        if arg.startswith('--') and '=' not in arg:
            loge(f"Unknown pdfconf option {arg}.\n"
                 f"If it's a pandoc option {arg}, it must be joined with =."
                 f"e.g. {arg}=some_val")
            sys.exit(1)


def get_config(args: argparse.Namespace, extra: List[str]) -> Configuration:
    pandoc_path, pandoc_version = pandoc_version_and_path(args.pandoc_path)
    out, err = get_pandoc_help_output(pandoc_path)
    logi(f"Pandoc path is {pandoc_path}")
    if args.print_pandoc_opts:
        print_pandoc_opts(out, err)
    watch_dir = getattr(args, "watch_dir", None)
    config = Configuration(watch_dir=watch_dir,
                           output_dir=args.output_dir,
                           config_file=args.config_file,
                           pandoc_path=pandoc_path,
                           pandoc_version=pandoc_version,
                           no_citeproc=args.no_citeproc,
                           csl_dir=args.csl_dir,
                           templates_dir=args.templates_dir,
                           post_processor=args.post_processor,
                           same_output_dir=args.same_output_dir,
                           dry_run=args.dry_run)
    set_log_levels_and_maybe_log_pandoc_output(args, config, out)
    return config


def add_common_args(parser):
    parser.add_argument("-o", "--output-dir",
                        dest="output_dir", default=".",
                        help="Directory for output files. Defaults to current directory")
    parser.add_argument("--no-citeproc", action="store_true", dest="no_citeproc",
                        help="Whether to process the citations via citeproc.")
    parser.add_argument("-g", "--generation",
                        dest="generation", default="pdf",
                        help=f"Which formats to output. Can be one of [{', '.join(gentypes)}].\n"
                        "Defaults to pdf. You can choose multiple generation at once.\n"
                        "E.g., 'pndconf -g pdf,html' or 'pndconf -g beamer,reveal'")
    parser.add_argument("--same-output-dir", action="store_true", dest="same_output_dir",
                        help="Output tex files and pdf to same dir as markdown file.\n"
                        "Default is to create a separate folder with a \"_files\" suffix")


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
    return parser


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
    return parser


def watch(args, config):
    # NOTE: The program assumes that extensions startwith '.'
    if args.exclude_regexp:
        set_exclude_regexps(args, config)
    if args.inclusions:
        set_inclusions(args, config)
    if args.exclusions:
        set_exclusions(args, config)
    input_files = args.input_files.split(",")
    logi(f"\nWatching in {os.path.abspath(config.watch_dir)}")
    # FIXME: Should just put input_files in config
    if input_files:
        watched_elements = input_files

        def is_watched(x):
            return os.path.abspath(x) in watched_elements

        def get_watched():
            return [os.path.abspath(x) for x in input_files]
    else:
        watched_elements = [os.path.basename(w) for w in config.get_watched()]
        is_watched = config.is_watched
        get_watched = config.get_watched
    logi(f"Watching: {watched_elements}")
    logi(f"Will output to {os.path.abspath(config.output_dir)}")
    logi("Starting pandoc watcher...")
    # CHECK: Maybe just pass config directly
    event_handler = ChangeHandler(config.watch_dir, is_watched,
                                  get_watched, config.compile_files,
                                  config.log_level)
    observer = Observer()
    observer.schedule(event_handler, str(config.watch_dir), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt as err:
        logi(str(err))
        # NOTE: Start simple server here when added and asked
        observer.stop()
    logi("Stopping pandoc watcher ...")
    sys.exit(0)


def convert(args, config):
    config.no_cite_cmd = args.no_cite_cmd
    input_files = args.input_files.split(",")
    not_input_files = [x for x in input_files if not os.path.exists(x)]
    if not_input_files:
        loge(f"{not_input_files} don't exist. Ignoring")
    input_files = [x for x in input_files if os.path.exists(x)]
    if not input_files:
        loge("Error! No input files present or given")
    elif not all(x.endswith(".md") for x in input_files):
        loge("Error! Some input files not markdown")
    else:
        logbi(f"Will compile {input_files} to {config.output_dir} once.")
        config.compile_files(input_files)


def check_and_dispatch_command(args, extra):
    config = get_config(args, extra)
    if args.print_generation_opts:
        print_generation_opts(args, config)
    if not args.generation:
        loge("Generation options cannot be empty")
        sys.exit(1)

    maybe_exit_for_unknown_generation_type(args)
    validate_extra_args(extra)
    logbi(f"Will generate for {args.generation.upper()}")
    logbi(f"Extra pandoc args are {extra}")
    config.set_cmdline_opts(args.generation.split(','), extra)

    if args.command == "watch":
        watch(args, config)
    elif args.command == "convert":
        convert(args, config)


def main():
    parser = argparse.ArgumentParser("pndconf: Pandoc Configuration Manager and File Watcher",
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
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Dry run. Don't actually do anything.")
    parser.add_argument("--dump-default-config", action="store_true",
                        help="Dump given config or default config.")
    parser.add_argument(
        "--pandoc-path", dest="pandoc_path",
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
                        help="Debug Level. One of: error, warning, info, debug")
    short_help = parser.format_help()
    long_help = parser.format_help()
    subparsers = parser.add_subparsers(help="Sub Commands", dest="command")
    add_watch_parser(subparsers)
    add_convert_parser(subparsers)
    args, extra = parser.parse_known_args()
    if args.help:
        print(short_help)
    if args.long_help:
        print("pndconf global options:\n" + long_help.replace(shorter_help, ""))
    if not args.command:
        print("No command given. Issue a command or a switch.\n")
        print(short_help)
    else:
        check_and_dispatch_command(args, extra)


if __name__ == '__main__':
    main()
