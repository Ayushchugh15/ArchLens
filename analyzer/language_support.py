"""Central registry for languages and source-file extensions supported by ArchLens.

Parsing/indexing support does not imply complete cross-file resolution for every language.
"""

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cs": "c_sharp",
    ".go": "go",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
}

# Generic syntax node names used to identify useful code units.
# These are intentionally conservative; unknown syntax is still indexed
# as a file-level chunk rather than being silently discarded.
DECLARATION_NODES = {
    "javascript": {
        "class_declaration", "function_declaration",
        "generator_function_declaration", "method_definition",
        "arrow_function",
    },
    "typescript": {
        "class_declaration", "function_declaration",
        "generator_function_declaration", "method_definition",
        "arrow_function", "interface_declaration", "enum_declaration",
    },
    "java": {
        "class_declaration", "interface_declaration", "enum_declaration",
        "record_declaration", "method_declaration",
        "constructor_declaration",
    },
    "c_sharp": {
        "class_declaration", "interface_declaration", "struct_declaration",
        "enum_declaration", "method_declaration",
        "constructor_declaration", "property_declaration",
    },
    "go": {
        "function_declaration", "method_declaration", "type_declaration",
        "type_spec",
    },
    "c": {"function_definition", "struct_specifier", "enum_specifier"},
    "cpp": {
        "function_definition", "class_specifier", "struct_specifier",
        "enum_specifier", "namespace_definition",
    },
    "rust": {
        "function_item", "struct_item", "enum_item", "trait_item",
        "impl_item", "mod_item",
    },
    "php": {
        "class_declaration", "interface_declaration", "trait_declaration",
        "function_definition", "method_declaration",
    },
    "ruby": {"class", "module", "method", "singleton_method"},
    "kotlin": {
        "class_declaration", "object_declaration", "function_declaration",
    },
    "swift": {
        "class_declaration", "struct_declaration", "protocol_declaration",
        "enum_declaration", "function_declaration",
    },
}

CLASS_NODES = {
    "class_declaration", "interface_declaration", "enum_declaration",
    "record_declaration", "struct_declaration", "type_declaration",
    "type_spec", "struct_specifier", "class_specifier", "function_item",
    "struct_item", "enum_item", "trait_item", "impl_item", "mod_item",
    "trait_declaration", "class", "module", "object_declaration",
    "protocol_declaration", "enum_specifier", "namespace_definition",
}

FUNCTION_NODES = {
    "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration", "constructor_declaration",
    "function_definition", "function_item", "method", "singleton_method",
}
