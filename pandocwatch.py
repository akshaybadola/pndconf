#! /usr/bin/python3
#
# The file copied from
# https://raw.githubusercontent.com/dloureiro/pandoc-watch/master/pandocwatch.py
# on "Sun Jun 17 16:33:03 IST 2018"

# Modified for python3 usage and some other extra arguments
# by Akshay Badola <akshay.badola.cs@gmail.com>
# on "Monday 27 July 2020 17:49:47 IST"

# Currently it also starts up a 'live-server' process which is a nodejs
# process. A simple python httpserver can also be used instead of that as the
# watcher is implemented already.

# TODO: Issue warning when incompatible options are used --biblatex and
# pandoc-citeproc conflict e.g.
#
# NOTE: FOR BLOG GENERATION - tags, keywords, SEO
# etc. should be updated from yaml in the markdown - if html has files it should
# be filename_html_files and not filename_files perhaps update pdf generation
# also to filename_pdf_files

import re
import os
import sys
import time
import yaml
import shlex
import pprint
from subprocess import Popen, PIPE
import datetime
import configparser
import argparse
from typing import Dict, Union, List, Any
from glob import glob
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib.machinery
import importlib.util


class COLORS:
    RED = '\033[31m'
    ALT_RED = '\033[91m'
    BRIGHT_RED = '\033[1;31m'
    ALT_BRIGHT_RED = '\033[1;91m'
    YELLOW = '\033[33m'
    BRIGHT_YELLOW = '\033[1;33m'
    BLUE = '\033[34m'
    BRIGHT_BLUE = '\033[1;34m'
    ALT_BLUE = '\033[94m'
    ALT_BRIGHT_BLUE = '\033[1;94m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'


def which(program):
    """
    This function is taken from
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    """
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


# NOTE: A more generic implementation is in common_pyutil
def load_user_module(modname):
    spec = importlib.machinery.PathFinder.find_spec(modname)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


# CHECK: What should configuration hold?
#
# TODO: Pandoc input and output processing should be with a better helper and
#       separate from config maybe
class Configuration:
    def __init__(self, config_file="config.ini", pandoc_path=None, live_server=False):
        self._pandoc_path = pandoc_path
        self._config_file = config_file
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
    def pandoc_path(self):
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = x
        else:
            print(f"Could not set new pandoc path {x}")

    @property
    def debug_level(self):
        return self._debug_level

    @debug_level.setter
    def debug_level(self, x):
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
        with open(filename, 'r') as f:
            in_file_pandoc_opts = yaml.load(f.read().split('---')[1], Loader=yaml.FullLoader)
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

    # TODO: Should be cached
    def get_watched(self):
        all_files = glob('**', recursive=True)
        elements = [f for f in all_files if self.is_watched(f)]
        return elements


def getext(filename):
    "Get the file extension."
    return os.path.splitext(filename)[-1].lower()


def get_now():
    return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def compile_files(md_files, config):
    post_processor = config.post_processor
    post = []
    if md_files and isinstance(md_files, str):
        if config.debug_level > 2:
            print(f"{COLORS.BLUE}Compiling{COLORS.ENDC}: {md_files}")
        commands = config.get_commands(md_files)
        post.append(recompile(commands, md_files))
    elif isinstance(md_files, list):
        for md_file in md_files:
            commands = config.get_commands(md_file)
            if config.debug_level > 2:
                print(f"{COLORS.BLUE}Compiling{COLORS.ENDC}: {md_file}")
            post.append(recompile(commands, md_file))
    if post_processor and post:
        print("Calling post_processor")
        post_processor(post)


def exec_tex_compile(command):
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    output = p.communicate()
    out = output[0].decode("utf-8")
    # err = output[1].decode("utf-8")
    opts = re.split(r'\s+', command)
    ind = [i for i, x in enumerate(opts) if "output-directory" in x]
    if ind:
        ind = ind[0]
    else:
        ind = None
    paras = out.split("\n\n")
    warnings = [x.replace("Warning", COLORS.ALT_RED + "Warning" + COLORS.ENDC)
                for x in paras if "Warning" in x]
    errors = [x.replace("Error", COLORS.BRIGHT_RED + "Error" + COLORS.ENDC).
              replace("error", COLORS.BRIGHT_RED + "error" + COLORS.ENDC)
              for x in paras if "Error" in x or "error" in x]
    fatal = [x.replace("Fatal", COLORS.BRIGHT_RED + "Fatal" + COLORS.ENDC).
             replace("fatal", COLORS.BRIGHT_RED + "fatal" + COLORS.ENDC)
             for x in paras if "fatal" in x.lower()]
    if fatal:
        print(f"pdftex {COLORS.BRIGHT_RED}fatal error{COLORS.ENDC}:")
        for i, x in enumerate(errors):
            x = x.replace("\n", "\n\t")
            print(f"{i+1}. \t{x}")
        return False
    if ind is not None:
        log_file_name = os.path.basename(opts[-1]).replace(".tex", ".log").strip()
        log_file = os.path.join(opts[ind+1].strip(), log_file_name)
        with open(log_file) as f:
            log_text = f.read().split("\n\n")
        warnings.extend([re.split(r'(\n\s+\n)', x)[0].
                         replace("Undefined",
                                 COLORS.ALT_RED +
                                 "Undefined" +
                                 COLORS.ENDC).replace("undefined",
                                                      COLORS.ALT_RED +
                                                      "undefined" +
                                                      COLORS.ENDC)
                         for x in log_text if "undefined" in x.lower()])
    if errors:
        print("pdftex errors:")
        for i, x in enumerate(errors):
            x = x.replace("\n", "\n\t")
            print(f"{i+1}. \t{x}")
    if warnings:
        print("pdftex warnings:")
        for i, x in enumerate(warnings):
            x = x.replace("\n", "\n\t")
            print(f"{i+1}. \t{x}")
    return True


def exec_command(command):
    print(f"Executing command : {command}")
    os.chdir(os.path.abspath(os.getcwd()))
    if command.startswith("pdflatex") or command.startswith("pdftex"):
        return exec_tex_compile(command)
    else:
        p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        output = p.communicate()
        out = output[0].decode("utf-8")
        err = output[1].decode("utf-8")
        success = not p.returncode
        if success:
            if out:
                out = out.strip("\n")
                print(f"Output from command: {out}")
            if err:
                err = err.strip("\n")
                print(f"No error from command, but: {COLORS.ALT_RED}{err}{COLORS.ENDC}")
            return True
        else:
            print(f"Error occured : {err}")
            return False


# NOTE: Only markdown files are watched and supported for now
def recompile(commands, md_file: str) -> None:  # FIXME: Actually it's a path
    if not isinstance(md_file, str) or not md_file.endswith('.md'):
        print(f"Not markdown file {md_file}")
        return
    print(f"\n{COLORS.BRIGHT_BLUE}Compiling {md_file} at {get_now()}{COLORS.ENDC}")
    postprocess = []
    # NOTE: commands' values are either strings or lists of strings
    for filetype, command_dict in commands.items():
        command = command_dict["command"]
        out_file = command_dict["out_file"]
        if isinstance(command, str):
            status = exec_command(command)
            if status:
                # mark status for processing
                postprocess.append({"in_file": md_file, "out_file": out_file})
        elif isinstance(command, list):
            statuses = []
            for com in command:
                statuses.append(exec_command(com))
            if all(statuses):
                postprocess.append({"in_file": md_file, "out_file": out_file})
    return postprocess


# TODO: This should only check for change in md files and associated <!-- includes --> files
class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config, root='.'):
        self.root = root
        self.config = config
        postproc_module = config.post_processor
        if postproc_module:
            try:
                self.config.post_processor = load_user_module(postproc_module).post_processor
                print(f"Post Processor module {postproc_module} successfully loaded")
            except Exception as e:
                print(f"Error occured while loading module {postproc_module}, {e}")
                self.config.post_processor = None
        else:
            print(f"No Post Processor module given")
            self.config.post_processor = None

    # NOTE: DEBUG
    # def on_any_event(self, event):
    #     print(str(event))

    def on_created(self, event):
        "Event fired when a new file is created"
        pwd = os.path.abspath(self.root) + '/'
        filepath = str(event.src_path)
        assert pwd in filepath
        filepath = filepath.replace(pwd, '')
        watched = self.config.is_watched(filepath)
        if watched:
            md_files = self.get_md_files(filepath)
            self.compile_stuff(md_files)

    def on_modified(self, event):
        "Event fired when a file is modified"
        if self.config.debug_level > 2:
            print("File " + event.src_path + " modified")
        md_files = self.get_md_files(event.src_path)
        if self.config.debug_level > 2:
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
        compile_files(md_files, self.config)
        print("Done\n")

    # CHECK: If it's working correctly
    def get_md_files(self, e):
        "Return all the markdown files which include the template"
        if e.endswith('.md'):
            return e
        elif e.endswith('template'):
            print("template" + e)
            md_files = []
            elements = self.config.get_watched()
            elements = [elem for elem in elements if elem.endswith('.md')]
            for elem in elements:
                with open(elem, 'r') as f:
                    text = f.read()
                if ("includes " + e) in text:
                    md_files.append(elem)
            return md_files


def parse_options():
    parser = argparse.ArgumentParser(
        description="Watcher for pandoc compilation",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--pandoc-path", dest="pandoc_path",
        required=False,
        help="Provide custom pandoc path. Must be full path to executable")
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
        "-d", "--debug-level", dest="debug_level",
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
    config = Configuration(config_file=args[0].config_file, pandoc_path=pandoc_path,
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

    config.debug_level = args[0].debug_level
    if config.debug_level > 2:
        print("\n".join(out.split("\n")[:3]))
        print("-" * len(out.split("\n")[2]))

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
    config.post_processor = args[0].post_processor
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
            print(f"Will compile {input_files} once.")
            compile_files(input_files, config)
    else:
        watched_elements = config.get_watched()
        print("watching ", watched_elements)
        if config.live_server:
            # print("Starting pandoc watcher and the live server ...")
            # p = Popen(['live-server', '--open=.'])
            # NOTE: Have to switch to Flask
            raise NotImplementedError
        else:
            print("Starting pandoc watcher only ...")
        event_handler = ChangeHandler(config)
        observer = Observer()
        observer.schedule(event_handler, os.getcwd(), recursive=True)
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

        # Code to recompile all the required files at startup not needed for now.
        # Though should include the code needed to compile all the
        # dependent files in a module later and not just templates.
        print("Stopping pandoc watcher ...")
        exit(0)


if __name__ == '__main__':
    main()
