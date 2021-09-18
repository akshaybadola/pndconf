#! /usr/bin/python3

import os
import time
import shlex
from pathlib import Path
from subprocess import Popen, PIPE
import argparse
from watchdog.observers import Observer

from .config import Configuration
from .watcher import ChangeHandler
from .util import which, logd, loge, logi, logbi, logw


# TODO: Issue warning when incompatible options are used --biblatex and
#       pandoc-citeproc conflict e.g.
def parse_options():
    gentypes = ["html", "pdf", "reveal", "beamer"]
    parser = argparse.ArgumentParser(
        usage="""
    pndconf [opts] [pandoc_opts]

    Pandoc options must be entered in '--opt=value' format.

    Example:
        # To watch in current directory and generate pdf and html outputs
        pndconf -g pdf,html

        # To watch in some input directory and generate pdf and beamer outputs
        # to some other output directory
        pndconf -g pdf,beamer -d /path/to/watch_dir -o output_dir
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--pandoc-path", dest="pandoc_path",
        required=False,
        help="Provide custom pandoc path. Must be full path to executable")
    parser.add_argument(
        "-d", "--watch-dir", dest="watch_dir", default=".",
        help="Directory where to watch files. Defaults to current directory")
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", default=".",
        help="Directory for output files. Defaults to current directory")
    parser.add_argument(
        "-i", "--ignore-extensions", dest="exclusions",
        default=".pdf,.tex,doc,bin,common", required=False,
        help="The extensions (.pdf for pdf files) or the folders to " +
        "exclude from watch operations separated with commas")
    parser.add_argument(
        "-w", "--watch-extensions", dest="inclusions",
        default=".md", required=False,
        help="The extensions to watch. Only markdown (.md) is supported for now")
    parser.add_argument(
        "--exclude-regexp", dest="exclude_regexp",
        default="#,~,readme.md,changelog.md", required=False,
        help="Files with specific regex to exclude. Should not contain ','")
    parser.add_argument(
        "--no-exclude-ignore-case", action="store_false", dest="exclude_ignore_case",
        help="Whether the exclude regexp should ignore case or not.")
    parser.add_argument(
        "--exclude-files", dest="excluded_files",
        default="",
        help="Specific files to exclude from watching")
    parser.add_argument(
        "-g", "--generation", dest="generation",
        default="pdf",
        help=(f"Which formats to output. Can be one of [{', '.join(gentypes)}].\n" +
              "Defaults to pdf. You can choose multiple generation at once."))
    parser.add_argument(
        "-ro", "--run-once", dest="run_once",
        action="store_true",
        help="Run once for given input files without starting the watchdog")
    parser.add_argument(
        "--extra-opts", dest="extra_opts", action="store_true", help="Use extra opts.")
    parser.add_argument(
        "--input-files", dest="input_files",
        default="",
        help="Comma separated list of input files. Required if \"--run-once\" is specified")
    parser.add_argument(
        "-p", "--post-processor", default="",
        help="python module (or filename, must be in path) from which to load" +
        "post_processor function should be named \"post_processor\"")
    # TODO: use a simple flask server instead
    # parser.add_argument(
    #     "--live-server", dest="live_server",
    #     action='store_true',
    #     help="Start a live server?")
    parser.add_argument(
        "--templates-dir",
        help="Directory where templates are placed")
    parser.add_argument(
        "--csl-dir",
        help="Directory where csl files are placed")
    parser.add_argument(
        "--config-file", "-c", dest="config_file",
        help="Config file to read")
    parser.add_argument(
        "-po", "--print-pandoc-opts", dest="print_pandoc_opts",
        action="store_true",
        help="Print pandoc options and exit")
    parser.add_argument(
        "-L", "--log-file", dest="log_file",
        type=str,
        default="",
        help="Log file to output instead of stdout. Optional")
    parser.add_argument(
        "-l", "--log-level", dest="log_level",
        default="warning",
        help="Debug Level. One of: error, warning, info, debug")
    args = parser.parse_known_args()

    pandoc_path = Path(args[0].pandoc_path or which("pandoc"))
    if not (pandoc_path.exists() and pandoc_path.is_file()):
        loge("pandoc executable not available. Exiting!")
        exit(1)
    if args[0].print_pandoc_opts:
        out, err = Popen([str(pandoc_path), "--help"], stdout=PIPE, stderr=PIPE).communicate()
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        if err:
            loge(f"Pandoc exited with error {err}")
        else:
            loge(f"Pandoc options are \n{out}")
        exit(0)
    out = Popen(shlex.split(f"{pandoc_path} --version"), stdout=PIPE).\
        communicate()[0].decode("utf-8")
    logi(f"Pandoc path is {pandoc_path}")
    config = Configuration(args[0].watch_dir, args[0].output_dir,
                           config_file=args[0].config_file,
                           pandoc_path=pandoc_path,
                           pandoc_version=out.split()[1],
                           csl_dir=args[0].csl_dir,
                           templates_dir=args[0].templates_dir,
                           post_processor=args[0].post_processor,
                           extra_opts=args[0].extra_opts)
    # NOTE: The program assumes that extensions startwith '.'
    if args[0].exclude_regexp:
        logi("Excluding files for given filters",
             str(args[0].exclude_regexp.split(',')))
        config.set_excluded_regexp(args[0].exclude_regexp.split(','),
                                   args[0].exclude_ignore_case)
    if args[0].inclusions:
        inclusions = args[0].inclusions
        inclusions = inclusions.split(",")
        config.set_included_extensions(
            [value for value in inclusions if value.startswith(".")])
        if args[0].excluded_files:
            for ef in args[0].excluded_files.split(','):
                assert type(ef) == str
            config.set_excluded_files(args.excluded_files.split(','))
    if args[0].exclusions:
        exclusions = args[0].exclusions
        exclusions = exclusions.split(",")
        excluded_extensions = [value for value in exclusions if value.startswith(".")]
        excluded_folders = list(set(exclusions) - set(excluded_extensions))
        config.set_excluded_extensions(excluded_extensions)
        config.set_excluded_folders(excluded_folders)
    assert args[0].generation is not None
    diff = set(args[0].generation.split(",")) - set(gentypes)
    if diff:
        print(f"Unknown generation type {diff}")
        print(f"Choose from {gentypes}")

    config.log_level = args[0].log_level
    if config.log_level > 2:
        logi("\n".join(out.split("\n")[:3]))
        logi("-" * len(out.split("\n")[2]))
    if args[0].log_file:
        config.log_file = args[0].log_file
        logw("Log file isn't implemented yet. Will output to stdout")
    # TODO: Need Better checks
    # NOTE: These options will override pandoc options in all the sections of
    #       the config file
    for arg in args[1]:
        assert arg.startswith('-')
        if arg.startswith('--'):
            assert '=' in arg
    logbi(f"Will generate for {args[0].generation.upper()}")
    logbi(f"Extra pandoc args are {args[1]}")
    config.set_generation_opts(args[0].generation.split(','), args[1])
    logi(f"Generation options are \n{config.generation_opts}")
    # NOTE: should it be like this?
    return config, args[0].run_once, args[0].input_files.split(",")


def main():
    config, run_once, input_files = parse_options()
    input_files = [*filter(None, input_files)]
    if run_once:
        # remove null strings
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
    else:
        logi(f"\nWatching in {os.path.abspath(config.watch_dir)}")
        if input_files:
            watched_elements = input_files
            is_watched = lambda x: [os.path.abspath(x) in watched_elements]
            get_watched = lambda: [os.path.abspath(x) for x in input_files]
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
