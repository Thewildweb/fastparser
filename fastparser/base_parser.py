import re
from typing import List, Union, Optional, Dict
from urllib.parse import urlparse

from selectolax.parser import HTMLParser
from selectolax.parser import Node

from .utilities import _URL, _CssSelector, make_absolute, fuzzy_search
from .utilities import ilt_elements


class Ahref:
    """Basic class for extracted Ahrefs

    :param href_node: selectolax node object
    :base_url: the url of the webpage
    """

    def __init__(self, href_node: Node, base_url: _URL) -> None:
        self.href: str = href_node.attributes.get("href")
        if self.href and self.href.startswith(("#", "mailto:", "javascript:", "tel:")):
            raise ValueError("Not a normal url")

        self.base_url: str = base_url
        self.absolute_url: str = make_absolute(self.href, self.base_url)
        self.text: str = href_node.text()
        self.parsed = urlparse(self.absolute_url)
        self.is_internal: bool = self.parsed.netloc == urlparse(self.base_url).netloc
        self.attributes: Dict[str, str] = href_node.attributes

    def __repr__(self) -> str:
        return f"Ahref: {self.absolute_url}"

    def __str__(self) -> str:
        return self.absolute_url

    @property
    def path_split(self) -> List[str]:
        parsed = urlparse(self.absolute_url)

        return [item.lower() for item in parsed.path.split("/") if len(item) > 0]


class BasePage:
    """The Basic HTML parser

    :param html: String representation of the HTML document
    :param url: URL of the page rendered

    """

    next_symbol = ["volgende", "next", "meer", "more", "ouder", "older"]
    prev_symbol = ["vorige", "previous", "nieuwe", "new"]

    def __init__(self, html: str, url: _URL):
        self.url: str = url
        self.parsed_url = urlparse(self.url)
        self.scheme_domain: str = (
            f"{self.parsed_url.scheme}://{self.parsed_url.hostname}/"
        )
        self._html_input: str = html
        self._tree = HTMLParser(self._html_input)
        self.links: List[Ahref] = self._get_links()

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.url == other.url

    def __repr__(self) -> str:
        return f"<Webpage: {self.url}>"

    def css(self, selector: _CssSelector) -> List[Node]:
        return self._tree.css(selector)

    def css_first(self, selector: _CssSelector) -> Node:
        return self._tree.css_first(selector)

    def find_in_text(
        self,
        selector: _CssSelector,
        to_search: Union[List[str], str],
    ) -> List[Node]:
        """Find string in text of the Nodes."""
        # If str, make a list
        if isinstance(to_search, str):
            to_search = [to_search]

        nodes = self.css(selector)
        return [
            node
            for node in nodes
            if any(substring in node.text(deep=False) for substring in to_search)
        ]

    def find_in_text_regex(self, selector: _CssSelector, reg_str: str) -> List[Node]:
        """Find regex in text and returns the Nodes."""
        nodes = self.css(selector)
        return [node for node in nodes if re.search(reg_str, node.text(deep=False))]

    def find_in_ahref(
        self,
        to_search: Union[List[str], str],
        in_path: bool = True,
        in_text: bool = True,
        fuzzy_score: Optional[int] = None,
        internal: bool = True,
        external: bool = True,
    ) -> List[Node]:
        """Find text in the link_list. Href starting with #:, javascript:,
        mailto:, tel: are left out.

        If fuzzy int provided, returned list is ordered by fuzzy score.

        When searchin in paths, don't use '/' backslashes, just the text
        :param to_search: the string(s) to be found
        :param in_path: searches in the path of href
        "param in_text: searches in the text
        "param fuzzy: integer between 0 and 100 used for minimum fuzzy search
        "param internal: only search in internal links
        """
        if isinstance(to_search, str):
            to_search = [to_search]

        # Select list of Ahrefs from which to pick
        link_list = []
        if internal:
            link_list.extend(self.internal_links)
        if external:
            link_list.extend(self.external_links)

        # Function that creates the list to be searched
        def path_text(link: Ahref) -> List[str]:
            return_list = []
            if in_path:
                return_list.extend(link.path_split)
            if in_text:
                return_list.append(link.text)
            return [path_text.lower() for path_text in return_list]

        if fuzzy_score:
            return_list = []
            for link in link_list:
                fuzz_extract = fuzzy_search(to_search, path_text(link))
                if fuzz_extract.score >= fuzzy_score:
                    return_list.append(link)
            return return_list

        return [
            link
            for link in link_list
            if any(string.lower() in path_text(link) for string in to_search)
        ]

    @classmethod
    def get_parent(cls, node: Node, depth: int = 1) -> Node:
        parent_node = node.parent
        depth -= 1
        if not parent_node:
            return node

        if depth == 0:
            return node.parent
        else:
            return cls.get_parent(parent_node, depth)

        parent = cls.get_parent(node, depth=depth)
        return parent

    @classmethod
    def get_children(cls, node: Node):
        return [i for i in node.iter()]

    @classmethod
    def get_siblings(cls, node: Node):
        pass

    @classmethod
    def get_first_block(cls, node: Node) -> Optional[Node]:
        """returns the first ancestor that is block level,
        if node is block level, it is returned. If Node has
        no parent, None is returned
        """
        if node.tag not in ilt_elements:
            return node

        return cls.get_first_block(node.parent)

    @property
    def internal_links(self) -> List[Ahref]:
        return [link for link in self.links if link.is_internal]

    @property
    def external_links(self) -> List[Ahref]:
        return [link for link in self.links if not link.is_internal]

    @property
    def text(self) -> str:
        new_tree = HTMLParser(self._html_input)
        tags = ["head", "script", "noscript", "style", "iframe", "noembed", "noframes"]
        new_tree.strip_tags(tags)
        return new_tree.text(separator=" ").strip()

    @property
    def next_page_url(self) -> _URL:
        if (next_node := self.css_first("link[rel='next'][href]")) :
            return next_node.attributes["href"]

        # find links with any next_symbol in path or text and check in "nav"
        # or "next" in class or id
        # TODO: check parent class and id
        candidates = self.find_in_ahref(self.next_symbol, external=False)
        for candidate in candidates:
            candidate_id_class = candidate.attributes.get(
                "class", ""
            ) + candidate.attributes.get("id", "")
            if any(i in candidate_id_class for i in ["nav", "next"]):
                return candidate.absolute_url

    @property
    def previous_page_url(self) -> _URL:
        if (prev_node := self.css_first("link[rel='prev'][href]")) :
            return prev_node.attributes["href"]

        # find links with any prev_symbol in path or text and check if "nav"
        # or "next" in class or id
        # TODO: check parent class and id
        candidates = self.find_in_ahref(self.prev_symbol, external=False)
        for candidate in candidates:
            candidate_id_class_text = (
                candidate.attributes.get("class", "")
                + " "
                + candidate.attributes.get("id", "")
                + " "
                + candidate.text
            )
            if any(["nav", "next"] in candidate_id_class):
                return candidate.absolute_url

    def _get_links(self) -> List[Ahref]:
        return_list = []
        ahrefs = self._tree.css("a[href]")

        for a_node in ahrefs:
            if a_node.attributes["href"] and not a_node.attributes["href"].startswith(
                ("#", "javascript:", "mailto:", "tel:")
            ):
                return_list.append(Ahref(a_node, self.url))

        return return_list
