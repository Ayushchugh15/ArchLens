import ast
import json
import os
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

from analyzer.language_support import LANGUAGE_BY_EXTENSION
from analyzer.parsers.tree_sitter_parser import TreeSitterParser


IGNORE_DIRS = {
    ".git", "__pycache__", "venv", ".venv", "node_modules",
    "vendor", "dist", "build", "target", ".next",
}

DECLARATION_TYPES = {
    "class_declaration", "interface_declaration", "enum_declaration",
    "record_declaration", "struct_declaration", "type_declaration",
    "type_spec", "struct_specifier", "class_specifier",
    "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration", "constructor_declaration",
    "function_definition", "function_item", "struct_item", "enum_item",
    "trait_item", "impl_item", "mod_item", "trait_declaration",
    "class", "module", "method", "singleton_method",
    "object_declaration", "protocol_declaration", "enum_specifier",
    "namespace_definition",
}


def _python_chunks(source, relative_path, repo_name):
    chunks = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return chunks

    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            code = ast.get_source_segment(source, node) or ""
            if code.strip():
                chunks.append({
                    "document": code,
                    "metadata": {
                        "repository": repo_name, "file": relative_path,
                        "language": "python", "type": "class",
                        "name": node.name, "line": node.lineno,
                        "end_line": node.end_lineno,
                    },
                })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            code = ast.get_source_segment(source, node) or ""
            parent = parent_map.get(node)
            while parent and not isinstance(parent, ast.ClassDef):
                parent = parent_map.get(parent)
            class_name = parent.name if parent else None
            if code.strip():
                chunks.append({
                    "document": code,
                    "metadata": {
                        "repository": repo_name, "file": relative_path,
                        "language": "python", "type": "function",
                        "name": node.name, "class_name": class_name,
                        "qualified_name": (
                            f"{class_name}.{node.name}" if class_name else node.name
                        ),
                        "line": node.lineno, "end_line": node.end_lineno,
                    },
                })
    return chunks


def _tree_sitter_chunks(source_bytes, relative_path, repo_name, language):
    chunks = []
    try:
        parser = get_parser(language)
        tree = parser.parse(source_bytes)
        if tree.root_node.has_error:
            parse_errors = True
        else:
            parse_errors = False

        def visit(node, enclosing_class=None):
            node_type = node.type
            if node_type in DECLARATION_TYPES:
                name_node = node.child_by_field_name("name")
                name = (
                    source_bytes[name_node.start_byte:name_node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if name_node else None
                )
                start = node.start_byte
                end = node.end_byte
                code = source_bytes[start:end].decode("utf-8", errors="replace")
                line = node.start_point.row + 1
                is_class = node_type in {
                    "class_declaration", "interface_declaration",
                    "enum_declaration", "record_declaration",
                    "struct_declaration", "type_declaration", "type_spec",
                    "struct_specifier", "class_specifier", "struct_item",
                    "enum_item", "trait_item", "impl_item", "mod_item",
                    "trait_declaration", "class", "module",
                    "object_declaration", "protocol_declaration",
                    "enum_specifier", "namespace_definition",
                }
                kind = "class" if is_class else "function"
                if code.strip():
                    chunks.append({
                        "document": code,
                        "metadata": {
                            "repository": repo_name,
                            "file": relative_path,
                            "language": language,
                            "type": kind,
                            "name": name or f"<anonymous:{kind}>",
                            "class_name": enclosing_class,
                            "qualified_name": (
                                f"{enclosing_class}.{name}"
                                if enclosing_class and name and not is_class
                                else name
                            ),
                            "line": line,
                            "end_line": node.end_point.row + 1,
                            "parse_errors": parse_errors,
                        },
                    })
                if is_class and name:
                    enclosing_class = name

            for child in node.named_children:
                visit(child, enclosing_class)

        visit(tree.root_node)
    except Exception as error:
        # Keep file-level retrieval available even if one grammar fails.
        return chunks, str(error)
    return chunks, None


def create_chunks(repository_path):
    """Create language-aware file and declaration chunks for a repository."""
    repository_path = os.path.abspath(repository_path)
    repo_name = os.path.basename(repository_path)
    chunks = []

    for root, dirs, files in os.walk(repository_path):
        dirs[:] = [directory for directory in dirs if directory not in IGNORE_DIRS]

        for filename in files:
            extension = Path(filename).suffix.lower()
            language = LANGUAGE_BY_EXTENSION.get(extension)
            if not language:
                continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, repository_path)

            try:
                source_bytes = Path(file_path).read_bytes()
                source = source_bytes.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not source.strip():
                continue

            # File-level context supports questions that span declarations.
            chunks.append({
                "document": source,
                "metadata": {
                    "repository": repo_name,
                    "file": relative_path,
                    "language": language,
                    "type": "file",
                    "name": filename,
                    "line": 1,
                },
            })

            if language == "python":
                chunks.extend(_python_chunks(source, relative_path, repo_name))
            elif language in {"javascript", "typescript", "tsx"}:
                parsed = TreeSitterParser(language).parse_file(file_path)
                for declaration in parsed.get("declaration_chunks", []):
                    chunks.append({
                        "document": declaration["code"],
                        "metadata": {
                            "repository": repo_name,
                            "file": relative_path,
                            "language": language,
                            "type": declaration["type"],
                            "name": declaration["name"],
                            "class_name": declaration.get("class_name"),
                            "qualified_name": (
                                str(declaration["class_name"]) + "." + str(declaration["name"])
                                if declaration.get("class_name")
                                and declaration["type"] == "function"
                                else declaration["name"]
                            ),
                            "line": declaration["line"],
                            "end_line": declaration["end_line"],
                            "parse_errors": bool(parsed.get("parse_errors", False)),
                        },
                    })
                if parsed.get("error"):
                    print(
                        "JavaScript/TypeScript chunking skipped declarations in "
                        + relative_path + ": " + parsed["error"]
                    )
            else:
                declaration_chunks, error = _tree_sitter_chunks(
                    source_bytes, relative_path, repo_name, language
                )
                chunks.extend(declaration_chunks)
                if error:
                    print("Tree-sitter chunking skipped declarations in "
                          + relative_path + ": " + error)

    return chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyzer/create_code_chunks.py <repository_path>")
        sys.exit(1)

    repository_path = sys.argv[1]
    if not os.path.isdir(repository_path):
        print(f"Repository not found: {repository_path}")
        sys.exit(1)

    repo_name = os.path.basename(os.path.abspath(repository_path))
    chunks = create_chunks(repository_path)
    output_file = f"code_chunks_{repo_name}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(chunks, file, indent=2)

    print("Code chunking completed.")
    print(f"Repository: {repo_name}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Languages: {', '.join(sorted({c['metadata']['language'] for c in chunks}))}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
