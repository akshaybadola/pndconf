#! /usr/bin/env python3
#
# The file copied from https://raw.githubusercontent.com/dloureiro/pandoc-watch/master/pandocwatch.py
# on Sun Jun 17 16:33:03 IST 2018
# and modified for python3 usage and some other extra arguments by Akshay Badola <akshay.badola.cs@gmail.com>
# Currently it also starts up a 'live-server' process which is a nodejs
# process. A simple python httpserver can also be used instead of
# that as the watcher is implemented already.

# TODO: Issue warning when incompatible options are used --biblatex and pandoc-citeproc conflict e.g.
# NOTE: FOR BLOG GENERATION
# - tags, keywords, SEO etc. should be updated from yaml in the markdown
# - if html has files it should be filename_html_files and not filename_files
#   perhaps update pdf generation also to filename_pdf_files

import re
import os
import sys
import time
import yaml
import subprocess
import datetime
import configparser
import argparse
from typing import Dict, List, Union, List, Any
from glob import glob
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib.machinery
import importlib.util


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
class Configuration:
    def __init__(self, config_file="config.ini", pandoc_path=None, live_server=False):
        if pandoc_path is not None:
            self._pandoc_path = pandoc_path
            print(f"Pandoc path is {pandoc_path}")
        self._config_file = config_file
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read(self._config_file)
        self._excluded_regex = []
        self._excluded_extensions = []
        self._excluded_folders = []
        self._included_extensions = []
        self._excluded_files = []
        # out_string = str(subprocess.run("uname -a".split(), stdout=subprocess.PIPE).stdout).lower()
        # self.buntu = "buntu" in out_string
        # print(out_string, self.buntu)

    @property
    def pandoc_path(self):
        return self._pandoc_path

    @pandoc_path.setter
    def pandoc_path(self, x):
        if os.path.exists(os.path.expanduser(x)):
            self._pandoc_path = x
        else:
            print("Could not set pandoc path")
            import ipdb; ipdb.set_trace()

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

    # TODO: should be a better way to compile with pdflatex
    # TODO: User defined options should override the default ones and the file ones
    def get_commands(self, filename: str) -> Dict[str, Dict[str, str]]:
        assert filename.endswith('.md')
        assert self._filetypes
        with open(filename, 'r') as f:
            in_file_pandoc_opts = yaml.load(f.read().split('---')[1])
        commands = {}
        filename = filename.replace('.md', '')
        pdflatex = 'pdflatex  -file-line-error -output-directory '\
                   + filename + '_files' + ' -interaction=nonstopmode '\
                   + '--synctex=1 ' + '"\input"' + filename + '.tex'
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

    def get_watched(self):
        all_files = glob('**', recursive=True)
        elements = [f for f in all_files if self.is_watched(f)]
        return elements


def getext(filename):
    "Get the file extension."
    return os.path.splitext(filename)[-1].lower()


def get_now():
    return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")


# NOTE: Only markdown files are watched and supported for now
def recompile(commands, md_file: str) -> None:  # FIXME: Actually it's a path
    def exec_command(command):
        print("Updating the output at %s" % get_now(), file=sys.stderr)
        print("executing command : " + command)
        os.chdir(os.path.abspath(os.getcwd()))
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True)
            print("No error found" + output.decode('utf-8'))
            return True
        except subprocess.CalledProcessError as err:
            print("Error : " + err.output.decode('utf-8'))
            return False
    print("Compiling " + md_file)
    assert type(md_file) == str
    assert md_file.endswith('.md')
    postprocess = []
    # NOTE: commands' values are either strings or lists of strings
    for filetype, command_dict in commands.items():
        command = command_dict["command"]
        out_file = command_dict["out_file"]
        if isinstance(command, str):
            output = exec_command(command)
            if output:
                # mark output for processing
                postprocess.append({"file": md_file, "out_file": out_file})
        elif isinstance(command, list):
            outputs = []
            for com in command:
                outputs.append(exec_command(com))
            if all(outputs):
                postprocess.append({"file": md_file, "out_file": out_file})
    return postprocess


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, config, root='.', postproc_module=None):
        self.root = root
        self.config = config
        if postproc_module:
            try:
                self.post_processor = load_user_module(postproc_module).post_processor
            except Exception as e:
                print(f"Error occured while loading module {postproc_module}, {e}")
                self.post_processor = None
        else:
            self.post_processor = None

    # def on_any_event(self, event):
    #     print(str(event))

    def on_created(self, event):
        # Should be root instead of '.'
        pwd = os.path.abspath(self.root) + '/'
        filepath = str(event.src_path)
        assert pwd in filepath
        filepath = filepath.replace(pwd, '')
        watched = self.config.is_watched(filepath)
        if watched:
            self.compile_stuff(filepath)

    def on_modified(self, event):
        print("file " + event.src_path + " modified")
        self.compile_stuff(event.src_path)

    def compile_stuff(self, e):
        md_files = self.get_md_files(e)
        # The assumption below should not be on the type of variable
        # Though assumption is actually valid as there's only a
        # single file at a time which is checked
        post = []
        if md_files and type(md_files) == str:
            print("compiling" + str(md_files))
            commands = self.config.get_commands(md_files)
            post.append(recompile(commands, md_files))
        elif type(md_files) == list:
            for md_file in md_files:
                commands = self.config.get_commands(md_file)
                print("compiling" + str(md_file))
                post.append(recompile(commands, md_file))
        if self.post_processor:
            print("Calling post_processor")
            self.post_processor(post)
        print("Done")

    # returns all the markdown files which include the template
    def get_md_files(self, e):
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


def parse_options(pandoc_path=None):
    if pandoc_path is None:
        pandoc_path = "pandoc"
    pandoc_output = subprocess.Popen(
        [pandoc_path, "--help"], stdout=subprocess.PIPE).communicate()[0]
    added_epilog = '\n'.join(pandoc_output.decode("utf-8").split("\n")[1:])
    epilog = "------------------------------------------\
\nPandoc standard options are: \n\n" + added_epilog
    parser = argparse.ArgumentParser(
        description="Watcher for pandoc compilation",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "-e", "--exclude", dest="exclusions",
        default=".pdf,.tex,doc,bin,common", required=False,
        help="The extensions (.pdf for pdf files) or the folders to\
        exclude from watch operations separated with commas")
    parser.add_argument(
        "--exclude-filters", dest="exclude_filters",
        default="#,~", required=False,
        help="Files with specific regex to exclude. Should not contain ',' ")
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
        "--run-once", dest="run_once",
        action="store_true",
        help="Whether to generate without starting the watchdog for file changes")
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
        help="Start a live server? Requires live-server to be installed\
        in the nodejs global namespace")
    args = parser.parse_known_args()

    if args[0].live_server:
        raise NotImplementedError
    config = Configuration(pandoc_path=pandoc_path, live_server=args[0].live_server)
    # since it assumes that extensions startwith '.', I'll remove
    # the check from the globber later
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

    # Better checks
    # These options will override pandoc options in all the sections
    # of the config file
    for arg in args[1]:
        assert arg.startswith('-')
        if arg.startswith('--'):
            assert '=' in arg
    print("Will generate for %s" % args[0].generation.upper())
    config.set_generation_opts(args[0].generation.split(','), ' '.join(args[1]))
    if args[0].run_once:
        return config, True, args[0].input_files.split(",")
    else:
        return config, False, None


# FIXME: A bunch of this code is annoying. Gotta reformat
def main():
    # pandoc_path = which("pandoc")
    pandoc_path = os.path.expanduser("/usr/bin/pandoc")
    if not os.path.exists(pandoc_path):
        print("pandoc executable must be in the path to be used by pandoc-watch!")
        exit()
    config, run_once, input_files = parse_options(pandoc_path)
    if run_once:
        # remove null strings
        input_files = [*filter(None, input_files)]
        if not input_files:
            print("Error! No input files given")
        else:
            # run for only the given files
            raise NotImplementedError
    else:
        watched_elements = config.get_watched()
        print("watching ", watched_elements)
        if config.live_server:
            # print("Starting pandoc watcher and the live server ...")
            # p = subprocess.Popen(['live-server', '--open=.'])
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
        exit()


if __name__ == '__main__':
    main()
