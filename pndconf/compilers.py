from typing import Dict, Any, Union, List, Optional, cast
import os
import re
import chardet
import yaml
from subprocess import Popen, PIPE

from .util import get_now as now
from .colors import COLORS


PostProc = List[Dict[str, str]]


# FIXME: Use log* for logging
class TexCompiler:
    """Pretty printed output from tex compiler.

    Args:
        env_vars: Additional environment variables to append to the shell command
    """
    def __init__(self, env_vars: str = ""):
        self.log_file_encoding = "ISO-8859-1"
        self.env_vars = env_vars

    def compile(self, command: str) -> bool:
        """Compile with `command`

        Args:
            command: Command string

        """
        if self.env_vars:
            p = Popen(self.env_vars + " ; " + command, stdout=PIPE, stderr=PIPE, shell=True)
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        output = p.communicate()
        out = output[0].decode("utf-8")
        # err = output[1].decode("utf-8")
        opts = re.split(r'\s+', command)
        inds = [i for i, x in enumerate(opts) if "output-directory" in x]
        if inds:
            ind: Optional[int] = inds[0]
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
                log_text = log_bytes.decode(self.log_file_encoding, "ignore").split("\n\n")
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


tex_compiler = TexCompiler()


def exec_command(command: str, input: Optional[str] = None, noshell: bool = False):
    """Execute a command via :class:`Popen`.

    The command is exectued with `shell=True`. Use `noshell=True` for inverting
    that behaviour

    Args:
        command: The command to execute
        input: Optional input to give to command via stdin
        noshell: Whether not to use shell

    """
    prefix = "Executing command: "
    splits = command.split(" ")
    splits = [splits[i*4:(i+1)*4] for i in range(len(splits)//4)]  # type: ignore
    cmd = ("\n" + " "*len(prefix)).join([" ".join(x) for x in splits])
    shell = not noshell
    print(f"{prefix}{cmd}")
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
        if input:
            p = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=shell)
            output = p.communicate(input=input.encode())
        else:
            p = Popen(command, stdout=PIPE, stderr=PIPE, shell=shell)
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
            if err:
                print(f"Error occured : {err}")
            elif "pdflatex" in p.args or "pdftex" in p.args:
                print(f"Got err return from pdflatex. Check log in output directory")
            else:
                print(f"Some unknown error reported. If all outputs seem fine, then ignore it.")
            return False


def markdown_compile(commands: Dict[str, Dict[str, Union[List[str], str]]],
                     md_file: str) -> Optional[PostProc]:  # FIXME: Actually it's a path
    """Compile markdown to output format with pandoc.

    Args:
        commands: :class:`dict` of commands with output filetypes as keys
        md_file: The markdown input file to compile
    """
    if not isinstance(md_file, str) or not md_file.endswith('.md'):
        print(f"Not markdown file {md_file}")
        return None
    print(f"\n{COLORS.BRIGHT_BLUE}Compiling {md_file} at {now()}{COLORS.ENDC}")
    postprocess = []
    # NOTE: commands' values are either strings or lists of strings
    for filetype, command_dict in commands.items():
        command = command_dict["command"]
        out_file: str = cast(str, command_dict["out_file"])
        pandoc_opts = command_dict["in_file_opts"]
        file_text: str = cast(str, command_dict["text"])
        if pandoc_opts:
            input = "---\n".join(["", yaml.dump(pandoc_opts), file_text])
        else:
            input = file_text
        if isinstance(command, str):
            status = exec_command(command, input)
            if status:
                # mark status for processing
                postprocess.append({"in_file": md_file, "out_file": out_file})
        elif isinstance(command, list):
            statuses = []
            for com in command:
                statuses.append(exec_command(com, input))
            if all(statuses):
                postprocess.append({"in_file": md_file, "out_file": out_file})
    return postprocess
