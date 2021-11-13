#! /usr/bin/python3

from typing import Optional

import os
import sys
import time
import shlex
from pathlib import Path
from subprocess import Popen, PIPE
import argparse
from watchdog.observers import Observer
from types import SimpleNamespace

from common_pyutil.system import hierarchical_parser

from .config import Configuration
from .watcher import ChangeHandler
from .util import which, logd, loge, logi, logbi, logw
from . import __version__

usage = """
    pndconf CMD [opts] [pandoc_opts]

    Pandoc options must be entered in '--opt=value' format.

    Example:
        # To watch in current directory and generate pdf and html outputs
        pndconf watch -g pdf,html

        # To watch in some input directory and generate pdf and beamer outputs
        # to some other output directory
        pndconf watch -g pdf,beamer -d /path/to/watch_dir -o output_dir
"""
gentypes = ["html", "pdf", "reveal", "beamer"]


def pandoc_version_and_path(pandoc_path: Optional[Path]):
    pandoc_path = Path(pandoc_path or which("pandoc"))
    if not (pandoc_path.exists() and pandoc_path.is_file()):
        loge("'pandoc' executable not available.\n" +
             "Please install pandoc. Exiting!")
        exit(1)
    try:
        pandoc_version = Popen(shlex.split(f"{pandoc_path} --version"), stdout=PIPE).\
            communicate()[0].decode("utf-8").split()[1]
    except Exception as e:
        loge(f"Error checking pandoc version {e}")
        sys.exit(1)
    return pandoc_path, pandoc_version


def get_config(args: SimpleNamespace, extra: SimpleNamespace) -> Configuration:
    pandoc_path, pandoc_version = pandoc_version_and_path(args.pandoc_path)
    logi(f"Pandoc path is {pandoc_path}")
    if args.print_pandoc_opts:
        out, err = Popen([str(pandoc_path), "--help"], stdout=PIPE, stderr=PIPE).communicate()
        if err:
            loge(f"Pandoc exited with error {err.decode('utf-8')}")
        else:
            loge(f"Pandoc options are \n{out.decode('utf-8')}")
        sys.exit(0)
    config = Configuration(args.watch_dir, args.output_dir,
                           config_file=args.config_file,
                           pandoc_path=pandoc_path,
                           pandoc_version=pandoc_version,
                           no_citeproc=args.no_citeproc,
                           csl_dir=args.csl_dir,
                           templates_dir=args.templates_dir,
                           post_processor=args.post_processor,
                           dry_run=args.dry_run)
    # FIXME: No other args should be given with this
    if args.print_generation_opts:
        for ft in filter(None, args.generation.split(",")):  # type: ignore
            opts = config._conf[ft]
            logi(f"Generation options for {ft} are:\n\t{[*opts.items()]}")
            sys.exit(0)
        else:
            loge(f"No generation options for {ft}")
    # NOTE: The program assumes that extensions startwith '.'
    if args.exclude_regexp:
        logi("Excluding files for given filters",
             str(args.exclude_regexp.split(',')))
        config.set_excluded_regexp(args.exclude_regexp.split(','),
                                   args.exclude_ignore_case)
    if args.inclusions:
        inclusions = args.inclusions
        inclusions = inclusions.split(",")
        config.set_included_extensions(
            [value for value in inclusions if value.startswith(".")])
        if args.excluded_files:
            for ef in args.excluded_files.split(','):
                assert type(ef) == str
            config.set_excluded_files(args.excluded_files.split(','))
    if args.exclusions:
        exclusions = args.exclusions
        exclusions = exclusions.split(",")
        excluded_extensions = [value for value in exclusions if value.startswith(".")]
        excluded_folders = list(set(exclusions) - set(excluded_extensions))
        config.set_excluded_extensions(excluded_extensions)
        config.set_excluded_folders(excluded_folders)
    if not args.generation:
        loge("Generation options cannot be empty")
        sys.exit(1)
    diff = set(args.generation.split(",")) - set(gentypes)
    if diff:
        loge(f"Unknown generation type {diff}")
        loge(f"Choose from {gentypes}")
        sys.exit(1)

    config.log_level = args.log_level
    if config.log_level > 2:
        logi("\n".join(out.split("\n")[:3]))
        logi("-" * len(out.split("\n")[2]))
    if args.log_file:
        config.log_file = args.log_file
        logw("Log file isn't implemented yet. Will output to stdout")
    # TODO: Need Better checks
    # NOTE: These options will override pandoc options in all the sections of
    #       the config file
    for i, arg in enumerate(extra):
        if not arg.startswith('-'):
            if not (i >= 1 and extra[i-1] == "-V"):
                loge(f"pandoc option {arg} must be preceded with -, e.g. -{arg} or --{arg}=some_val")
                sys.exit(1)
        if arg.startswith('--') and '=' not in arg:
            loge(f"pandoc option {arg} must be joined with =. e.g. {arg}=some_val")
            sys.exit(1)
    logbi(f"Will generate for {args.generation.upper()}")
    logbi(f"Extra pandoc args are {extra}")
    config.set_cmdline_opts(args.generation.split(','), extra)
    return config


def add_common_args(parser):
    parser.add_argument(
        "--pandoc-path", dest="pandoc_path",
        required=False,
        help="Provide custom pandoc path. Must be full path to executable")
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", default=".",
        help="Directory for output files. Defaults to current directory")
    parser.add_argument(
        "--no-citeproc", action="store_true", dest="no_citeproc",
        help="Whether to process the citations via citeproc.")
    parser.add_argument(
        "-g", "--generation", dest="generation",
        default="pdf",
        help=f"Which formats to output. Can be one of [{', '.join(gentypes)}].\n" +
        "Defaults to pdf. You can choose multiple generation at once.\n" +
        "E.g., 'pndconf -g pdf,html' or 'pndconf -g beamer,reveal'")
    parser.add_argument(
        "-p", "--post-processor", default="",
        help="python module (or filename, must be in path) from which to load\n" +
        "post_processor function should be named \"post_processor\"")
    parser.add_argument(
        "--templates-dir",
        help="Directory where templates are placed")
    parser.add_argument("--csl-dir",
                        help="Directory where csl files are placed")
    parser.add_argument("--config-file", "-c", dest="config_file",
                        help="Config file to read.\n" +
                        "A default configuration is provided with the distribution.\n" +
                        "Print \"pndconf --dump-default-config\" to view the default config.")
    parser.add_argument("-po", "--print-pandoc-opts", dest="print_pandoc_opts",
                        action="store_true",
                        help="Print pandoc options and exit")
    parser.add_argument("-pg", "--print-generation-opts",
                        action="store_true",
                        help="Print pandoc options for filetype (e.g., for 'pdf') and exit")
    parser.add_argument("-L", "--log-file", dest="log_file",
                        type=str,
                        default="",
                        help="Log file to output instead of stdout. Optional")
    parser.add_argument("-l", "--log-level", dest="log_level",
                        default="warning",
                        help="Debug Level. One of: error, warning, info, debug")


def convert(arglist, gopts=None):
    description = "Convert files with pandoc"
    parser = argparse.ArgumentParser(
        usage=usage,
        description=description,
        allow_abbrev=False,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input_files", help="Comma separated list of input files.")
    add_common_args(parser)
    parser.add_argument("--no-cite-cmd",
                        action="store_true",
                        help="Don't run extra bibtex or biber commands for citations.\n" +
                        "Helpful when pdflatex is run with bibtex etc. and references need not be updated.")
    args, extra = parser.parse_known_args(arglist)
    args.watch_dir = None
    args.dry_run = gopts and gopts.dry_run
    args.exclude_regexp = None
    args.inclusions = None
    args.exclusions = None
    config = get_config(args, extra)
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


def watch(arglist, gopts=None):
    description = "Watch files for changes and convert with pandoc"
    parser = argparse.ArgumentParser(
        usage=usage,
        description=description,
        allow_abbrev=False,
        formatter_class=argparse.RawTextHelpFormatter)
    add_common_args(parser)
    parser.add_argument("-i", "--input-files", default="",
                        help="Comma separated list of input files.\n" +
                        "If given, only these files are watched.")
    parser.add_argument("-w", "--watch-dir", default=".", dest="watch_dir",
                        help="Directory to watch. Watch current directory if not specified.")
    parser.add_argument("--ignore-extensions", dest="exclusions",
                        default=".pdf,.tex,doc,bin,common", required=False,
                        help="The extensions (.pdf for pdf files) or the folders to " +
                        "exclude from watch operations separated with commas")
    parser.add_argument("--watch-extensions", dest="inclusions",
                        default=".md", required=False,
                        help="The extensions to watch. Only markdown (.md) is supported for now")
    parser.add_argument("--exclude-regexp", dest="exclude_regexp",
                        default="#,~,readme.md,changelog.md", required=False,
                        help="Files with specific regex to exclude. Should not contain ','")
    parser.add_argument("--no-exclude-ignore-case", action="store_false", dest="exclude_ignore_case",
                        help="Whether the exclude regexp should ignore case or not.")
    parser.add_argument("--exclude-files", dest="excluded_files",
                        default="",
                        help="Specific files to exclude from watching")
    args, extra = parser.parse_known_args(arglist)
    args.dry_run = gopts and gopts.dry_run
    config = get_config(args, extra)
    input_files = args.input_files.split(",")
    logi(f"\nWatching in {os.path.abspath(config.watch_dir)}")
    if input_files:
        watched_elements = input_files

        def is_watched(x):
            return os.path.abspath(x) in watched_elements

        def get_watched(x):
            return [os.path.abspath(x) for x in input_files]
    else:
        watched_elements = [os.path.basename(w) for w in config.get_watched()]
        is_watched = config.is_watched
        get_watched = config.get_watched
    logi(f"Watching: {watched_elements}")
    logi(f"Will output to {os.path.abspath(config.output_dir)}")
    logi("Starting pandoc watcher...")
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
    exit(0)


def gopts_parser(arglist):
    parser = argparse.ArgumentParser("File watcher")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("-vv", "--loud", action="store_true",
                        help="More verbose")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Dry run. Don't actually do anything.")
    parser.add_argument("--dump-default-config", action="store_true",
                        help="Dump given config or default config.")
    # parser.add_argument("-po", "--print-pandoc-opts", dest="print_pandoc_opts",
    #                     action="store_true",
    #                     help="Print pandoc options and exit")
    args = parser.parse_args(arglist)
    if args.dump_default_config:
        with open(Path(__file__).parent.joinpath("config_default.ini")) as f:
            print(f.read())
        sys.exit(0)
    # if args.print_pandoc_opts:
    #     out, err = Popen([str(pandoc_path), "--help"], stdout=PIPE, stderr=PIPE).communicate()
    #     out = out.decode("utf-8")
    #     err = err.decode("utf-8")
    #     if err:
    #         loge(f"Pandoc exited with error {err}")
    #     else:
    #         loge(f"Pandoc options are \n{out}")
    #     sys.exit(0)
    return args


def main():
    cmds = {"convert": convert, "watch": watch}
    parser = hierarchical_parser("pndconf", usage, cmds, gopts_parser, __version__)
    parser()
