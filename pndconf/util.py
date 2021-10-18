from typing import List, Dict, Union, Optional
import re
import os
import sys
import time
import datetime
import importlib
from pathlib import Path
from subprocess import Popen, PIPE

from bibtexparser import bparser, bwriter

from .colors import COLORS


class Debounce:
    # Should we instead make a class where all events are timed?
    def __init__(self, interval=10):
        self.interval = interval / 1000
        self._reset()

    def _reset(self):
        self.start = 0
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


# NOTE: An alternative library is :mod:`biblib`, but that's not been updated
#       for a while.
def generate_bibtex(in_file: Path, metadata: Dict, style: str,
                    text: str, pandoc_path: Path) -> str:
    """Generate bibtex for markdown file.

    Args:
        in_file: input file
        references: Metadata for the file including bibliography files and
                    references in the metadata

    The bibtex file is generated in the same directory as `in_file` with a
    ".bib" suffix.

    We use :mod:`re` for spliting the bibtex file.  Searching with :mod:`re` is
    faster than parsing all the bib entries with :mod:`bibtexparser`.

    """
    out_file = in_file.parent.joinpath(in_file.stem + ".bib")
    bib_files = metadata["bibliography"]
    splits = []
    for bf in bib_files:
        with open(bf) as f:
            temp = f.read()
            splits.extend([*filter(None, re.split(r'(@.+){', temp))])
    entries: Dict[str, str] = {}
    for i in range(0, len(splits), 2):
        key = splits[i+1].split(",")[0]
        entries[key] = splits[i] + "{" + splits[i+1]
    bibs = []
    text_citations = re.findall(r'\[@(.+?)\]', text)
    for t in text_citations:
        if t in entries:
            bibs.append(entries[t])
    # NOTE: parser is used primarily to validate the bibtexs. We might use it to
    #       transform them later
    parser = bparser.BibTexParser(common_strings=True)
    try:
        bibtex = parser.parse("\n".join(bibs))  # noqa
        # bibs = transform_bibtex(bibtex)
    except Exception:
        msg = "Error while parsing bibtexs. Check sources."
        raise ValueError(msg)
    p = Popen(f"{pandoc_path} -r markdown -s -t {style} {in_file}",
              shell=True, stdout=PIPE, stderr=PIPE)
    yaml_refs, err = p.communicate()
    with open(out_file, "w") as f:
        f.write("".join(bibs))
        f.write(yaml_refs.decode("utf-8"))
    metadata["bibliography"] = [str(out_file.absolute())]
    return str(out_file)


def transform_bibtex(bibtex) -> List[str]:
    # writer = bwriter.BibTexWriter(write_common_strings=True)
    # retval = []
    # for entry in bibtex.entries:
    #     retval.append(writer._entry_to_bibtex(transform(entry)))
    pass


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


def get_csl_or_template(key: str, val: str, dir: Path):
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
    return message


def logw(message, newline=True):
    "Log Warning message"
    end = "\n" if newline else ""
    print(f"{COLORS.ALT_RED}{message}{COLORS.ENDC}", end=end)
    return message


def logd(message, newline=True):
    "Log Debug message"
    end = "\n" if newline else ""
    print(message, end=end)
    return message


def logi(message, newline=True):
    "Log Info message"
    end = "\n" if newline else ""
    print(message, end=end)
    return message


def logbi(message, newline=True):
    "Log Info message"
    end = "\n" if newline else ""
    print(f"{COLORS.BLUE}{message}{COLORS.ENDC}", end=end)
    return message
