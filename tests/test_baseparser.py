import re
import os

import pytest
import pytest_check as check
from selectolax.parser import HTMLParser

from fastparser.utilities import make_absolute
from fastparser.base_parser import Ahref
from fastparser.base_parser import BasePage

TEST_HTML_1 = """<html>
    <head>
        <title>Een test pagina</title>
    </head>
    <body>
        <script>Een script tag</script>
        <style>Een style tag</style>
        <p class="select">Een test tag</p>
    </body>
    </html>"""

SCRIPT_PATH = os.path.realpath(__file__)
DIRR = os.path.dirname(SCRIPT_PATH)
HTML_FILE = "python.html"
with open(os.path.join(DIRR, HTML_FILE), "r") as html_file:
    TEST_HTML_PAGE = html_file.read()
TEST_HTML_URL = "https://www.python.org/"


def test_make_absolute():
    url = "/testers"
    base_url = "https://www.getevents.nl/asd/"
    absolute = make_absolute(url, base_url)
    assert absolute == "https://www.getevents.nl/testers"


def test_make_absolute_external():
    url = "//www.google.com/tester"
    base_url = "https://www.getevents.nl/tester"
    absolute = make_absolute(url, base_url)
    assert absolute == "https://www.google.com/tester"


def test_ahref_split():
    tree = HTMLParser(
        '<html><a href="https://www.google.com/tester/nog1/enq/">Google tester</a></html>'
    )
    href_node = tree.css_first("a")
    base = "https://www.google.com/"

    ahref = Ahref(href_node, base)
    check.equal(len(ahref.path_split), 3)
    check.equal(ahref.parsed.netloc, "www.google.com")
    check.equal(str(ahref), "https://www.google.com/tester/nog1/enq/")
    check.equal(ahref.parsed.scheme, "https")
    check.is_true(ahref.is_internal)


def test_relative_url():
    tree = HTMLParser('<html><a href="/test/relative">Testing</a></html>')
    href_node = tree.css_first("a")
    base = "https://www.google.com/tester1"

    ahref = Ahref(href_node, base)
    assert ahref.absolute_url == "https://www.google.com/test/relative"


def test_external_url():
    tree = HTMLParser(
        '<html><a href="https://www.getevents.nl/tester">Getevents</a></html>'
    )
    href_node = tree.css_first("a")
    base = "https://www.google.com/getevents"

    ahref = Ahref(href_node, base)
    assert not ahref.is_internal


def test_base_url():
    url = (
        "https://www.google.com/search?source=hp&ei=gF1nX5HVE5GxkwWNkaWgAw&q=url+tester"
        "&oq=url+tester&gs_lcp=CgZwc3ktYWIQAzICCAAyAggAMgIIADIGCAAQFhAeMgYIABAWEB4yBggAE"
        "BYQHjIGCAAQFhAeMgYIABAWEB4yBggAEBYQHjIGCAAQFhAeOgsILhCxAxCDARCTAjoICAAQsQMQgwE6B"
        "QgAELEDOgUILhCxAzoICC4QsQMQgwE6AgguUJwKWMMVYL8WaAFwAHgAgAGAAYgBswaSAQM2LjOYAQCg"
        "AQGqAQdnd3Mtd2l6sAEA&sclient=psy-ab&ved=0ahUKEwiRld3T7_frAhWR2KQKHY1ICTQQ4dUDCA"
        "c&uact=5"
    )
    html_string = "<p>Een stukje html</p>"

    page = BasePage(html_string, url)
    assert page.scheme_domain == "https://www.google.com/"


def test_text():
    url = "https://www.google.com/"
    html_string = """<html>
    <head>
        <title>Een test pagina</title>
        <!--
        - DEze
        - Multiline comment moet eruit
        -->
    </head>
    <body>
        <!-- Deze comment moet eruit -->
        <script>Een script tag</script>
        <style>Een style tag</style>
        <p>Deze content moet bewaard blijven
        </p>
    </body>
    </html>"""

    page = BasePage(html_string, url)
    assert page.text == "Deze content moet bewaard blijven"


def test_css():
    url = "https://www.getevents.nl"
    html_string = """<html>
    <head>
        <title>Een test pagina</title>
    </head>
    <body>
        <script>Een script tag</script>
        <style>Een style tag</style>
        <p class="select">Een stukje content</p>
    </body>
    </html>"""

    page = BasePage(html_string, url)
    nodes = page.css("p.select")
    assert nodes[0].text() == "Een stukje content"


def test_css_first():
    url = "https://www.getevents.nl"
    html_string = """<html>
    <head>
        <title>Een test pagina</title>
    </head>
    <body>
        <script>Een script tag</script>
        <style>Een style tag</style>
        <p class="select">Een stukje content</p>
    </body>
    </html>"""

    page = BasePage(html_string, url)
    node = page.css_first("p.select")
    assert node.text() == "Een stukje content"


def test_find_in_text():
    url = "https://www.google.com"
    html_string = """<html>
    <head>
        <title>Een test pagina</title>
    </head>
    <body>
        <script>Een script tag</script>
        <style>Een style tag</style>
        <p class="select">Een test tag</p>
    </body>
    </html>"""

    page = BasePage(html_string, url)
    nodes_p = page.find_in_text("p", "test")
    nodes_star = page.find_in_text("*", "test")
    check.equal(nodes_p[0].html, '<p class="select">Een test tag</p>')
    check.equal(len(nodes_star), 2)


# TODO add test_find_in_text_fuzzy


def test_find_in_text_regex():
    url = "https://www.google.com/"
    page = BasePage(TEST_HTML_1, url)
    reg = re.compile(r"t\wst")
    nodes = page.find_in_text_regex("p", reg)
    assert nodes[0].text() == "Een test tag"


def test_links():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    assert len(page.links) == 197


def test_internal_links():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    nr_absolute_links = len(page.internal_links)
    domain_in_links = len(
        [i for i in page.internal_links if TEST_HTML_URL in i.absolute_url]
    )
    check.equal(nr_absolute_links, domain_in_links)
    check.is_true(page.internal_links)


def test_external_links():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    check.is_not_in(TEST_HTML_PAGE, [i.absolute_url for i in page.external_links])
    check.is_true(page.external_links)


def test_find_in_ahref():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_string = "learn more"
    first_found = page.find_in_ahref(search_string)[0]
    assert first_found.href == "/doc/"


def test_find_in_ahref_internal():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_string = "Python 3.8.6 is now available"
    internal_links = page.find_in_ahref(search_string, external=False)
    all_links = page.find_in_ahref(search_string)
    check.is_true(all_links)
    check.equal(len(internal_links), 0)


def test_find_in_ahref_internal_searchlist():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_list = ["donate", "facebook"]
    links = page.find_in_ahref(search_list)
    print(links)
    assert len(links) == 2


def test_find_in_ahref_path():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_string = "doc"
    links = page.find_in_ahref(search_string, in_text=False, internal=True)
    assert links[0].text.lower() == "documentation"


def test_find_in_ahref_text():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_string = "documentation"
    links = page.find_in_ahref(search_string, in_path=False)
    assert links[0].href == "/doc/"


def test_find_in_ahref_fuzzy():
    page = BasePage(TEST_HTML_PAGE, TEST_HTML_URL)
    search_string = "donate"
    links = page.find_in_ahref(search_string, fuzzy_score=90)
    print(links)
    assert (
        str(links[0])
        == "https://psfmember.org/civicrm/contribute/transact?reset=1&id=2"
    )


def test_next_page_rel_next():
    html_string = """<html>
    <head>
        <title>Page 1</title>
        <link rel="next" href="https://www.getevents.nl/p2" />
    </head>
    <body>
        <p>Een p tag</p>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    assert page.next_page_url == "https://www.getevents.nl/p2"


def test_prev_page_rel_prev():
    html_string = """<html>
    <head>
        <title>Page 2</title>
        <link rel="prev" href="https://www.getevents.nl/"
    </head>
    <body>
        <p>Een p tag</p>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/p2"
    page = BasePage(html_string, mock_url)
    assert page.previous_page_url == "https://www.getevents.nl/"


def test_next_page_url():
    html_string = """<html>
    <head>
        <title>Page 1</title>
    </head>
    <body>
        <p>Een p tag</p>
        <a href="/p2" class="next">Next</a>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    assert page.next_page_url == "https://www.getevents.nl/p2"


def test_get_parent():
    html_string = """<html>
    <head>
        <title>Test page</title>
    </head>
    <body class="grand_parent">
        <article class="parent">
            <h1>Headline</h1>
            <p>Some text ...</p>
        </article>
        <sidebar>
            <div>
                Widget
            </div>
        </sidebar>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    p_node = page.css_first("p")
    parent = page.get_parent(p_node)
    grand_parent = page.get_parent(p_node, 2)
    check.equal(parent.attributes["class"], "parent")
    check.equal(grand_parent.attributes["class"], "grand_parent")


def test_get_children():
    html_string = """<html>
    <head>
        <title>Test page</title>
    </head>
    <body class="grand_parent">
        <article class="parent">
            <h1>Headline</h1>
            <p>Some text ...</p>
            <p>Antother tag</p>
            <button>Click me!</button>
        </article>
        <sidebar>
            <div>
                Widget
            </div>
        </sidebar>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    a_node = page.css_first("article")
    children = BasePage.get_children(a_node)
    assert len(children) == 4


def test_get_first_block():
    html_string = """<html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <article>
            <ul class="blockParent">
                <li>test1</li>
                <li id="selectMe">test2</li>
                <li>test3</li>
            </ul>
        </article>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    li_node = page.css_first("li#selectMe")
    block_parent = page.get_first_block(li_node)
    assert block_parent.attributes["class"] == "blockParent"


def test_get_first_block_with_inner_inline():
    html_string = """<html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <atricle>
            <ul class="BlockParent">
                <li>Test 1</li>
                <li>Test 2</li>
                <li>Test <strong id="SelectMe">Nog 1</strong></li>
            </ul>
        </article>
    </body>
    </html>"""
    mock_url = "https://www.getevents.nl/"
    page = BasePage(html_string, mock_url)
    strong_node = page.css_first("strong#SelectMe")
    block_parent = page.get_first_block(strong_node)
    assert block_parent.attributes["class"] == "BlockParent"

