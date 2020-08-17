import os
import sys
import datetime
import importlib

from colors import COLORS


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
