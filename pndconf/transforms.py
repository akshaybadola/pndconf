from typing import Dict, List
import re


def rule_neurips(x):
    if "nips" in x.lower() or "neurips" in x.lower() or\
       "neural information processing" in x.lower():
        return "neurips"


def rule_iccv(x):
    if ("computer vision" in x.lower() and "international conference" in x.lower() and
            "pattern" not in x.lower()) or "iccv" in x.lower():
        return "iccv"


def rule_cvpr(x):
    if "computer vision and pattern recognition" in x.lower() or "cvpr" in x.lower():
        return "cvpr"


def rule_wavc(x):
    if "winter conference" in x.lower() and "computer vision" in x.lower() or\
       "wavc" in x.lower():
        return "wavc"


def rule_eccv(x):
    if "european conference" in x.lower() and "computer vision" in x.lower() or\
       "eccv" in x.lower():
        return "eccv"


def rule_iclr(x):
    if "learning representations" in x.lower() or "iclr" in x.lower():
        return "iclr"


def rule_bmvc(x):
    if "british" in x.lower() and "machine vision" in x.lower() or "bmvc" in x.lower():
        return "bmvc"


def rule_aistats(x):
    if "artificial intelligence and statistics" in x.lower() or\
       "aistats" in x.lower():
        return "aistats"


def rule_uai(x):
    if "uncertainty in artificial intelligence" in x.lower() or\
       "UAI" in x:
        return "uai"


def rule_ijcv(x):
    if "international journal of computer vision" in x.lower() or\
       "ijcv" in x.lower():
        return "ijcv"


def rule_ijcai(x):
    if "ijcai" in x.lower() or\
       "joint conference on artificial intelligence" in x.lower():
        return "ijcai"


def rule_aaai(x):
    if "aaai" in x.lower():
        return "aaai"


def rule_icml(x):
    if "icml" in x.lower() or\
       {*filter(lambda y: y not in stop_words_set, x.lower().split())} ==\
       {"international", "conference", "machine", "learning"}:
        return "icml"


def rule_pami(x):
    if ("ieee" in x.lower() and "transactions" in x.lower() and
            "pattern analysis" in x.lower() and "machine intelligence" in x.lower())\
            or "PAMI" in x or "TPAMI" in x:
        return "pami"


def rule_jair(x):
    if "jair" in x.lower() or\
       re.match(r"journal +of +artificial +intelligence +research", x, flags=re.IGNORECASE):
        return True


def rule_jmlr(x):
    if "jmlr" in x.lower() or\
       re.match(r"journal +of +machine +learning +research", x, flags=re.IGNORECASE):
        return True


# TODO: WHAT ABOUT ABBREVIATIONS?
#       Currently there's no rule to classify "Int. Jour. Comp. Vis." etc.

# TODO: We can add certain other rules like Transactions is always a journal etc.

# TODO: The variables here should be synced from the network Eventually, the
#       pndconf should run as a service and accept markdown files so that the
#       editor doesn't have to wait.

# TODO: In some venues, "eleventh" and "twelfth" etc. are also written denoting
#       the iteration of the conference. Perhaps use DOI to fetch that or some other method.
venues = {'neurips': {'name': 'Advances in Neural Information Processing Systems',
                      'type': 'inproceedings',
                      'contraction': 'NeurIPS',
                      'rule': rule_neurips},
          'iccv': {'name': 'Proceedings of the IEEE International Conference on Computer Vision',
                   'type': 'inproceedings',
                   'contraction': 'ICCV',
                   'rule': rule_iccv},
          'cvpr': {'name': 'Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition',
                   'type': 'inproceedings',
                   'contraction': 'CVPR',
                   'rule': rule_cvpr},
          'wavc': {'name': 'Proceedings of the IEEE Winter Conference on Applications of Computer Vision',
                   'type': 'inproceedings',
                   'contraction': 'WAVC',
                   'rule': rule_wavc},
          'eccv': {'name': 'Proceedings of the European Conference on Computer Vision',
                   'type': 'inproceedings',
                   'contraction': 'ECCV',
                   'rule': rule_eccv},
          'iclr': {'name': 'Proceedings of the International Conference on Learning Representations',
                   'type': 'inproceedings',
                   'contraction': 'ICLR',
                   'rule': rule_iclr},
          'bmvc': {'name': 'Proceedings of the British Machine Vision Conference',
                   'type': 'inproceedings',
                   'contraction': 'BMVC',
                   'rule': rule_bmvc},
          'aistats': {'name': 'Proceedings of the International Conference on Artificial Intelligence and Statistics',
                      'type': 'inproceedings',
                      'contraction': 'AISTATS',
                      'rule': rule_aistats},
          'uai': {'name': 'Proceedings of the Conference on Uncertainty in Artificial Intelligence',
                  'type': 'inproceedings',
                  'contraction': 'UAI',
                  'rule': rule_uai},
          'ijcv': {'name': 'International Journal of Computer Vision',
                   'type': 'article',
                   'contraction': 'IJCV',
                   'rule': rule_ijcv},
          'ijcai': {'name': 'Proceedings of the International Joint Conference on Artificial Intelligence',
                    'type': 'inproceedings',
                    'contraction': 'IJCAI',
                    'rule': rule_ijcai},
          'aaai': {'name': 'Proceedings of the AAAI Conference on Artificial Intelligence',
                   'type': 'inproceedings',
                   'contraction': 'AAAI',
                   'rule': rule_aaai},
          'icml': {'name': 'Proceedings of the International Conference on Machine Learning',
                   'type': 'inproceedings',
                   'contraction': 'ICML',
                   'rule': rule_icml},
          'pami': {'name': 'IEEE Transactions on Pattern Analysis and Machine Intelligence',
                   'type': 'article',
                   'contraction': 'TPAMI',
                   'rule': rule_pami},
          'jair': {'name': 'Journal of Artificial Intelligence Research',
                   'type': 'article',
                   'contraction': 'JAIR',
                   'rule': rule_jair},
          'jmlr': {'name': 'Journal of Machine Learning Research',
                   'type': 'article',
                   'contraction': 'JMLR',
                   'rule': rule_jmlr}}
stop_words_set = {"a", "an", "and", "are", "as", "at", "by", "can", "did",
                  "do", "does", "for", "from", "had", "has", "have", "having", "here", "how",
                  "in", "into", "is", "it", "it's", "its", "not", "of", "on", "over", "should",
                  "so", "than", "that", "the", "then", "there", "these", "to", "via", "was", "were",
                  "what", "when", "where", "which", "who", "why", "will", "with"}
abbrevs = {'Advances': 'Adv.',
           'in': None,
           'Neural': 'n.a.',
           'Information': 'Inf.',
           'Processing': 'Process.',
           'Systems': 'Syst.',
           'Proceedings': 'Proc.',
           'of': None,
           'the': None,
           'IEEE': None,
           'International': 'n.a.',
           'Conference': 'Conf.',
           'on': None,
           'Computer': 'Comput.',
           'Vision': 'Vis.',
           'and': None,
           'Pattern': 'n.a.',
           'Recognition': 'Recognit.',
           'Winter': 'n.a.',
           'Applications': 'Appl.',
           'European': 'Eur.',
           'Learning': 'Learn.',
           'Representations': 'Represent.',
           'British': 'Br.',
           'Machine': 'Mach.',
           'Artificial': 'Artif.',
           'Intelligence': 'Intell.',
           'Statistics': 'Stat.',
           'Uncertainty': 'Uncertain.',
           'Journal': 'J.',
           'Joint': 'Jt.',
           'AAAI': None,
           'Transactions': 'Trans.',
           'Analysis': 'Anal.',
           'advances': 'adv.',
           'analysis': 'anal.',
           'applications': 'appl.',
           'artificial': 'artif.',
           'british': 'br.',
           'computer': 'comput.',
           'conference': 'conf.',
           'european': 'eur.',
           'information': 'inf.',
           'intelligence': 'intell.',
           'international': 'n.a.',
           'joint': 'jt.',
           'journal': 'j.',
           'learning': 'learn.',
           'machine': 'mach.',
           'neural': 'n.a.',
           'pattern': 'n.a.',
           'proceedings': 'proc.',
           'processing': 'process.',
           'recognition': 'recognit.',
           'representations': 'represent.',
           'statistics': 'stat.',
           'systems': 'syst.',
           'transactions': 'trans.',
           'uncertainty': 'uncertain.',
           'vision': 'vis.',
           'winter': 'n.a.'}


def load_abbrevs(abbrevs_file):
    import csv
    lines = []
    with open(abbrevs_file) as f:
        reader = csv.reader(f, delimiter=";")
        for line in reader:
            lines.append(line)
    return {re.sub("-$", ".+", x[0].lower()): x[1].lower()
            for x in lines if "eng" in x[-1] or x[-1] == "mul"}


def get_abbrev(abbrev_regexps, word):
    for k, v in abbrev_regexps.items():
        if re.match(k, word, flags=re.IGNORECASE):
            return v


def update_abbrevs(words, abbrevs, abbrev_regexps):
    for w in set(words):
        match = re.match(r"[A-Z]+$", w)  # check all upcase
        if not match and w not in abbrevs or abbrevs[w] is None:
            abbrev = get_abbrev(abbrev_regexps, w)
            if abbrev:
                abbrevs[w.lower()] = abbrev.lower()
                abbrevs[w.capitalize()] = abbrev.capitalize()


def fix_cvf(x: str):
    if "ieee/cvf" in x.lower():
        return x.replace("ieee/cvf", "IEEE").replace("IEEE/CVF", "IEEE")


def normalize(ent: Dict[str, str]):
    """Replaces newlines in entries with a space. (for now)"""
    for k, v in ent.items():
        ent[k] = v.replace("\n", " ")
    return ent


def fix_venue(ent: Dict[str, str], contract: bool = False):
    """Fix venue if it's a known venue.

    Args:
        ent: Bibtex Entry as a dictionary. It's modified in place.
        contract: Flag to signal contraction of venue.

    Fix name of conference or journal to standard nomenclature for that venue
    and also change the venue type to correct one of \"inproceedings\" or
    "journal".

    E.g., CVPR is often listed as "CVPR", "Computer Vision and Pattern Recognition",
    "IEEE Internation Conference on Computer Vision and Pattern Recognition",
    "IEEE/CVF Internation Conference on Computer Vision and Pattern Recognition" etc.

    Instead, if the abbreviation or the some version of the venue is found, then
    replace with the canonical version.

    If :code:`contract` is given, then Change the venue name to a contraction
    instead.

    """
    venue = ent.get("booktitle", None) or ent.get("journal", None) or ent.get("venue", None)
    if venue:
        venue = venue.replace("{", "").replace("}", "")
        for k, v in venues.items():
            rule = v["rule"]
            vtype = v["type"]
            if rule(venue):
                vname = v["contraction"] if contract else v["name"]
                if vtype == "inproceedings":
                    if ent["ENTRYTYPE"] == "article":
                        ent["ENTRYTYPE"] = "inproceedings"
                        ent.pop("journal")
                    ent["booktitle"] = vname
                elif vtype == "article":
                    if ent["ENTRYTYPE"] == "inproceedings":
                        ent["ENTRYTYPE"] = "article"
                        ent.pop("booktitle")
                    ent["journal"] = vname
                else:
                    raise AttributeError(f"Unknown venue type of {ent['ENTRYTYPE']}")
                break
    return ent


def standardize_venue(ent: Dict[str, str]):
    """Change the venue name to a standard name.

    See :func:`fix_venue`.

    """
    return fix_venue(ent)


def contract_venue(ent: Dict[str, str]):
    """Change the venue name to a contraction.

    See :func:`fix_venue`.

    """
    return fix_venue(ent, contract=True)


def change_to_title_case(ent: Dict[str, str]) -> Dict[str, str]:
    """Change some values in a bibtex entry to title case.

    Title, Booktitle, and Journal are changed.

    Args:
        ent: Bibtex entry as a dictionary

    """
    for key in ["title", "booktitle", "journal"]:
        if key in ent:
            val = ent[key]
            temp: List[str] = []
            capitalize_next = False
            for i, x in enumerate(filter(lambda x: x and not re.match(r"^ +$", x),
                                         re.split(r"( +|-)", val))):
                cap = (not i) or capitalize_next or x not in stop_words_set
                y = x.capitalize() if cap else x
                temp.append(y)
                capitalize_next = bool(x.endswith((".", ":")))
            ent[key] = " ".join([x if x.startswith("{") else "{" + x + "}" for x in temp])
    return ent


def abbreviate_venue(ent: Dict[str, str]) -> Dict[str, str]:
    if ent["ENTRYTYPE"] == "inproceedings":
        vkey = "booktitle"
    elif ent["ENTRYTYPE"] == "article":
        vkey = "journal"
    else:
        return ent
    try:
        words = ent[vkey].split()
    except Exception:
        raise AttributeError(f"{vkey} not in entry")
    for i, w in enumerate(words):
        term = re.sub(r"{(.+)}", r"\1", w)
        found = term in abbrevs and abbrevs[term] != "n.a." and abbrevs[term]
        if found:
            words[i] = "{" + found + "}"
    ent[vkey] = " ".join(words)
    return ent


def date_to_year_month(ent: Dict[str, str]) -> Dict[str, str]:
    months = dict(zip(range(1, 13), [x[:3] for x in ["January", "February",
                                                     "March", "April", "May", "June", "July", "August",
                                                     "September", "October", "November", "December"]]))
    if "date" in ent:
        date = ent.pop("date").split("-")
        if len(date) == 1:
            ent["year"] = date[0]
        else:
            year, month = date[0], date[1]
            ent["year"] = year
            ent["month"] = months[int(month)]
    return ent


def remove_keys(ent: Dict[str, str], keys: List[str]) -> Dict[str, str]:
    for key in keys:
        if key in ent:
            ent.pop(key)
    return ent


def remove_url(ent: Dict[str, str]) -> Dict[str, str]:
    if "url" in ent:
        url = ent.pop("url")
        if ent["ENTRYTYPE"] == "misc" and "howpublished" not in ent:
            ent["howpublished"] = f'\\url{{{url}}}'
    return ent


def check_author_names(ent: Dict[str, str]):
    check_for_unicode = None
