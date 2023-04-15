from typing import List, Dict, Union, Optional, Tuple, Any
import re
import os
import sys
import time
import datetime
import importlib
from pathlib import Path

import yaml

from .const import COLORS


Pathlike = Union[str, Path]


class Debounce:
    """Debounce class for file watching.

    Run the commands after a specified number of seconds has elapsed

    Args:
        interval: The interal in milliseconds to wait


    """
    def __init__(self, interval: Union[int, float] = 10):
        self.interval = interval / 1000
        self._reset()

    def _reset(self):
        self.start: Union[int, float] = 0
        self.started = False

    def _start(self):
        self.start = time.time()
        self.objects = set()
        self.started = True

    def __call__(self, x):
        if not self.started:
            self._start()
        diff = (time.time() - self.start)
        if self.started and diff < self.interval:
            if x in self.objects:
                return None
            else:
                self.objects.add(x)
                # print(self.interval)
                # print(f"WILL RETURN {x} as NEW OBJECT after", time.time() - self.start)
                # if x.endswith(".md"):
                #     print(self.objects, x)
                return x
        else:
            self._start()
            self.objects.add(x)
            # print(self.interval)
            # print(f"WILL RETURN {x} as TIMEOUT after", time.time() - self.start)
            # if x.endswith(".md"):
            #     print(self.objects, x)
            return x


# TODO: The following should be replaced with separate tests
# assert in_file.endswith('.md')
# assert self._filetypes
def read_md_file_with_header(filename: Pathlike) -> Optional[Tuple[str, Dict[str, Any]]]:
    try:
        with open(filename) as f:
            splits = f.read().split('---', maxsplit=3)
            if len(splits) == 3:
                in_file_pandoc_opts = yaml.load(splits[1], Loader=yaml.FullLoader)
                in_file_text = splits[2]
            else:
                in_file_pandoc_opts = {}
                in_file_text = splits[0]
    except Exception as e:
        loge(f"Yaml parse error {e}. Will not compile.")
        return None
    return in_file_text, in_file_pandoc_opts


def compress_space(x: str):
    return re.sub(" +", " ", x)


def update_command(command: List[str], k: str, v: str) -> None:
    """Update a list of options by removing the current matching options.

    Args:
        command: List of command options
        k: Key to match
        v: Value to update with

    The list is updated in place.

    """
    existing = [x for x in command if "--" + k in x]
    for val in existing:
        command.remove(val)
    command.append(f"--{k}={v}")


def get_csl_or_template(key: str, val: str, dir: Path) -> str:
    """Get CSL or template file according to the value :code:`val`

    Args:
        key: One of "csl" or "template"
        val: The file path or file stem to search for, essentially
             the CSL or template name.
        dir: The directory in which to search

    The CSL or template file can be searched in a given directory with the file
    name or file name without suffix with some rules according to naming
    conventions.

    E.g., :code:`get_csl_or_template("csl", "ieee", "some_dir")` will search for
    "ieee" and "ieee.csl" in "some_dir".
    While, :code:`get_csl_or_template("template", "ieee", "some_dir")` will search for
    "default.ieee" and "ieee.template" in those directories

    """
    v = val
    if dir.joinpath(v).exists():
        v = str(dir.joinpath(v))
    else:
        candidates = [x.name for x in dir.iterdir()
                      if v in str(x)]
        if key == "template":
            if f"default.{v}" in candidates:
                v = str(dir.joinpath(f"default.{v}"))
            elif f"{v}.template" in candidates:
                v = str(dir.joinpath(f"{v}.template"))
        elif key == "csl":
            if f"{v}" in candidates:
                v = str(dir.joinpath(f"{v}"))
            elif f"{v}.csl" in candidates:
                v = str(dir.joinpath(f"{v}.csl"))
    return v


def which(program):
    """Search for program name in paths.

    This function is taken from
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    Though could actually simply use `which` shell command, but yeah on windows
    it may not be available.
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


def expandpath(x: Union[str, Path]):
    return Path(x).expanduser().absolute()


# NOTE: A more generic implementation is in common_pyutil
def load_user_module(modname):
    if modname.endswith(".py"):  # remove .py if it exists
        modname = modname[:-3]
    spec = importlib.machinery.PathFinder.find_spec(modname)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def get_now():
    return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def loge(message: str, newline: bool = True) -> str:
    "Log Error message"
    end = "\n" if newline else ""
    print(f"{COLORS.BRIGHT_RED}{message}{COLORS.ENDC}", end=end)
    return message


def logw(message: str, newline: bool = True) -> str:
    "Log Warning message"
    end = "\n" if newline else ""
    print(f"{COLORS.ALT_RED}{message}{COLORS.ENDC}", end=end)
    return message


def logd(message: str, newline: bool = True) -> str:
    "Log Debug message"
    end = "\n" if newline else ""
    print(message, end=end)
    return message


def logi(message: str, newline: bool = True) -> str:
    "Log Info message"
    end = "\n" if newline else ""
    print(message, end=end)
    return message


def logbi(message: str, newline: bool = True) -> str:
    "Log Info message with color blue"
    end = "\n" if newline else ""
    print(f"{COLORS.BLUE}{message}{COLORS.ENDC}", end=end)
    return message


def logbbi(message: str, newline: bool = True) -> str:
    """Log message with bright blue color

    Args:
        message: Message
        newline: Print newline


    """
    end = "\n" if newline else ""
    print(f"{COLORS.BRIGHT_BLUE}{message}{COLORS.ENDC}", end=end)
    return message
