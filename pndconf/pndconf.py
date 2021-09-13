#! /usr/bin/python3
#
# The file copied from
# https://raw.githubusercontent.com/dloureiro/pandoc-watch/master/pandocwatch.py
# on "Sun Jun 17 16:33:03 IST 2018"

# Modified for python3 usage and some other extra arguments
# by Akshay Badola <akshay.badola.cs@gmail.com>
# on "Monday 27 July 2020 17:49:47 IST"

# Actually from that point onward I've changed it a lot so it's a completely
# different project now. Similar goals but different.
# "Saturday 15 August 2020 19:06:58 IST"

# TODO: Issue warning when incompatible options are used --biblatex and
#       pandoc-citeproc conflict e.g.

from typing import Dict, Union, List, Optional, Callable
from pathlib import Path
import re
import os
import time
import yaml
import shlex
import pprint
from subprocess import Popen, PIPE
import configparser
import argparse
from glob import glob
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from common_pyutil.system import Semver
from common_pyutil.functional import unique

from util import which, load_user_module, logd, loge, logi, logbi, logw
from compilers import markdown_compile


class ChangeHandler(FileSystemEventHandler):
    """Watch for changes in file system and fire events.

    ChangeHandler fires the commands corresnponding to the event and the
    Configuration instance `config`
    """
    def __init__(self, root, is_watched, get_watched, compile_func, log_level):
        self.root = root
        self.is_watched = is_watched
        self.get_watched = get_watched
        self.compile_files = compile_func
        self.log_level = log_level

    # NOTE: DEBUG
    # def on_any_event(self, event):
    #     print(str(event))

    def on_created(self, event):
        "Event fired when a new file is created"
        pwd = os.path.abspath(self.root) + '/'
        filepath = str(os.path.abspath(event.src_path))
        assert pwd in filepath
        filepath = filepath.replace(pwd, '')
        watched = self.is_watched(filepath)
        if watched:
            md_files = self.get_md_files(filepath)
            self.compile_stuff(md_files)

    def on_modified(self, event):
        "Event fired when a file is modified"
        if self.log_level > 2:
            logd(f"File {event.src_path} modified")
        md_files = self.get_md_files(event.src_path)
        if self.log_level > 2:
            logd(f"DEBUG: {md_files}")
        if md_files:
            self.compile_stuff(md_files)

    # NOTE: Maybe rename this function
    def compile_stuff(self, md_files: Union[str, List[str]]) -> None:
        "Compile if required when an event is fired"
        # NOTE:
        # The assumption below should not be on the type of variable
        # Though assumption is actually valid as there's only a
        # single file at a time which is checked
        self.compile_files(md_files)
        logbi("Done\n")

    # CHECK: If it's working correctly
    def get_md_files(self, e):
        "Return all the markdown files which include the template"
        if e.endswith('.md'):
            return e
        elif e.endswith('template'):
            logd(f"Template {e}")
            md_files = []
            elements = self.get_watched()
            elements = [elem for elem in elements if elem.endswith('.md')]
            for elem in elements:
                with open(elem, 'r') as f:
                    text = f.read()
                if ("includes " + e) in text:
                    md_files.append(elem)
            return md_files


# CHECK: What should configuration hold?
#
# TODO: Pandoc input and output processing should be with a better helper and
#       separate from config maybe
class Configuration:
    def __init__(self, watch_dir: Path, output_dir: Path,
                 config_file: Path = Path("config.ini"),
                 pandoc_path: Optional[Path] = None,
                 pandoc_version: str = "",
                 post_processor: Optional[Callable] = None,
                 extra_opts=False):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.pandoc_path = pandoc_path
        self.pandoc_version = Semver(pandoc_version)
        self._config_file = config_file
        self._post_processor = post_processor
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read(self._config_file)
        self._excluded_regexp = []
        self._excluded_extensions = []
        self._excluded_folders = []
        self._included_extensions = []
        self._excluded_files = []
        self._use_extra_opts = extra_opts
        self._extra_opts = {"latex-preproc": None}
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
    def watch_dir(self):
        return self._watch_dir

    @watch_dir.setter
    def watch_dir(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._watch_dir = os.path.expanduser(x)
        else:
            loge(f"Could not set watch_dir {x}. Directory doesn't exist")

    @property
    def output_dir(self):
        return self._output_dir

    @output_dir.setter
    def output_dir(self, x):
        x = os.path.expanduser(x)
        if not os.path.exists(x):
            os.makedirs(x)
            logbi(f"Directory didn't exist. Created {x}.")
        self._output_dir = x

    @property
    def pandoc_path(self):
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = os.path.expanduser(x)
        else:
            loge(f"Could not set new pandoc path {x}. File doesn't exist.")

    @property
    def log_level(self):
        return self._debug_level

    @log_level.setter
    def log_level(self, x):
        if x in [0, 1, 2, 3]:
            self._debug_level = x
        elif x in self._debug_levels:
            self._debug_level = self._debug_levels.index(x)
        else:
            self._debug_level = 0

    def set_generation_opts(self, filetypes: List[str], pandoc_options: List[str]) -> None:
        """
        """
        self._filetypes = filetypes
        if pandoc_options:
            for section in filetypes:
                for opt in pandoc_options:
                    if opt.startswith('--') and "=" in opt:
                        opt_key, opt_value = opt.split('=')
                        if opt_key == "--filter":
                            self._conf[section][opt_key] = ",".join([self._conf[section][opt_key], opt_value])
                        else:
                            self._conf[section][opt_key] = opt_value
                    else:
                        self._conf[section][opt] = ''

    @property
    def generation_opts(self):
        return pprint.pformat([(f, dict(self._conf[f])) for f in self._filetypes])

    def add_filters(self, command, k, v):
        vals = unique(v.split(","))
        if vals[0]:
            for val in vals:
                command.append(k + '=' + val)


    # TODO: should be a better way to compile with pdflatex
    # TODO: User defined options should override the default ones and the file ones
    def get_commands(self, in_file: str) ->\
            Optional[Dict[str, Dict[str, Union[List[str], str]]]]:
        # TODO: The following should be replaced with separate tests
        # assert in_file.endswith('.md')
        # assert self._filetypes
        try:
            with open(in_file, 'r') as f:
                in_file_pandoc_opts = yaml.load(f.read().split('---')[1], Loader=yaml.FullLoader)
        except Exception as e:
            loge(f"Yaml parse error {e}. Will not compile.")
            return None
        commands = {}
        filename_no_ext = os.path.splitext(os.path.basename(in_file))[0]
        out_path_no_ext = os.path.join(self.output_dir, filename_no_ext)
        pdflatex = 'pdflatex  -file-line-error -output-directory '\
                   + out_path_no_ext + '_files'\
                   + ' -interaction=nonstopmode '\
                   + '--synctex=1 ' + out_path_no_ext + '.tex'
        for ft in self._filetypes:
            command = []
            for k, v in self._conf[ft].items():
                if k == '-V':
                    split_vals = v.split(',')
                    for val in split_vals:
                        command.append('-V ' + val.strip())
                elif k.startswith('--'):
                    if k[2:] in in_file_pandoc_opts:
                        command.append(k + '=' + in_file_pandoc_opts[k[2:]])
                        if k[2:] == 'filter':
                            self.add_filters(command, k, v)
                    elif k[2:] in self._extra_opts:
                        self._extra_opts[k[2:]] = v
                    else:
                        if k[2:] == 'filter':
                            self.add_filters(command, k, v)
                        else:
                            command.append(k + '=' + v if v else k)
                else:
                    if k == '-o':
                        out_file = out_path_no_ext + "." + v
                        command.append(k + ' ' + out_file)
                    else:
                        command.append(k + (' ' + v) if v else '')
            if self.pandoc_version.geq("2.12") and "--filter=pandoc-citeproc" in command:
                command.remove("--filter=pandoc-citeproc")
                command.insert(0, "--citeproc")
            command_str = " ".join([self.pandoc_path, ' '.join(command), in_file])
            command = []
            if ft == 'pdf':
                # FIXME: Bad hack for doing a regexp after latex generation
                if self._extra_opts["latex-preproc"] and self._use_extra_opts:
                    command = [command_str, self._extra_opts["latex-preproc"] + " " +
                               f"{out_path_no_ext}.tex"]
                else:
                    command = [command_str]
                command.append('mkdir -p ' + out_path_no_ext + "_files")
                command.append(pdflatex)
                out_file = os.path.join(out_path_no_ext + '_files', filename_no_ext + ".pdf")
            commands[ft] = {"command": command or command_str, "out_file": out_file}
        return commands

    def set_included_extensions(self, included_file_extensions):
        self._included_extensions = included_file_extensions

    def set_excluded_extensions(self, excluded_file_extensions):
        self._excluded_extensions = excluded_file_extensions

    def set_excluded_regexp(self, e, ignore_case: bool):
        self._excluded_regexp = e
        self._exclude_ignore_case = ignore_case

    def set_excluded_files(self, excluded_files):
        self._excluded_files = excluded_files

    def set_excluded_folders(self, excluded_folders):
        self._excluded_folders = excluded_folders

    # is_watched requires full relative filepath
    def is_watched(self, filepath):
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
            if re.findall(regex, filepath, flags=flags):
                watched = False
        return watched

    def set_watched(self, watched: List[Path]):
        pass

    # CHECK: Should be cached maybe?
    def get_watched(self):
        all_files = glob(os.path.join(self.watch_dir, '**'), recursive=True)
        elements = [f for f in all_files if self.is_watched(f)]
        return elements

    def compile_files(self, md_files):
        """This function logs the compilation and calls the post_processor if it
        exists.
        """
        post = []
        commands = None
        if md_files and isinstance(md_files, str):
            if self.log_level > 2:
                logbi(f"Compiling: {md_files}")
            commands = self.get_commands(md_files)
            if commands is not None:
                post.append(markdown_compile(commands, md_files))
        elif isinstance(md_files, list):
            for md_file in md_files:
                commands = self.get_commands(md_file)
                if self.log_level > 2:
                    logbi(f"Compiling: {md_file}")
                if commands is not None:
                    post.append(markdown_compile(commands, md_file))
        if commands and self.post_processor and post:
            logbi("Calling post_processor")
            self.post_processor(post)


def parse_options():
    parser = argparse.ArgumentParser(
        description="A config manager and file watcher for pandoc",
        usage="""

    pandocwatch [opts] [pandoc_opts]

    Pandoc options must be entered in '--opt=value' format.
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
        help="The extensions (.pdf for pdf files) or the folders to\
        exclude from watch operations separated with commas")
    parser.add_argument(
        "-w", "--watch-extensions", dest="inclusions",
        default=".md", required=False,
        help="The extensions (.pdf for pdf files) or the folders to\
        exclude from watch operations separated with commas")
    parser.add_argument(
        "--exclude-regexp", dest="exclude_regexp",
        default="#,~,readme.md,changelog.md", required=False,
        help="Files with specific regex to exclude. Should not contain ','")
    parser.add_argument(
        "--no-exclude-ignore-case", action="store_false", dest="exclude_ignore_case",
        help="Whether the exclude regexp should ignore case or not.")
    parser.add_argument(
        "--exclude-files", dest="excluded_files",
        default="", required=False,
        help="Specific files to exclude from watching")
    parser.add_argument(
        "-g", "--generation", dest="generation",
        default="blog", required=False,
        help="Which formats to output. Can be blog,pdf,reveal,beamer")
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
        "--config-file", "-c", dest="config_file",
        default="config.ini",
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

    pandoc_path = args[0].pandoc_path or which("pandoc")
    if not os.path.exists(pandoc_path):
        loge("pandoc executable not available. Exiting!")
        exit(1)
    if args[0].print_pandoc_opts:
        out, err = Popen([pandoc_path, "--help"], stdout=PIPE, stderr=PIPE).communicate()
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


# FIXME: A bunch of this code is annoying. Gotta reformat
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
            get_watched = lambda x: [os.path.abspath(x) for x in input_files]
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
        observer.schedule(event_handler, config.watch_dir, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt as err:
            logi(str(err))
            # NOTE: Have to switch to Flask
            # if config.live_server:
            #     p.terminate()
            observer.stop()

        # Code to compile all the required files at startup not needed for now.
        # Though should include the code needed to compile all the
        # dependent files in a module later and not just templates.
        logi("Stopping pandoc watcher ...")
        exit(0)


if __name__ == '__main__':
    main()
