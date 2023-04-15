from typing import List, Dict, Union, Optional, Callable
import re
from pathlib import Path
from subprocess import Popen, PIPE

from bibtexparser import bparser, bwriter
from common_pyutil.functional import compose, identity, rpartial

from . import transforms


def compose_transforms(transform_names: List[str]) -> Callable:
    bib_transforms = []
    for name in transform_names:
        match = re.match(r"(.+?)\((.+)\)", name)
        if match:
            func_name, args = re.match(r"(.+?)\((.+)\)", name).groups()  # type: ignore
            args = args.split(":")
            func = getattr(transforms, func_name)
            bib_transforms.append(rpartial(func, args))
        else:
            bib_transforms.append(getattr(transforms, name))
    return compose(*bib_transforms)


# NOTE: An alternative library is :mod:`biblib`, but that's not been updated
#       for a while.
# TODO: references are parsed from the md file and converted to bibtex etc. format,
#       but bibs from the bibliography files are also combined and if a ref exists
#       in one of the files and also in references, the it's not known which of those
#       should be kept.
#       Also at present duplicates are simply written to the bibtex/biblatex file
def generate_bibtex(in_file: Path, metadata: Dict, style: str,
                    text: str, pandoc_path: Path, transform_names: List[str]) -> Path:
    """Generate bibtex for markdown file.

    Args:
        in_file: input file
        references: Metadata for the file including bibliography files and
                    references in the metadata

    The bibtex file is generated in the same directory as `in_file` with a
    ".bib" suffix.

    We use :mod:`re` for spliting the bibtex file.  Searching with :mod:`re` is
    faster than parsing all the bib entries with :mod:`bibtexparser`.

    Conflicts:

    """
    out_file = in_file.parent.joinpath(in_file.stem + ".bib")
    bib_files = metadata.get("bibliography", [])
    if isinstance(bib_files, str):
        bib_files = [bib_files]
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
    transform = compose_transforms(transform_names) if transform_names else identity
    try:
        bibtex = parser.parse("\n".join(bibs))  # noqa
        p = Popen(f"{pandoc_path} -r markdown -s -t {style} {in_file}",
                  shell=True, stdout=PIPE, stderr=PIPE)
        yaml_refs, err = p.communicate()
        parser.parse(yaml_refs)
        bibs = transform_bibtex(bibtex.entries, transform)  # type: ignore
    except Exception:
        msg = "Error while parsing bibtexs. Check sources."
        raise ValueError(msg)
    with open(out_file, "w") as f:
        f.write("".join(bibs))
    metadata["bibliography"] = [str(out_file.absolute())]
    return out_file


default_transforms = ["abbreviate_venue", "change_to_title_case", "normalize"]


# TODO: `t` should be a hook from which the functions can be appended or
#       removed.
# TODO: Not only should they be removable, but it should be configurable
#       via a config file
def transform_bibtex(entries: List[Dict[str, str]], transform: Callable) -> List[str]:
    """Transform bibtex entries according to given functions.

    Args:
        entries: Bibtex entries as a dictionary

    The functions are applied in order.

    """
    # Can either use abbreviate after full names or contractions
    # t = compose(transforms.abbreviate_venue,
    #             transforms.change_to_title_case,
    #             transforms.standardize_venue,
    #             transforms.normalize,
    #             transforms.remove_url,
    #             # transforms.date_to_year_month,
    #             partial(transforms.remove_keys, keys=["file"]))  # HACK: leave doi for now
    # t = compose(transforms.change_to_title_case,
    #             transforms.contract_venue,
    #             transforms.normalize)
    writer = bwriter.BibTexWriter(write_common_strings=True)
    retval: Dict[str, str] = {}
    for ent in entries:
        # TODO: Filter duplicates somewhere here maybe
        ID = ent["ID"]
        # if ID in retval:
        #     existing = retval[ID]
        #     check_which_one_to_keep
        retval[ID] = writer._entry_to_bibtex(transform(ent.copy()))
    return [*retval.values()]
