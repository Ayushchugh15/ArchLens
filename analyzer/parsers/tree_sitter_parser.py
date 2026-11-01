from pathlib import Path

from tree_sitter_language_pack import get_parser

from analyzer.parsers.base_parser import BaseParser


class _SyntaxNodeSnapshot:
    """Python-only copy of the Tree-sitter data used by the analyzer."""

    __slots__ = ("type", "start_byte", "end_byte", "start_point", "children", "fields", "parent")

    def __init__(self, node_type, start_byte, end_byte, start_point):
        self.type = node_type
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.start_point = start_point
        self.children = []
        self.fields = {}
        self.parent = None

    def child_by_field_name(self, name):
        return self.fields.get(name)


def _snapshot_tree(root_node):
    """Copy syntax metadata before running extraction on Python objects only."""
    cursor = root_node.walk()

    def copy_cursor(current):
        native_node = current.node
        copied = _SyntaxNodeSnapshot(
            native_node.type,
            native_node.start_byte,
            native_node.end_byte,
            native_node.start_point,
        )

        if current.goto_first_child():
            while True:
                field_name = current.current_field_name
                child = copy_cursor(current.copy())
                child.parent = copied
                copied.children.append(child)
                if field_name is not None:
                    copied.fields[field_name] = child
                if not current.goto_next_sibling():
                    break

        return copied

    return copy_cursor(cursor)


class TreeSitterParser(BaseParser):

    def __init__(self, language: str):
        if language not in {"javascript", "typescript"}:
            raise ValueError(f"Unsupported language: {language}")

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

            root = _snapshot_tree(tree.root_node)
            del tree

            def text(node):
                return source[
                    node.start_byte:node.end_byte
                ].decode("utf-8", errors="replace")

            def extract_arguments(node):
                arguments = []

                if node is None:
                    return arguments

                def collect_parameters(parameter_node):
                    if parameter_node.type == "identifier":
                        arguments.append(text(parameter_node))

                    elif parameter_node.type in {
                        "required_parameter",
                        "optional_parameter",
                    }:
                        name_node = parameter_node.child_by_field_name("pattern")

                        if name_node:
                            collect_parameters(name_node)

                    elif parameter_node.type == "assignment_pattern":
                        left_node = parameter_node.child_by_field_name("left")

                        if left_node:
                            collect_parameters(left_node)

                    elif parameter_node.type == "rest_pattern":
                        for child in parameter_node.children:
                            if child.type == "identifier":
                                arguments.append("..." + text(child))

                    else:
                        for child in parameter_node.children:
                            collect_parameters(child)

                for child in node.children:
                    collect_parameters(child)

                return arguments

            def visit(
                node,
                current_function=None,
                current_function_line=None,
                current_class=None
            ):

                node_type = node.type

                # -----------------------------
                # IMPORTS
                # -----------------------------

                if node_type == "import_statement":

                    module_node = None
                    import_clause = None

                    for child in node.children:
                        if child.type == "string":
                            module_node = child
                        elif child.type == "import_clause":
                            import_clause = child

                    if module_node:
                        module = text(module_node).strip("'\"")

                        result["imports"].append(module)

                        line = node.start_point.row + 1

                        if import_clause is None:
                            result["import_details"].append({
                                "type": "import",
                                "module": module,
                                "name": None,
                                "alias": None,
                                "import_kind": "side_effect",
                                "line": line,
                                "level": 0,
                            })

                        else:
                            for child in import_clause.children:

                                # Default import
                                if child.type == "identifier":
                                    local_name = text(child)

                                    result["import_details"].append({
                                        "type": "import",
                                        "module": module,
                                        "name": None,
                                        "alias": local_name,
                                        "import_kind": "default",
                                        "line": line,
                                        "level": 0,
                                    })

                                # Named imports
                                elif child.type == "named_imports":
                                    for specifier in child.children:
                                        if specifier.type != "import_specifier":
                                            continue

                                        identifiers = [
                                            part for part in specifier.children
                                            if part.type == "identifier"
                                        ]

                                        if not identifiers:
                                            continue

                                        imported_name = text(identifiers[0])
                                        local_name = text(identifiers[-1])

                                        result["import_details"].append({
                                            "type": "import",
                                            "module": module,
                                            "name": imported_name,
                                            "alias": (
                                                local_name
                                                if local_name != imported_name
                                                else None
                                            ),
                                            "import_kind": "named",
                                            "line": line,
                                            "level": 0,
                                        })

                                # Namespace imports
                                elif child.type == "namespace_import":
                                    identifiers = [
                                        part for part in child.children
                                        if part.type == "identifier"
                                    ]

                                    if identifiers:
                                        local_name = text(identifiers[-1])

                                        result["import_details"].append({
                                            "type": "import",
                                            "module": module,
                                            "name": None,
                                            "alias": local_name,
                                            "import_kind": "namespace",
                                            "line": line,
                                            "level": 0,
                                        })

                # INTERFACES
                if node_type == "interface_declaration":
                    name_node = node.child_by_field_name("name")

                    if name_node:
                        result.setdefault("interfaces", []).append({
                            "name": text(name_node),
                            "line": node.start_point.row + 1,
                        })
                # -----------------------------
                # CLASSES
                # -----------------------------

                if node_type == "class_declaration":

                    name_node = node.child_by_field_name(
                        "name"
                    )

                    if name_node:

                        class_name = text(name_node)

                        result["classes"].append({
                            "name": class_name,
                            "line": node.start_point.row + 1,
                        })

                        current_class = class_name

                # INHERITANCE
                if node_type == "class_declaration":
                    name_node = node.child_by_field_name("name")

                    if name_node:
                        class_name = text(name_node)

                        for child in node.children:
                            if child.type == "class_heritage":
                                for clause in child.children:
                                    if clause.type == "extends_clause":

                                        def find_parent(parent_node):
                                            if parent_node.type in {
                                                "identifier",
                                                "type_identifier",
                                            }:
                                                result["inheritance"].append({
                                                    "class": class_name,
                                                    "parent": text(parent_node),
                                                    "line": node.start_point.row + 1,
                                                })
                                                return

                                            for nested in parent_node.children:
                                                find_parent(nested)

                                        find_parent(clause)

                # INTERFACE IMPLEMENTATION
                if node_type == "class_declaration":
                    name_node = node.child_by_field_name("name")

                    if name_node:
                        class_name = text(name_node)

                        for child in node.children:
                            if child.type == "class_heritage":
                                for clause in child.children:
                                    if clause.type == "implements_clause":
                                        for interface_node in clause.children:
                                            if interface_node.type in {
                                                "identifier",
                                                "type_identifier",
                                            }:
                                                result.setdefault(
                                                    "implementations", []
                                                ).append({
                                                    "class": class_name,
                                                    "interface": text(interface_node),
                                                    "line": node.start_point.row + 1,
                                                })

                # -----------------------------
                # FUNCTIONS AND METHODS
                # -----------------------------

                if node_type in {
                    "function_declaration",
                    "generator_function_declaration",
                    "method_definition",
                }:

                    name_node = node.child_by_field_name(
                        "name"
                    )

                    if name_node:

                        function_name = text(name_node)
                        function_line = node.start_point.row + 1

                        result["functions"].append({
                            "name": function_name,
                            "line": function_line,
                            "arguments": extract_arguments(
                                node.child_by_field_name("parameters")
                            ),
                            "class": current_class,
                        })

                        current_function = function_name
                        current_function_line = function_line

                # -----------------------------
                # ARROW FUNCTIONS
                # -----------------------------

                if node_type == "arrow_function":

                    parent = node.parent
                    function_name = "<anonymous_arrow>"

                    if (
                        parent
                        and parent.type == "variable_declarator"
                    ):

                        name_node = parent.child_by_field_name(
                            "name"
                        )

                        if name_node:
                            function_name = text(name_node)

                    function_line = node.start_point.row + 1

                    result["functions"].append({
                        "name": function_name,
                        "line": function_line,
                        "arguments": extract_arguments(
                            node.child_by_field_name("parameters")
                        ),
                        "class": current_class,
                    })

                    current_function = function_name
                    current_function_line = function_line

                # CONSTRUCTOR CALLS
                if node_type == "new_expression":
                    constructor_node = node.child_by_field_name("constructor")

                    if constructor_node:
                        result["calls"].append({
                            "name": text(constructor_node),
                            "called_from": current_function,
                            "called_from_line": current_function_line,
                            "called_from_class": current_class,
                            "line": node.start_point.row + 1,
                            "call_type": "constructor",
                            "expression": text(constructor_node),
                            "receiver": None,
                        })

                # -----------------------------
                # FUNCTION CALLS
                # -----------------------------

                if node_type == "call_expression":

                    function_node = node.child_by_field_name(
                        "function"
                    )

                    if function_node:

                        call_expression = text(function_node)

                        receiver = None
                        call_name = call_expression

                        if function_node.type == "member_expression":

                            object_node = (
                                function_node.child_by_field_name(
                                    "object"
                                )
                            )

                            property_node = (
                                function_node.child_by_field_name(
                                    "property"
                                )
                            )

                            if object_node:
                                receiver = text(object_node)

                            if property_node:
                                call_name = text(property_node)

                        result["calls"].append({
                            "name": call_name,
                            "called_from": current_function,
                            "called_from_line": current_function_line,
                            "called_from_class": current_class,
                            "line": node.start_point.row + 1,
                            "call_type": (
                                "attribute"
                                if receiver
                                else "direct"
                            ),
                            "expression": call_expression,
                            "receiver": receiver,
                        })

                # -----------------------------
                # CHILD NODES
                # -----------------------------

                for child in node.children:

                    visit(
                        child,
                        current_function,
                        current_function_line,
                        current_class,
                    )

            visit(root)

        except Exception as error:
            result["error"] = str(error)

        return result
