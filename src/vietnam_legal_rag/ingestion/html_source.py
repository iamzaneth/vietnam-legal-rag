"""Small source-preserving HTML tree with deterministic DOM references."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re


NON_CONTENT = {"head", "script", "style", "template"}
BLOCK_TAGS = {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "li", "ul", "ol", "blockquote", "pre", "dt", "dd", "button", "caption"}


def whitespace(text: str) -> str:
    """Collapse formatting whitespace without normalizing spelling or Unicode."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def whole_unit_emphasis(node):
    """All meaningful display text is bold; inline note markers may differ."""
    seen = False
    def visit(current, inherited=False):
        nonlocal seen
        if current.tag in NON_CONTENT or current.tag in {'sup', 'sub'}:
            return True
        bold = inherited or current.tag in {'b', 'strong'} or bool(re.search(
            r'font-weight\s*:\s*(?:bold|[7-9]00)', current.attrs.get('style', ''), re.I))
        for child in current.children:
            if isinstance(child, str):
                if whitespace(child):
                    if not bold:
                        return False
                    seen = True
            elif not visit(child, bold):
                return False
        return True
    return visit(node) and seen


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    dom_order: int = 0
    line: int = 0
    column: int = 0
    issues: list = field(default_factory=list)
    text_refs: dict = field(default_factory=dict)
    document_titles: list = field(default_factory=list)

    @property
    def ref(self) -> dict:
        return {"tag": self.tag, "dom_order": self.dom_order, "line": self.line, "column": self.column}

    def find(self, tag: str | None = None, css_class: str | None = None) -> list[Node]:
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if ((tag is None or child.tag == tag)
                        and (css_class is None or css_class in child.attrs.get("class", "").split())):
                    result.append(child)
                result.extend(child.find(tag, css_class))
        return result

    def text(self, blocks: bool = False) -> str:
        if self.tag in NON_CONTENT:
            return ""
        if self.tag == "br":
            return "\n" if blocks else " "
        parts = []
        for child in self.children:
            if isinstance(child, str):
                # Newlines in text nodes are HTML formatting, not explicit breaks.
                parts.append(re.sub(r"\s+", " ", child.replace("\xa0", " ")))
            else:
                value = child.text(blocks)
                if child.tag in BLOCK_TAGS:
                    separator = "\n" if blocks else " "
                    value = separator + value + separator
                elif child.tag in {"td", "th"}:
                    value = " " + value + " "
                parts.append(value)
        value = "".join(parts)
        if blocks:
            return "\n".join(whitespace(line) for line in value.split("\n")).strip()
        return whitespace(value)


class SourceHTMLParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
            "meta", "param", "source", "track", "wbr"}
    P_BREAKERS = BLOCK_TAGS | {"table", "thead", "tbody", "tfoot"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.counter = 0

    def issue(self, code: str, message: str, node: Node | None = None) -> None:
        self.root.issues.append({"code": code, "message": message,
                                 "source_ref": (node or self.stack[-1]).ref})

    def close_optional(self, tag: str) -> None:
        # Limit implicit endings to the nearest structural scope. Do not close
        # an outer row/cell/list item when a nested table/list starts.
        targets = {"li": {"li"}, "tr": {"tr"}, "td": {"td", "th"}, "th": {"td", "th"},
                   "thead": {"thead", "tbody", "tfoot"}, "tbody": {"thead", "tbody", "tfoot"},
                   "tfoot": {"thead", "tbody", "tfoot"}, "dt": {"dt", "dd"}, "dd": {"dt", "dd"}}
        scopes = {"li": {"ul", "ol"}, "tr": {"table", "thead", "tbody", "tfoot"},
                  "td": {"tr", "table"}, "th": {"tr", "table"},
                  "thead": {"table"}, "tbody": {"table"}, "tfoot": {"table"},
                  "dt": {"dl"}, "dd": {"dl"}}
        for index in range(len(self.stack) - 1, 0, -1):
            node = self.stack[index]
            if node.tag in targets.get(tag, set()) or (node.tag == "p" and tag in self.P_BREAKERS):
                self.issue("implied_end_tag", f"HTML implied the end of {node.tag} before {tag}", node)
                del self.stack[index:]
                break
            if node.tag in scopes.get(tag, {"table", "td", "th"}):
                break

    def handle_starttag(self, tag, attrs):
        self.close_optional(tag)
        self.counter += 1
        line, column = self.getpos()
        node = Node(tag, dict(attrs), dom_order=self.counter, line=line, column=column)
        self.stack[-1].children.append(node)
        if len(dict(attrs)) != len(attrs):
            self.issue("duplicate_attribute", f"Duplicate attributes on {tag}; last values retained", node)
            node.attrs["_source_attributes"] = [list(pair) for pair in attrs]
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                if any(n.tag not in {"p", "li", "td", "th", "tr", "tbody", "thead", "tfoot"}
                       for n in self.stack[index + 1:]):
                    self.issue("misnested_html", f"Unclosed markup before </{tag}>")
                del self.stack[index:]
                return
        if tag not in self.VOID:
            self.issue("unmatched_end_tag", f"Unmatched closing tag: {tag}")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        self.counter += 1
        line, column = self.getpos()
        self.stack[-1].text_refs[len(self.stack[-1].children)] = {
            "tag": "#text", "dom_order": self.counter, "line": line, "column": column,
        }
        self.stack[-1].children.append(data)

    def handle_comment(self, data):
        if data.strip():
            self.counter += 1
            line, column = self.getpos()
            self.stack[-1].children.append(Node("comment", {"comment": data},
                                               dom_order=self.counter, line=line, column=column))

    def unknown_decl(self, data):
        self.counter += 1
        line, column = self.getpos()
        text = data[6:] if data.startswith("CDATA[") else data
        node = Node("declaration", {"source_declaration": data}, [text],
                    dom_order=self.counter, line=line, column=column)
        self.stack[-1].children.append(node)
        self.issue("unknown_declaration", "Unrecognized declaration retained without interpreting its role", node)


def parse_html(html: str) -> Node:
    parser = SourceHTMLParser()
    parser.feed(html)
    parser.close()
    if len(parser.stack) > 1:
        parser.issue("unclosed_html", "HTML ended with unclosed elements")
    bodies = parser.root.find("body")
    root = bodies[0] if len(bodies) == 1 else parser.root
    root.issues = parser.root.issues
    root.document_titles = [{"text": title.text(), "source_ref": title.ref}
                            for title in parser.root.find("title")]
    if len(bodies) > 1:
        parser.issue("multiple_bodies", "Multiple body elements retained in source order")
    return root
