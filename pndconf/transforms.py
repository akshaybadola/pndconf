from typing import Dict, List, Optional
import re


# TODO: The variables here should be synced from the network Eventually, the
#       pndconf should run as a service and accept markdown files so that the
#       editor doesn't have to wait.

# TODO: In some venues, "eleventh" and "twelfth" etc. are also written denoting
#       the iteration of the conference. Perhaps use DOI to fetch that or some other method.
venue_names = {"neurips": "Advances in Neural Information Processing Systems",
               "iccv": "Proceedings of the IEEE International Conference on Computer Vision",
               "cvpr": "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition",
               "wavc": "Proceedings of the IEEE Winter Conference on Applications of Computer Vision",
               "eccv": "Proceedings of the European Conference on Computer Vision",
               "iclr": "Proceedings of the International Conference on Learning Representations",
               "bmvc": "Proceedings of the British Machine Vision Conference",
               "aistats": "Proceedings of the International Conference on Artificial Intelligence and Statistics",
               "uai": "Proceedings of the Conference on Uncertainty in Artificial Intelligence",
               "ijcv": "International Journal of Computer Vision",
               "ijcai": "Proceedings of the International Joint Conference on Artificial Intelligence",
               "aaai": "Proceedings of the AAAI Conference on Artificial Intelligence",
               "icml": "Proceedings of the International Conference on Machine Learning",
               "pami": "IEEE Transactions on Pattern Analysis and Machine Intelligence"}
entry_types = {"neurips": "inproceedings",
               "iccv": "inproceedings",
               "cvpr": "inproceedings",
               "wavc": "inproceedings",
               "eccv": "inproceedings",
               "iclr": "inproceedings",
               "bmvc": "inproceedings",
               "aistats": "inproceedings",
               "uai": "inproceedings",
               "ijcv": "article",
               "ijcai": "inproceedings",
               "aaai": "inproceedings",
               "icml": "inproceedings",
               "pami": "article"}
venue_contractions = {"neurips": "NeurIPS",
                      "iccv": "ICCV",
                      "cvpr": "CVPR",
                      "wavc": "WAVC",
                      "eccv": "ECCV",
                      "iclr": "ICLR",
                      "bmvc": "BMVC",
                      "aistats": "AISTATS",
                      "uai": "UAI",
                      "ijcv": "IJCV",
                      "ijcai": "IJCAI",
                      "aaai": "AAAI",
                      "icml": "ICML",
                      "pami": "TPAMI"}
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
    return dict((re.sub("-$", ".+", x[0].lower()), x[1].lower())
                for x in lines if "eng" in x[-1] or x[-1] == "mul")


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


def rule_neurips(x):
    if "nips" in x.lower() or "neurips" in x.lower() or\
       "neural information processing" in x.lower():
        return venue_names["neurips"]


def rule_iccv(x):
    if ("computer vision" in x.lower() and "international conference" in x.lower() and
            "pattern" not in x.lower()) or "iccv" in x.lower():
        return venue_names["iccv"]


def rule_cvpr(x):
    if "computer vision and pattern recognition" in x.lower() or "cvpr" in x.lower():
        return venue_names["cvpr"]


def rule_wavc(x):
    if "winter conference" in x.lower() and "computer vision" in x.lower() or\
       "wavc" in x.lower():
        return venue_names["wavc"]


def rule_eccv(x):
    if "european conference" in x.lower() and "computer vision" in x.lower() or\
       "eccv" in x.lower():
        return venue_names["eccv"]


def rule_iclr(x):
    if "learning representations" in x.lower() or "iclr" in x.lower():
        return venue_names["iclr"]


def rule_bmvc(x):
    if "british" in x.lower() and "machine vision" in x.lower() or "bmvc" in x.lower():
        return venue_names["bmvc"]


def rule_aistats(x):
    if "artificial intelligence and statistics" in x.lower() or\
       "aistats" in x.lower():
        return venue_names["aistats"]


def rule_uai(x):
    if "uncertainty in artificial intelligence" in x.lower() or\
       "UAI" in x:
        return venue_names["uai"]


def rule_ijcv(x):
    if "international journal of computer vision" in x.lower() or\
       "ijcv" in x.lower():
        return venue_names["ijcv"]


def rule_ijcai(x):
    if "ijcai" in x.lower() or\
       "joint conference on artificial intelligence" in x.lower():
        return venue_names["ijcai"]


def rule_aaai(x):
    if "aaai" in x.lower():
        return venue_names["aaai"]


def rule_icml(x):
    if "icml" in x.lower() or\
       {*filter(lambda y: y not in stop_words_set, x.lower().split())} ==\
       {"international", "conference", "machine", "learning"}:
        return venue_names["icml"]


def rule_pami(x):
    if ("ieee" in x.lower() and "transactions" in x.lower() and
            "pattern analysis" in x.lower() and "machine intelligence" in x.lower())\
            or "PAMI" in x or "TPAMI" in x:
        return venue_names["pami"]


def normalize(ent: Dict[str, str]):
    """Replaces newlines in entries with a space. (for now)"""
    for k, v in ent.items():
        ent[k] = v.replace("\n", " ")
    return ent


def fix_cvf(x):
    if "ieee/cvf" in x.lower():
        return x.replace("ieee/cvf", "IEEE").replace("IEEE/CVF", "IEEE")


# TODO: Can add certain other rules like Transactions is always a journal etc.
rules = {"neurips": rule_neurips,
         "iccv": rule_iccv,
         "cvpr": rule_cvpr,
         "wavc": rule_wavc,
         "eccv": rule_eccv,
         "iclr": rule_iclr,
         "bmvc": rule_bmvc,
         "aistats": rule_aistats,
         "uai": rule_uai,
         "ijcv": rule_ijcv,
         "ijcai": rule_ijcai,
         "aaai": rule_aaai,
         "icml": rule_icml,
         "pami": rule_pami}
# NOTE: This assertion should hold after each edition of the venues
assert set(rules.keys()) == set(venue_names.keys()) ==\
    set(entry_types.keys()) == set(venue_contractions.keys())


def fix_venue(ent, contract=False):
    """Fix venue if it's a known venue.

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
    venue = ent.get("booktitle", None) or ent.get("journal", None)
    if venue:
        venue = venue.replace("{", "").replace("}", "")
        for k, v in rules.items():
            if v(venue):
                vname = venue_contractions[k] if contract else venue_names[k]
                if entry_types[k] == "inproceedings":
                    if ent["ENTRYTYPE"] == "article":
                        ent["ENTRYTYPE"] = "inproceedings"
                        ent.pop("journal")
                    ent["booktitle"] = vname
                elif entry_types[k] == "article":
                    if ent["ENTRYTYPE"] == "inproceedings":
                        ent["ENTRYTYPE"] = "article"
                        ent.pop("booktitle")
                    ent["journal"] = vname
                else:
                    raise AttributeError(f"Unknown venue type of {ent['ENTRYTYPE']}")
                break
    return ent


def standardize_venue(ent):
    """Change the venue name to a standard name.

    See :func:`fix_venue`.

    """
    return fix_venue(ent)


def contract_venue(ent):
    """Change the venue name to a contraction.

    See :func:`fix_venue`.

    """
    return fix_venue(ent, True)


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
                if x.startswith("{") or x.upper() == x:
                    temp.append(x)
                elif i == 0 or capitalize_next:
                    temp.append(x.capitalize())
                elif not (x in stop_words_set):
                    temp.append(x.capitalize())
                else:
                    temp.append(x)
                if x.endswith(".") or x.endswith(":"):
                    capitalize_next = True
                else:
                    capitalize_next = False
            ent[key] = " ".join([x if x.startswith("{") else "{" + x + "}" for x in temp])
    return ent


def abbreviate_venue(ent):
    if ent["ENTRYTYPE"] == "inproceedings":
        vkey = "booktitle"
    elif ent["ENTRYTYPE"] == "article":
        vkey = "journal"
    else:
        return ent
    try:
        words = ent[vkey].split()
    except Exception:
        import ipdb; ipdb.set_trace()
    for i, w in enumerate(words):
        term = re.sub(r"{(.+)}", r"\1", w)
        found = term in abbrevs and abbrevs[term] != "n.a." and abbrevs[term]
        if found:
            words[i] = "{" + found + "}"
    ent[vkey] = " ".join(words)
    return ent


def check_author_names(ent):
    check_for_unicode = None
