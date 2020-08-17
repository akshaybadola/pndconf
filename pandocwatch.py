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

# NOTE: FOR BLOG GENERATION - tags, keywords, SEO
# etc. should be updated from yaml in the markdown - if html has files it should
# be filename_html_files and not filename_files perhaps update pdf generation
# also to filename_pdf_files

import re
import os
import time
import yaml
import shlex
import pprint
from subprocess import Popen, PIPE
import configparser
import argparse
from typing import Dict, Union, List
from glob import glob
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from util import which, load_user_module
from colors import COLORS
from compilers import markdown_compile


# TODO: This should only check for change in md files and associated <!-- includes --> files
#
# CHECK: So I changed the ChangeHandler to be a bit more explicit but now I'm
#        thinking how much this and Configuration are coupled.
#        I can either:
#        1. Merge them into a single class, but then Configuration will have to
#        inherit from FileSystemEventHandler and maybe have to be renamed to
#        PandocWatch
#        2. Or I could make a separate Compiler (or Executor or Something) class
#        which does what?
class ChangeHandler(FileSystemEventHandler):
    """ChangeHandler fires the commands corresnponding to the event and the
    Configuration instance `config`"""
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
            print("File " + event.src_path + " modified")
        md_files = self.get_md_files(event.src_path)
        if self.log_level > 2:
            print(f"DEBUG: {md_files}")
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
        print("Done\n")

    # CHECK: If it's working correctly
    def get_md_files(self, e):
        "Return all the markdown files which include the template"
        if e.endswith('.md'):
            return e
        elif e.endswith('template'):
            print("template" + e)
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
    def __init__(self, watch_dir, output_dir, config_file="config.ini",
                 pandoc_path=None, post_processor=None, live_server=False):
        self._watch_dir = watch_dir
        self._output_dir = output_dir
        self._pandoc_path = pandoc_path
        self._config_file = config_file
        self._post_processor = post_processor
        self.live_server = live_server
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read(self._config_file)
        self._excluded_regex = []
        self._excluded_extensions = []
        self._excluded_folders = []
        self._included_extensions = []
        self._excluded_files = []
        self._debug_levels = ["error", "warning", "info", "debug"]

    @property
    def post_processor(self):
        return self._post_processor

    @post_processor.setter
    def post_processor(self, postproc_module):
        if isinstance(postproc_module, str):
            if os.path.exists(postproc_module):
                pass
        if postproc_module:
            try:
                # NOTE: Must contain symbol post_processor
                self.post_processor = load_user_module(postproc_module).post_processor
                print(f"Post Processor module {postproc_module} successfully loaded")
            except Exception as e:
                print(f"Error occured while loading module {postproc_module}, {e}")
                self.post_processor = None
        else:
            print(f"No Post Processor module given")
            self.post_processor = None

    @property
    def output_dir(self):
        return self._output_dir

    @output_dir.setter
    def output_dir(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = x
        else:
            print(f"Could not set output_dir {x}. Directory doesn't exist")

    @property
    def watch_dir(self):
        return self._watch_dir

    @watch_dir.setter
    def watch_dir(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = x
        else:
            print(f"Could not set watch_dir {x}. Directory doesn't exist")

    @property
    def pandoc_path(self):
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = x
        else:
            print(f"Could not set new pandoc path {x}")

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

    def set_generation_opts(self, filetypes: List[str], pandoc_options) -> None:
        self._filetypes = filetypes
        if pandoc_options:
            for section in filetypes:
                for opt in pandoc_options:
                    if opt.startswith('--'):
                        opt_key, opt_value = opt.split('=')
                        self._conf[section][opt_key] = self._conf[section][opt_value]
                    else:
                        self._conf[section][opt] = ''

    @property
    def generation_opts(self):
        return pprint.pformat([(f, dict(self._conf[f])) for f in self._filetypes])

    # TODO: should be a better way to compile with pdflatex
    # TODO: User defined options should override the default ones and the file ones
    def get_commands(self, filename: str) -> Dict[str, Dict[str, str]]:
        assert filename.endswith('.md')
        assert self._filetypes
        try:
            with open(filename, 'r') as f:
                in_file_pandoc_opts = yaml.load(f.read().split('---')[1], Loader=yaml.FullLoader)
        except Exception as e:
            print(f"Yaml parse error {e}. Will not compile.")
            return None
        commands = {}
        filename = filename.replace('.md', '')
        pdflatex = 'pdflatex  -file-line-error -output-directory '\
                   + filename + '_files' + ' -interaction=nonstopmode '\
                   + '--synctex=1 ' + filename + '.tex'
        for ft in self._filetypes:
            command = []
            for k, v in self._conf[ft].items():
                if k == '-V':
                    split_vals = v.split(',')
                    for val in split_vals:
                        command.append('-V ' + val.strip())
                elif k.startswith('--'):
                    if k[2:] in in_file_pandoc_opts:
                        if k[2:] == 'filter':
                            command.append(k + '=' + v if v else k)
                        command.append(k + '=' + in_file_pandoc_opts[k[2:]])
                    else:
                        # if self.buntu:
                        #     if k[2:] == "pdf-engine":
                        #         k = "--latex-engine"
                        command.append(k + '=' + v if v else k)
                else:
                    if k == '-o':
                        out_file = filename + '.' + v
                        command.append(k + ' ' + filename + '.' + v)
                    else:
                        command.append(k + (' ' + v) if v else '')
            command = " ".join([self.pandoc_path, ' '.join(command), filename + '.md'])
            if ft == 'pdf':
                command = [command, 'mkdir -p ' + filename + '_files']
                command.append(pdflatex)
                out_file = filename + "_files" + filename + ".pdf"
            commands[ft] = {"command": command, "out_file": out_file}
        return commands

    def set_included_extensions(self, included_file_extensions):
        self._included_extensions = included_file_extensions

    def set_excluded_extensions(self, excluded_file_extensions):
        self._excluded_extensions = excluded_file_extensions

    def set_excluded_regex(self, excluded_filters):
        self._excluded_regex = excluded_filters

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
        for regex in self._excluded_regex:
            if re.findall(regex, filepath):
                watched = False
        return watched

    # CHECK: Should be cached maybe?
    def get_watched(self):
        all_files = glob(os.path.join(self._watch_dir, '**'), recursive=True)
        elements = [f for f in all_files if self.is_watched(f)]
        return elements

    def compile_files(self, md_files):
        """This function logs the compilation and calls the post_processor if it
        exists.
        """
        post = []
        if md_files and isinstance(md_files, str):
            if self.log_level > 2:
                print(f"{COLORS.BLUE}Compiling{COLORS.ENDC}: {md_files}")
            commands = self.get_commands(md_files)
            if commands is not None:
                post.append(markdown_compile(commands, md_files))
        elif isinstance(md_files, list):
            for md_file in md_files:
                commands = self.get_commands(md_file)
                if self.log_level > 2:
                    print(f"{COLORS.BLUE}Compiling{COLORS.ENDC}: {md_file}")
                if commands is not None:
                    post.append(markdown_compile(commands, md_file))
        if commands and self.post_processor and post:
            print("Calling post_processor")
            self.post_processor(post)


def parse_options():
    parser = argparse.ArgumentParser(
        description="Watcher for pandoc compilation",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--pandoc-path", dest="pandoc_path",
        required=False,
        help="Provide custom pandoc path. Must be full path to executable")
    parser.add_argument(
        "--watch-dir", "-d", dest="watch_dir", default=".",
        help="Directory where to watch files. Defaults to current directory")
    parser.add_argument(
        "--output-dir", "-o", dest="output_dir", default=".",
        help="Directory for output files. Defaults to current directory")
    parser.add_argument(
        "-e", "--exclude", dest="exclusions",
        default=".pdf,.tex,doc,bin,common", required=False,
        help="The extensions (.pdf for pdf files) or the folders to\
        exclude from watch operations separated with commas")
    parser.add_argument(
        "--exclude-filters", dest="exclude_filters",
        default="#,~", required=False,
        help="Files with specific regex to exclude. Should not contain ','")
    parser.add_argument(
        "--exclude-files", dest="excluded_files",
        default="", required=False,
        help="Specific files to exclude from watching")
    parser.add_argument(
        "-i", "--include", dest="inclusions",
        default=".md", required=False,
        help="The extensions (.pdf for pdf files) or the folders to\
        exclude from watch operations separated with commas")
    parser.add_argument(
        "-g", "--generation", dest="generation",
        default="blog", required=False,
        help="Which formats to output. Can be blog,pdf,reveal,beamer")
    parser.add_argument(
        "-ro", "--run-once", dest="run_once",
        action="store_true",
        help="Run once for given input files without starting the watchdog")
    parser.add_argument(
        "--input-files", dest="input_files",
        default="",
        help="Comma separated list of input files. Required if \"--run-once\" is specified")
    parser.add_argument(
        "-p", "--post-processor", default="",
        help="python module (or filename, must be in path) from which to load" +
        "post_processor function should be named \"post_processor\"")
    # TODO: use a simple flask server instead
    parser.add_argument(
        "--live-server", dest="live_server",
        action='store_true',
        help="Start a live server?")
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

    if args[0].pandoc_path:
        pandoc_path = args.pandoc_path
    else:
        pandoc_path = which("pandoc")
    if not os.path.exists(pandoc_path):
        print("pandoc executable not available. Exiting!")
        exit(1)
    if args[0].print_pandoc_opts:
        out, err = Popen([pandoc_path, "--help"], stdout=PIPE, stderr=PIPE).communicate()
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        if err:
            print(f"Pandoc exited with error {err}")
        else:
            print(f"Pandoc options are \n{out}")
        exit(0)
    out = Popen(shlex.split(f"{pandoc_path} --version"), stdout=PIPE).\
        communicate()[0].decode("utf-8")
    print(f"Pandoc path is {pandoc_path}")
    if args[0].live_server:
        raise NotImplementedError
    config = Configuration(args[0].watch_dir, args[0].output_dir,
                           config_file=args[0].config_file,
                           pandoc_path=pandoc_path,
                           post_processor=args[0].post_processor,
                           live_server=args[0].live_server)
    # NOTE: The program assumes that extensions startwith '.'
    if args[0].exclude_filters:
        print("Excluding files for given filters",
              str(args[0].exclude_filters.split(',')))
        config.set_excluded_regex(args[0].exclude_filters.split(','))
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
        print("\n".join(out.split("\n")[:3]))
        print("-" * len(out.split("\n")[2]))
    if args[0].log_file:
        config.log_file = args[0].log_file
        print("Log file isn't implemented yet. Will output to stdout")
    # TODO: Need Better checks
    # NOTE: These options will override pandoc options in all the sections of
    #       the config file
    for arg in args[1]:
        assert arg.startswith('-')
        if arg.startswith('--'):
            assert '=' in arg
    print(f"Will generate for {args[0].generation.upper()}")
    config.set_generation_opts(args[0].generation.split(','), ' '.join(args[1]))
    print(f"Generation options are \n{config.generation_opts}")
    # NOTE: should it be like this?
    if args[0].run_once:
        return config, True, args[0].input_files.split(",")
    else:
        return config, False, None


# FIXME: A bunch of this code is annoying. Gotta reformat
def main():
    config, run_once, input_files = parse_options()
    if run_once:
        # remove null strings
        input_files = [*filter(None, input_files)]
        not_input_files = [x for x in input_files if not os.path.exists(x)]
        if not_input_files:
            print(f"{not_input_files} don't exist. Ignoring")
        input_files = [x for x in input_files if os.path.exists(x)]
        if not input_files:
            print("Error! No input files present or given")
        elif not all(x.endswith(".md") for x in input_files):
            print("Error! Some input files not markdown")
        else:
            print(f"Will compile {input_files} to {config.output_dir} once.")
            config.compile_files(input_files)
    else:
        watched_elements = config.get_watched()
        print("watching ", [w.replace(config.watch_dir, "")
                            for w in watched_elements])
        print(f"Will output to {config.output_dir}")
        if config.live_server:
            # NOTE: Have to switch to Flask
            # print("Starting pandoc watcher and the live server ...")
            # p = Popen(['live-server', '--open=.'])
            raise NotImplementedError
        else:
            print("Starting pandoc watcher only ...")
        event_handler = ChangeHandler(config.watch_dir, config.is_watched,
                                      config.get_watched, config.compile_files,
                                      config.log_level)
        observer = Observer()
        observer.schedule(event_handler, config.watch_dir, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt as err:
            print(str(err))
            # NOTE: Have to switch to Flask
            # if config.live_server:
            #     p.terminate()
            observer.stop()

        # Code to compile all the required files at startup not needed for now.
        # Though should include the code needed to compile all the
        # dependent files in a module later and not just templates.
        print("Stopping pandoc watcher ...")
        exit(0)


if __name__ == '__main__':
    main()
