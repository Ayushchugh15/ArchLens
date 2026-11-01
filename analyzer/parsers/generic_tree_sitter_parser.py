"""Conservative Tree-sitter adapter for languages beyond JS/TS."""

from pathlib import Path

from tree_sitter_language_pack import get_parser

from analyzer.parsers.base_parser import BaseParser
from analyzer.language_support import CLASS_NODES, FUNCTION_NODES


class GenericTreeSitterParser(BaseParser):
    def __init__(self, language: str):
        self.language = language
        self.parser = get_parser(language)

    def parse_file(self, file_path: str) -> dict:
        path = Path(file_path)
        result = {
            "file": str(path),
            "language": self.language,
            "imports": [],
            "import_details": [],
            "classes": [],
            "interfaces": [],
            "functions": [],
            "calls": [],
            "inheritance": [],
            "implementations": [],
        }

        try:
            source = path.read_bytes()
            tree = self.parser.parse(source)
            if tree.root_node.has_error:
                result["parse_errors"] = True

            def node_text(node):
                return source[node.start_byte:node.end_byte].decode(
                    "utf-8", errors="replace"
                )

            def get_name(node):
                name_node = node.child_by_field_name("name")
                if name_node:
                    return node_text(name_node)
                # Some grammars represent names as the first named child.
                for child in node.named_children:
                    if child.type in {
                        "identifier", "type_identifier", "constant",
                        "namespace_identifier", "name",
                    }:
                        return node_text(child)
                return None

            def walk(node, enclosing_class=None):
                node_type = node.type
                line = node.start_point.row + 1

                if node_type in CLASS_NODES:
                    name = get_name(node)
                    if name:
                        target = (
                            result["interfaces"]
                            if "interface" in node_type or node_type in {
                                "trait_item", "trait_declaration",
                                "protocol_declaration",
                            }
                            else result["classes"]
                        )
                        target.append({"name": name, "line": line})
                        enclosing_class = name

                if node_type in FUNCTION_NODES:
                    name = get_name(node) or "<anonymous>"
                    result["functions"].append({
                        "name": name,
                        "line": line,
                        "arguments": [],
                        "class": enclosing_class,
                    })

                for child in node.named_children:
                    walk(child, enclosing_class)

            walk(tree.root_node)

        except Exception as error:
            result["error"] = str(error)

        return result
