from typing import Union, List
from urllib.parse import urlparse, urlunparse, urljoin
from dataclasses import dataclass

from fuzzywuzzy import fuzz


# Typing
_URL = str
_CssSelector = str


@dataclass
class FuzzyExtract:
    extract: str
    score: int


def make_absolute(link: str, base_url: str) -> _URL:
    """Makes a given link absolute."""

    # Parse the link with stdlib.
    parsed = urlparse(link)._asdict()

    # If link is relative, then join it with base_url.
    if not parsed["netloc"]:
        return urljoin(base_url, link)

    # Link is absolute; if it lacks a scheme, add one from base_url.
    if not parsed["scheme"]:
        parsed["scheme"] = urlparse(base_url).scheme

        # Reconstruct the URL to incorporate the new scheme.
        parsed = (v for v in parsed.values())
        return urlunparse(parsed)

    # Link is absolute and complete with scheme; nothing to be done here.
    return link


def fuzzy_search(
    to_match: Union[List[str], str], search_list: List[str]
) -> FuzzyExtract:
    if isinstance(to_match, str):
        to_match = [to_match]
    highest_match: int = 0
    extract: str = ""
    for i in search_list:
        for string in to_match:
            score = fuzz.ratio(string, i)
            if score > highest_match:
                highest_match = score
                extract = i
    return FuzzyExtract(extract, highest_match)


# List of tags that are mostly used for inline html elements
inline_elements = [
    "a",
    "abbr",
    "acronym",
    "b",
    "bdo",
    "big",
    "br",
    "button",
    "cite",
    "code",
    "del",
    "dfn",
    "em",
    "i",
    "img",
    "ins",
    "input",
    "kdb",
    "label",
    "map",
    "mark",
    "object",
    "output",
    "q",
    "samp",
    "script",
    "select",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "textarea",
    "time",
    "tt",
    "var",
]


# List of list element tags
list_elements = [
    "li",
    "dl",
    "dt",
    "dd",
]

# List of table elements (not main table tag)
table_elements = [
    "tr",
    "th",
    "td",
]


ilt_elements = inline_elements + list_elements + table_elements
