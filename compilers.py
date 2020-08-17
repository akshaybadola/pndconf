import os
import re
import chardet
from subprocess import Popen, PIPE
from typing import Dict, Any

from util import get_now
from colors import COLORS


class TexCompiler:
    def __init__(self):
        self.log_file_encoding = "ISO-8859-1"

    def compile(self, command):
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
            with open(log_file, "rb") as f:
                log_bytes = f.read()
            try:
                log_text = log_bytes.decode(self.log_file_encoding).split("\n\n")
            except UnicodeDecodeError as e:
                print(f"UTF codec failed for log_file {log_file}. Error {e}")
                self.log_file_encoding = chardet.detect(log_bytes)["encoding"]
                print(f"Opening with new codec {self.log_file_encoding}")
                log_text = log_bytes.decode(self.log_file_encoding, "ignore")
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


# NOTE: This should execute, but will the function retain the instance?
tex_compiler = TexCompiler()


def exec_command(command):
    print(f"Executing command : {command}")
    os.chdir(os.path.abspath(os.getcwd()))
    if command.startswith("pdflatex") or command.startswith("pdftex"):
        try:
            # NOTE: Changed to TexCompiler
            # status = exec_tex_compile(command)
            status = tex_compiler.compile(command)
            return status
        except Exception as e:
            print(f"Error occured while compiling file {e}")
            return False
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
                err = "\n".join([f"\t{e}" for e in err.split("\n")])
                print(f"No error from command, but: {COLORS.ALT_RED}\n{err}{COLORS.ENDC}")
            return True
        else:
            print(f"Error occured : {err}")
            return False


# NOTE: Only markdown files are watched and supported for now
def markdown_compile(commands: Dict[str, str], md_file: str) -> Any:  # FIXME: Actually it's a path
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
        with open(log_file, "rb") as f:
            log_bytes = f.read()
        try:
            log_text = log_bytes.decode("utf-8").split("\n\n")
        except UnicodeDecodeError as e:
            print(f"UTF codec failed for log_file {log_file}. Error {e}")
            encoding = chardet.detect(log_bytes)["encoding"]
            print(f"Opening with codec {encoding}")
            log_text = log_bytes.decode(encoding, "ignore")
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
