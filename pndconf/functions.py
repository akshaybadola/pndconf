import os
import sys
import time

from watchdog.observers import Observer

from .watcher import ChangeHandler
from .util import which, logd, loge, logi, logbi, logw


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


def watch(args, config):
    # FIXME: The program assumes that extensions startwith '.'
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
        logi("Stopping pandoc watcher ...")
        # NOTE: Start simple server here when added and asked
        observer.stop()
    logi("Stopped pandoc watcher")
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
        if config.same_pdf_output_dir:
            logbi("Will compile pdf files to same directory as they're in.")
        config.compile_files(input_files)



def standalone(args, config):
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
        logbi(f"Will generate standalone files for {input_files} to {config.output_dir} once.")
        raise NotImplementedError("Not implemented after this, LOL")

