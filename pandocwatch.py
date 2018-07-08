#! /usr/bin/env python3
# The file copied from https://raw.githubusercontent.com/dloureiro/pandoc-watch/master/pandocwatch.py
# on Sun Jun 17 16:33:03 IST 2018
# and modified for python3 usage and some other extra arguments by Akshay Badola <akshay.badola.cs@gmail.com>
# Currently it also starts up a 'live-server' process which is a nodejs
# process. A simple python httpserver can also be used instead of
# that as the watcher is implemented already.

import re
import os
import sys
import time
import subprocess
import datetime
import configparser
import argparse
from glob import glob
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


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


class Singleton:
    """
    A non-thread-safe helper class to ease implementing singletons.
    This should be used as a decorator -- not a metaclass -- to the
    class that should be a singleton.

    The decorated class can define one `__init__` function that
    takes only the `self` argument. Other than that, there are
    no restrictions that apply to the decorated class.

    To get the singleton instance, use the `Instance` method. Trying
    to use `__call__` will result in a `TypeError` being raised.

    Limitations: The decorated class cannot be inherited from.

    This singleton class is taken from
    http://stackoverflow.com/questions/42558/python-and-the-singleton-pattern

    """

    def __init__(self, decorated):
        self._decorated = decorated

    def Instance(self):
        """
        Returns the singleton instance. Upon its first call, it creates a
        new instance of the decorated class and calls its `__init__` method.
        On all subsequent calls, the already created instance is returned.

        """
        try:
            return self._instance
        except AttributeError:
            self._instance = self._decorated()
            return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `Instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)

# What should configuration hold?
@Singleton
class Configuration:
    def __init__(self):
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read('config.ini')
        self._excluded_regex = []
        self._excluded_extensions = []
        self._excluded_folders = []
        self._included_extensions = []
        self._excluded_files = []

    def setGenerationOpts(self, filetypes, pandoc_options):
        self._filetypes = filetypes
        if pandoc_options:
            for section in filetypes:
                for opt in pandoc_options:
                    if opt.startswith('--'):
                        opt_key, opt_value = opt.split('=')
                        self._conf[section][opt_key] = self._conf[section][opt_value]
                    else:
                        self._conf[section][opt] = ''

    # should be a better way to compile with pdflatex
    def get_commands(self, filename):
        assert filename.endswith('.md')
        assert self._filetypes

        commands = []
        filename = filename.replace('.md', '')
        pdflatex = 'pdflatex  -file-line-error -output-directory '\
                   + filename + '_files' + ' -interaction=nonstopmode '\
                   + '"\input"' + filename + '.tex'
        for ft in self._filetypes:
            command = []
            for k, v in self._conf[ft].items():
                if k.startswith('--'):
                    command.append(k + '=' + v if v else k)
                else:
                    if k == '-o':
                        command.append(k + ' ' + filename + '.' + v)
                    else:
                        command.append(k + (' ' + v) if v else '')
            command = 'pandoc ' + ' '.join(command) + ' ' + filename + '.md'
            if ft == 'pdf':
                command = [command, 'mkdir -p ' + filename + '_files']
                command.append(pdflatex)
            commands.append(command)
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


# Only markdown files are watched and supported for now
def recompile(md_file):
    print("Compiling " + md_file)
    assert type(md_file) == str
    assert md_file.endswith('.md')

    config = Configuration.Instance()
    commands = config.get_commands(md_file)

    def exec_command(command):
        print("Updating the output at %s" % get_now(), file=sys.stderr)
        print("executing command : " + command)
        os.chdir(os.path.abspath(os.getcwd()))
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True)
            print("No error found" + output.decode('utf-8'))
        except subprocess.CalledProcessError as err:
            print("Error : " + err.output.decode('utf-8'))

    # commands's entities are either strings or lists of strings
    for command in commands:
        if isinstance(command, str):
            exec_command(command)
        elif isinstance(command, list):
            for com in command:
                exec_command(com)

class ChangeHandler(FileSystemEventHandler):
    # def __init__(self, server_process):
    #     self.server_process = server_process
    #     print(self.server_process)
    #     self.config = Configuration.Instance()

    def __init__(self, root='.'):
        self.root = root
        self.config = Configuration.Instance()

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
        if md_files and type(md_files) == str:
            print("compiling" + str(md_files))
            recompile(md_files)
        elif type(md_files) == list:
            for md_file in md_files:
                print("compiling" + str(md_file))
                recompile(md_file)
        print("Done")

        # out, err = self.server_process.communicate()
        # if err:
        #     print("Error occured\n\n", err.decode('utf-8').split('\n'))
        # elif out:
        #     print(out.decode('utf-8').split('\n'))

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


def parseOptions():
    pandoc_output = subprocess.Popen(
        ["pandoc", "--help"], stdout=subprocess.PIPE).communicate()[0]
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
    # parser.add_argument(
    #     "--live-server", dest="live_server",
    #     type=bool, default=True, required=False,
    #     help="Start a live server? Requires live-server to be installed\
    #     in the node global namespace")
    parser.add_argument(
        "--live-server", dest="live_server",
        action='store_true',
        help="Start a live server? Requires live-server to be installed\
        in the nodejs global namespace")
    args = parser.parse_known_args()

    config = Configuration.Instance()

    if args[0].live_server:
        config.live_server = True
    else:
        config.live_server = False

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

    config.setGenerationOpts(args[0].generation.split(','), ' '.join(args[1]))


def main():
    pandoc_path = which("pandoc")

    if not pandoc_path:
        print("pandoc executable must be in the path to be used by pandoc-watch!")
        exit()

    parseOptions()
    config = Configuration.Instance()

    watched_elements = config.get_watched()
    print("watching ", watched_elements)

    if config.live_server:
        print("Starting pandoc watcher and the live server ...")
        p = subprocess.Popen(['live-server', '--open=.'])
    else:
        print("Starting pandoc watcher only ...")

    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, os.getcwd(), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt as err:
        print(str(err))
        if config.live_server:
            p.terminate()
        observer.stop()

    # Code to recompile all the required files at startup not needed for now.
    # Though should include the code needed to compile all the
    # dependent files in a module later and not just templates.
    print("Stopping pandoc watcher ...")
    exit()


if __name__ == '__main__':
    main()
