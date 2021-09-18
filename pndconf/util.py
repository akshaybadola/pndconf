from typing import List, Dict, Union, Optional
import os
import sys
import datetime
import importlib
from pathlib import Path

from .colors import COLORS


def update_command(command: List[str], k: str, v: str) -> None:
    existing = [x for x in command if "--" + k in x]
    for val in existing:
        command.remove(val)
    command.append(f"--{k}={v}")


def get_csl_or_template(key: str, val: str, dir: Path):
    v = val
    if dir.joinpath(v).exists():
        v = dir.joinpath(v)
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
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def get_now():
    return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def loge(message, newline=True):
    "Log Error message"
    end = "\n" if newline else ""
    print(f"{COLORS.BRIGHT_RED}{message}{COLORS.ENDC}", end=end)


def logw(message, newline=True):
    "Log Warning message"
    end = "\n" if newline else ""
    print(f"{COLORS.ALT_RED}{message}{COLORS.ENDC}", end=end)


def logd(message, newline=True):
    "Log Debug message"
    end = "\n" if newline else ""
    print(message, end=end)


def logi(message, newline=True):
    "Log Info message"
    end = "\n" if newline else ""
    print(message, end=end)


def logbi(message, newline=True):
    "Log Info message"
    end = "\n" if newline else ""
    print(f"{COLORS.BLUE}{message}{COLORS.ENDC}", end=end)
