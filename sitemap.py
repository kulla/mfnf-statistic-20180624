"""Functions for parsing sitemap.

Copyright 2017 Stephan Kulla
"""

import re

from functools import reduce

SITEMAP_NODE_TYPES = ["mfnf_sitemap", "book", "chapter", "article", "article"]

def query_path(obj, path):
    return reduce(lambda x, y: y(x) if callable(y) else x[y], path, obj)

def lookup(obj, *path):
    """Lookups repeatedly the items in the list `path` of the object `obj`. In
    case any `IndexError` or `KeyError` is thrown, `None` is returned. For
    example the call `safe_lookup(obj, "a", 0, "b")` returns
    `obj["a"][0]["b"]` when it exists and `None` otherwise."""
    try:
        return query_path(obj, path)
    except (IndexError, KeyError, TypeError):
        return None

def remove_prefix(text, prefix):
    """Removes the prefix `prefix` from string `text` in case it is present."""
    return text[len(prefix):] if text.startswith(prefix) else text

def generate_sitemap_nodes(sitemap_text):
    """Generator for all node specifications in a sitemap source code. It
    yields dictionaries of the form:

        { "code": code, "depth": depth, "children": [] }

    Thereby `code` is a string representation of the node and `depth` is a
    number corresponding to the node's depth. The higher the depth is, the
    deeper the node need to be included in the final tree.
    """
    # In MediaWiki the maximal depth of a headline is 6 (as in HTML).
    # For list elements this maximal header depth is added so that list
    # elements will always be included under a headline node.
    max_headline_depth = 6

    headline_re = re.compile(r"""(={1,%s}) # Equal signs of the headline
                                 (.*)      # code defining the node
                                 \1        # Repeatation of the equal signs
                              """ % max_headline_depth, re.X)

    list_re = re.compile(r"""([*]+) # asteriks of a list element
                             (.*)   # code defining a sitemap node
                          """, re.X)

    for line in sitemap_text.splitlines():
        for regex, depth_start in ((headline_re, 0),
                                   (list_re, max_headline_depth)):
            match = regex.fullmatch(line.strip())

            if match:
                yield {
                    "code": match.group(2).strip(),
                    "depth": depth_start + len(match.group(1)),
                    "children": []
                }

        if line.startswith(": Exclude:"):
            header = remove_prefix(line, ": Exclude:").strip()

            yield { "type": "exclude", "header": header }

def insert_node(node, new_node):
    """Inserts the node `new_node` in the tree `node` at the right position
    regarding to the attribute `depth` of `node`."""
    if node["children"] and new_node["depth"] > node["children"][-1]["depth"]:
        insert_node(node["children"][-1], new_node)
    else:
        node["children"].append(new_node)

def parse_sitemap_node_codes(node):
    """Returns a new tree where the `code` attributes are parsed. The nodes of
    the new tree contain a `name` and a `title` attribute. The `name` attribute
    corresponds to the name of the node which shall be appear in the table of
    contents. The `title` corresponds to the title of the Wikibooks page the
    node points to. In case there is no article behind the node, the attribute
    `title` is `None`.
    """

    # Delete `{{Symbol|..%}}` at the end of the code
    code = re.sub(r"\s+\{Symbol\|\d+%\}\}\s+\Z", "", node["code"])

    # Parse links of the form `[[<title>|<name>]]`
    match = re.match(r"""
        \[\[      # [[
        ([^|\]]+) # title of the page on Wikibooks
        \|        # |
        ([^|\]]+) # name of the node in toc
        \]\]      # ]]
    """, code, re.X)

    if match:
        title = match.group(1)
        name = match.group(2)
    else:
        name = code
        title = None

    parsed_node = {
        "title": title,
        "name": name,
        "children": [parse_sitemap_node_codes(x) for x in node["children"]],
        "excludes": node.get("excludes", [])
    }
    return add_sitemap_node_type(parsed_node)

def add_sitemap_node_type(node, depth=0):
    """Returns a new tree where each node is enriched by a `type` attribute,
    which depends on its depth in the tree."""
    title = node["title"]
    name = node["name"]
    children = node["children"]

    return {
        "title": title,
        "name": name,
        "type": SITEMAP_NODE_TYPES[depth],
        "children": [add_sitemap_node_type(x, depth + 1) for x in children],
        "excludes": node["excludes"]
    }

def parse_sitemap(sitemap_text):
    """Parse the sitemap and returns a JSON object representing it.

    Arguments:
        sitemap_text -- content of the sitemap (a string)
    """
    root = {"children":[], "depth":0, "code": "Mathe für Nicht-Freaks"}

    last_node = None

    for node in generate_sitemap_nodes(sitemap_text):
        if lookup(node, "type") == "exclude":
            assert last_node

            if "excludes" not in last_node:
                last_node["excludes"] = []

            last_node["excludes"].append(node["header"])
        else:
            last_node = node
            insert_node(root, node)

    return parse_sitemap_node_codes(root)
