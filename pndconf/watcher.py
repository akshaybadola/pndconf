from typing import Dict, Union, List, Optional, Callable
import os
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from .util import logd, loge, logi, logbi, logw, Debounce


class ChangeHandler(FileSystemEventHandler):
    """Watch for changes in file system and fire events.

    ChangeHandler fires the commands corresnponding to the event and the
    Configuration instance `config`
    """
    def __init__(self, root: Path, is_watched: Callable[[str], bool],
                 get_watched: Callable[[], List[Path]],
                 compile_func: Callable[[Union[str, List[str]]], None],
                 log_level: int):
        self.root = root
        self.is_watched = is_watched
        self.get_watched = get_watched
        self.compile_files = compile_func
        self.log_level = log_level
        self.debounce = Debounce(3000)
        self.count = 0

    # NOTE: DEBUG
    # def on_any_event(self, event):
    #     print(str(event))

    def on_created(self, event: FileSystemEvent):
        "Event fired when a new file is created"
        pwd = os.path.abspath(self.root) + '/'
        filepath = str(os.path.abspath(event.src_path))
        assert pwd in filepath
        filepath = filepath.replace(pwd, '')
        watched = self.is_watched(filepath)
        if watched:
            md_files = self.get_md_files(filepath)
            self.compile_stuff(md_files)

    def on_modified(self, event: FileSystemEvent):
        "Event fired when a file is modified"
        src_path = event.src_path
        # NOTE: Hack around bug in watchdog where file modified event is called
        #       twice on a single modification or some reason
        src_path = self.debounce(src_path)
        if src_path:
            if self.log_level > 2:
                logd(f"File {src_path} modified")
            md_files = self.get_md_files(src_path)
            if self.log_level > 2:
                logd(f"DEBUG: {md_files}")
            if md_files:
                self.count += 1
                # print(md_files, self.count)
                self.compile_stuff(md_files)

    # NOTE: Maybe rename this function
    def compile_stuff(self, md_files: Union[str, List[str]]) -> None:
        "Compile if required when an event is fired"
        # NOTE: The assumption below should not be on the type of variable
        #       Though assumption is actually valid as there's only a
        #       single file at a time which is checked
        self.compile_files(md_files)
        logbi("Done\n")

    # CHECK: If it's working correctly
    def get_md_files(self, e):
        "Return all the markdown files which include the template"
        if e.endswith('.md'):
            return e
        elif e.endswith('template'):
            logd(f"Template {e}")
            md_files = []
            elements = self.get_watched()
            elements = [elem for elem in elements if elem.endswith('.md')]
            for elem in elements:
                with open(elem, 'r') as f:
                    text = f.read()
                if ("includes " + e) in text:
                    md_files.append(elem)
            return md_files
