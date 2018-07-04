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
import json
from functools import reduce
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


@Singleton
class Configuration:
    def __init__(self):
        self._conf = configparser.ConfigParser()
        self._conf.optionxform = str
        self._conf.read('config.ini')
        self._dirContentAndTime = {}
        self._excludedFileRegex = []
        self._excludedFileExtensions = []
        self._excludedFolders = []
        self._includedFileExtensions = []
        self._excludedFiles = []

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

    def getCommands(self, filename):
        assert filename.endswith('.md')
        assert self._filetypes

        print(list(self._conf.sections()))
        commands = []
        filename = filename.replace('.md', '')
        texstring = '; mkdir -p ' + filename + '_files ' + '; pdflatex  -file-line-error -output-directory ' + filename + '_files' + ' -interaction=nonstopmode "\input" ' + filename + '.tex'
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
            commands.append('pandoc ' + ' '.join(command) + ' ' + filename + '.md')
            commands = [command + texstring
                        if filename + '.tex' in command else command
                        for command in commands]
        return commands

    def setIncludedFileExtensions(self, included_file_extensions):
        self._includedFileExtensions = included_file_extensions

    def getIncludedFileExtensions(self):
        return self._includedFileExtensions

    def setExcludedFileExtensions(self, excluded_file_extensions):
        self._excludedFileExtensions = excluded_file_extensions

    def getExcludedFileExtensions(self):
        return self._excludedFileExtensions

    def setExcludedFileRegex(self, excluded_filters):
        self._excludedFileRegex = excluded_filters

    def getExcludedFileRegex(self):
        return self._excludedFileRegex

    def setExcludedFiles(self, excluded_files):
        self._excludedFiles = excluded_files

    def getExcludedFiles(self):
        return self._excludedFiles

    def setDirContentAndTime(self, e):
        self._dirContentAndTime[e] = os.path.getmtime(e)

    def getDirContentAndTime(self):
        return self._dirContentAndTime

    def setExcludedFolders(self, excluded_folders):
        self._excludedFolders = excluded_folders

    def getExcludedFolders(self):
        return self._excludedFolders

    def isWatched(self, filepath):
        watched = False
        for ext in self._includedFileExtensions:
            if filepath.endswith(ext):
                watched = True
        for ext in self._excludedFileExtensions:
            if filepath.endswith(ext):
                watched = False
        for folder in self._excludedFolders:
            if folder in filepath:
                watched = False
        for fn in self._excludedFiles:
            if fn in filepath:
                watched = False
        for regex in self._excludedFileRegex:
            if re.findall(regex, filepath):
                watched = False
        return watched


def getext(filename):
    "Get the file extension."
    return os.path.splitext(filename)[-1].lower()


def get_now():
    return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def getDirectoryWatchedElements():
    config = Configuration.Instance()
    elements = []
    included_extensions = config.getIncludedFileExtensions()
    excluded_regex = config.getExcludedFileRegex()
    if included_extensions:
        for extension in included_extensions:
            if extension.startswith('.'):
                elements += glob('*' + extension)
                elements += glob('*/*' + extension)
            else:
                elements += glob('*.' + extension)
                elements += glob('*/*' + extension)
    else:
        for path in os.listdir(os.getcwd()):
            path_to_remove = False
            for extension in config.getExcludedFileExtensions():
                if path.endswith(extension):
                    path_to_remove = True
                    break
            if not path_to_remove and path not in config.getExcludedFolders():
                elements.append((path, os.stat(path).st_mtime))
    filtered = []
    for e in elements:
        if not reduce(lambda x, y: x or y, [re.findall(r, e) for r in excluded_regex]):
            filtered.append(e)
    return filtered


# Only markdown files are watched and supported for now
def recompile(md_file):
    print("Compiling " + md_file)
    assert type(md_file) == str
    assert md_file.endswith('.md')

    config = Configuration.Instance()
    commands = config.getCommands(md_file)

    for command in commands:
        print("Updating the output at %s" % get_now(), file=sys.stderr)
        print("executing command : " + command)
        os.chdir(os.path.abspath(os.getcwd()))
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True)
            print("No error found" + output.decode('utf-8'))
        except subprocess.CalledProcessError as err:
            print("Error : " + err.output.decode('utf-8'))


class ChangeHandler(FileSystemEventHandler):
    # def __init__(self, server_process):
    #     self.server_process = server_process
    #     print(self.server_process)
    #     self.config = Configuration.Instance()

    def __init__(self):
        self.config = Configuration.Instance()

    def on_any_event(self, event):
        print(str(event))

    def on_created(self, event):
        pwd = os.path.abspath('.') + '/'
        filepath = str(event.src_path)
        assert pwd in filepath
        filepath = filepath.replace(pwd, '')
        watched = self.config.isWatched(filepath)
        if watched:
            self.config.setDirContentAndTime(filepath)
            self.compile_stuff(filepath)

    def on_modified(self, event):
        print("modified")
        dir_content = self.config.getDirContentAndTime()
        # serching for existing file that has been modified
        for e, t in dir_content.items():
            if os.path.getmtime(e) > t:
                print("File " + e + " has changed")
                self.config.setDirContentAndTime(e)
                self.compile_stuff(e)
        # if not found:
        #     print("Something else changed. Not compiling")
        # recompile()

    def compile_stuff(self, e):
        md_files = self.get_md_files(e)
        # The assumption below should not be on the type of variable
        # Though assumption is actually valid as there's only a
        # single file at a time which is checked
        if md_files and type(md_files) == str:
            print(md_files)
            recompile(md_files)
        elif type(md_files) == list:
            for md_file in md_files:
                print(md_file)
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
            print(e)
            md_files = []
            elements = getDirectoryWatchedElements()
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
    args = parser.parse_known_args()

    config = Configuration.Instance()

    # since it assumes that extensions startwith '.', I'll remove
    # the check from the globber later
    if args[0].exclude_filters:
        print(str(args[0].exclude_filters.split(',')))
        config.setExcludedFileRegex(args[0].exclude_filters.split(','))
    if args[0].inclusions:
        inclusions = args[0].inclusions
        inclusions = inclusions.split(",")
        config.setIncludedFileExtensions(
            [value for value in inclusions if value.startswith(".")])
        if args[0].excluded_files:
            for ef in args[0].excluded_files.split(','):
                assert type(ef) == str
            config.setExcludedFiles(args.excluded_files.split(','))
    elif args[0].exclusions:
        exclusions = args[0].exclusions
        exclusions = exclusions.split(",")
        config.setExcludedFileExtensions(
            [value for value in exclusions if value.startswith(".")])
        config.setExcludedFolders(
            list(set(exclusions).symmetric_difference(
                set(config.getExcludedFileExtensions()))))
    elif args[0].inclusions and args[0].exclusions:
        print("Can't have both inclusions and exclusions.\
        The system will exit")
        sys.exit(0)

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

    config = Configuration.Instance()
    parseOptions()

    watched_elements = getDirectoryWatchedElements()
    print("watching ", watched_elements)
    for e in watched_elements:
        config.setDirContentAndTime(e)

    print("Starting pandoc watcher and the live server ...")
    p = subprocess.Popen(['live-server', '--open=.'])

    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, os.getcwd(), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt as err:
        print(str(err))
        p.terminate()
        observer.stop()

    # Code to recompile all the required files at startup not needed for now.
    # Though should include the code needed to compile all the
    # dependent files in a module later and not just templates.
    # json.dump(config.getDirContentAndTime(), open('.watched_elements', 'w'))
    print("Stopping pandoc watcher ...")
    exit()


if __name__ == '__main__':
    main()
