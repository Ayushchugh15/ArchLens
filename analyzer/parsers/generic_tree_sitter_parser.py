"""Conservative Tree-sitter adapter for additional supported languages."""

from pathlib import Path
from tree_sitter_language_pack import get_parser
from analyzer.parsers.base_parser import BaseParser


CLASS_NODES = {
    "class_declaration", "interface_declaration", "enum_declaration",
    "record_declaration", "struct_declaration", "type_spec",
    "struct_specifier", "class_specifier", "function_item",
    "struct_item", "enum_item", "trait_item", "impl_item", "mod_item",
    "trait_declaration", "class", "module", "object_declaration",
    "protocol_declaration", "enum_specifier", "namespace_definition",
}
INTERFACE_NODES = {
    "interface_declaration", "trait_item", "trait_declaration",
    "protocol_declaration",
}
FUNCTION_NODES = {
    "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration", "constructor_declaration",
    "function_definition", "function_item", "method", "singleton_method",
}
IMPORT_NODES = {
    "import_declaration", "using_directive", "preproc_include",
    "use_declaration", "namespace_use_declaration",
}


class GenericTreeSitterParser(BaseParser):
    def __init__(self, language: str):
        self.language = language
        self.parser = get_parser(language)

    def parse_file(self, file_path: str) -> dict:
        path = Path(file_path)
        result = {
            "file": str(path), "language": self.language,
            "imports": [], "import_details": [], "classes": [],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
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

            def node_name(node):
                name_node = node.child_by_field_name("name")
                if name_node:
                    return node_text(name_node)
                for child in node.named_children:
                    if child.type in {
                        "identifier", "type_identifier", "constant",
                        "namespace_identifier", "name",
                    }:
                        return node_text(child)
                return None

            def visit(node, enclosing_class=None):
                node_type = node.type
                line = node.start_point.row + 1

                if node_type in IMPORT_NODES:
                    import_text = node_text(node).strip()
                    if import_text:
                        result["imports"].append(import_text)
                        result["import_details"].append({
                            "type": "import",
                            "module": import_text,
                            "name": None,
                            "alias": None,
                            "import_kind": "statement",
                            "line": line,
                            "level": 0,
                        })

                if node_type in CLASS_NODES:
                    name = node_name(node)
                    if name:
                        target = (
                            result["interfaces"]
                            if node_type in INTERFACE_NODES
                            else result["classes"]
                        )
                        target.append({"name": name, "line": line})
                        enclosing_class = name

                if node_type in FUNCTION_NODES:
                    result["functions"].append({
                        "name": node_name(node) or "<anonymous>",
                        "line": line,
                        "arguments": [],
                        "class": enclosing_class,
                    })

                for child in node.named_children:
                    visit(child, enclosing_class)

            visit(tree.root_node)

        except Exception as error:
            result["error"] = str(error)

        return result
