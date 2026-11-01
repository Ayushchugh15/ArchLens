from pathlib import Path

from analyzer.create_code_chunks import create_chunks
from analyzer.repository_analyzer import analyze_repository


SAMPLES = {
    "sample.java": "class UserService { String getUser(int id) { return \"user\"; } }",
    "sample.cs": "class UserService { public string GetUser(int id) { return \"user\"; } }",
    "sample.go": "package main\ntype UserService struct {}\nfunc (s UserService) GetUser(id int) string { return \"user\" }",
    "sample.c": "struct User { int id; };\nint get_user(int id) { return id; }",
    "sample.cpp": "class UserService { public: int getUser(int id) { return id; } };",
    "sample.rs": "struct User { id: i32 }\nfn get_user(id: i32) -> i32 { id }",
    "sample.php": "<?php class UserService { public function getUser($id) { return $id; } }",
    "sample.rb": "class UserService\n  def get_user(id)\n    id\n  end\nend",
    "sample.kt": "class UserService { fun getUser(id: Int): Int { return id } }",
    "sample.swift": "class UserService { func getUser(id: Int) -> Int { return id } }",
}


def test_repository_analyzer_recognizes_additional_languages(tmp_path):
    for filename, source in SAMPLES.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    results = analyze_repository(str(tmp_path))
    languages = {item["language"] for item in results}

    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    errors = [(item["language"], item.get("error")) for item in results if item.get("error")]
    assert not errors, errors


def test_chunker_creates_language_tagged_chunks(tmp_path):
    for filename, source in SAMPLES.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    chunks = create_chunks(str(tmp_path))
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert len(chunks) >= len(SAMPLES)
    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    assert all(chunk["document"].strip() for chunk in chunks)

    declaration_languages = {
        chunk["metadata"]["language"]
        for chunk in chunks
        if chunk["metadata"]["type"] in {"class", "function"}
    }
    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= declaration_languages


def test_javascript_and_typescript_receive_language_tagged_chunks():
    chunks = create_chunks("tests/fixtures")
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert "javascript" in languages
    assert "typescript" in languages
    assert all(chunk["metadata"].get("file") for chunk in chunks)


def test_build_graph_resolves_unique_cross_file_inheritance_and_implementation(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "base.py"), "language": "python",
            "imports": [], "classes": [{"name": "BaseService", "line": 1}],
            "interfaces": [{"name": "ServiceContract", "line": 2}],
            "functions": [], "calls": [], "inheritance": [],
            "implementations": [],
        },
        {
            "file": str(tmp_path / "implementation.py"), "language": "python",
            "imports": [], "classes": [{"name": "UserService", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "UserService", "parent": "BaseService", "line": 1}],
            "implementations": [{"class": "UserService", "interface": "ServiceContract", "line": 1}],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    relationships = {
        (edge["relationship"], edge["source"], edge["target"])
        for edge in graph["edges"]
    }

    child = f"class:{analysis[1]['file']}:UserService:1"
    parent = f"class:{analysis[0]['file']}:BaseService:1"
    interface = f"interface:{analysis[0]['file']}:ServiceContract:2"
    assert ("extends", child, parent) in relationships
    assert ("implements", child, interface) in relationships
    assert not graph["unresolved_relationships"]


def test_build_graph_does_not_guess_ambiguous_cross_file_parent(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "one.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
        {
            "file": str(tmp_path / "two.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
        {
            "file": str(tmp_path / "child.py"), "language": "python",
            "imports": [], "classes": [{"name": "Child", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "Child", "parent": "Base", "line": 1}],
            "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    assert not [
        edge for edge in graph["edges"]
        if edge["relationship"] == "extends"
        and edge["source"].endswith(":Child:1")
    ]
    assert {
        "file": analysis[2]["file"], "kind": "extends",
        "source": "Child", "target": "Base", "reason": "ambiguous_target",
    } in graph["unresolved_relationships"]


def test_build_graph_prefers_same_file_parent_over_external_duplicate(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "local.py"), "language": "python",
            "imports": [], "classes": [
                {"name": "Base", "line": 1}, {"name": "Child", "line": 2}
            ],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "Child", "parent": "Base", "line": 2}],
            "implementations": [],
        },
        {
            "file": str(tmp_path / "external.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    child = f"class:{analysis[0]['file']}:Child:2"
    targets = {
        edge["target"] for edge in graph["edges"]
        if edge["relationship"] == "extends" and edge["source"] == child
    }
    assert targets == {f"class:{analysis[0]['file']}:Base:1"}


def test_build_graph_resolves_python_imported_function_and_class_method_aliases(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    service_file = str(tmp_path / "services.py")
    caller_file = str(tmp_path / "consumer.py")
    analysis = [
        {
            "file": service_file, "language": "python", "imports": [],
            "import_details": [], "classes": [{"name": "UserService", "line": 1}],
            "interfaces": [], "functions": [
                {"name": "fetch_user", "line": 2, "class": None},
                {"name": "get_user", "line": 3, "class": "UserService"},
            ], "calls": [], "inheritance": [], "implementations": [],
        },
        {
            "file": caller_file, "language": "python", "imports": ["services"],
            "import_details": [
                {"type": "from_import", "module": "services", "name": "fetch_user",
                 "alias": "load_user", "level": 0, "line": 1},
                {"type": "from_import", "module": "services", "name": "UserService",
                 "alias": "Service", "level": 0, "line": 2},
            ],
            "classes": [], "interfaces": [],
            "functions": [{"name": "run", "line": 4, "class": None}],
            "calls": [
                {"name": "load_user", "called_from": "run", "called_from_line": 4,
                 "called_from_class": None, "call_type": "direct", "line": 5},
                {"name": "get_user", "called_from": "run", "called_from_line": 4,
                 "called_from_class": None, "call_type": "attribute",
                 "receiver": "Service", "line": 6},
            ],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    calls = [edge for edge in graph["edges"] if edge["relationship"] == "calls"]
    assert len(calls) == 2
    assert {edge["resolution"] for edge in calls} == {
        "imported_function", "imported_class_method"
    }
    assert graph["call_resolution"]["resolved_calls"] == 2


def test_build_graph_resolves_javascript_named_import_function_alias(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    source_file = str(tmp_path / "helpers.js")
    caller_file = str(tmp_path / "app.js")
    analysis = [
        {
            "file": source_file, "language": "javascript", "imports": [],
            "import_details": [], "classes": [], "interfaces": [],
            "functions": [{"name": "formatUser", "line": 1, "class": None}],
            "calls": [], "inheritance": [], "implementations": [],
        },
        {
            "file": caller_file, "language": "javascript", "imports": ["./helpers"],
            "import_details": [
                {"type": "import", "module": "./helpers", "name": "formatUser",
                 "alias": "format", "import_kind": "named", "line": 1},
            ],
            "classes": [], "interfaces": [],
            "functions": [{"name": "render", "line": 2, "class": None}],
            "calls": [
                {"name": "format", "called_from": "render", "called_from_line": 2,
                 "called_from_class": None, "call_type": "direct",
                 "expression": "format(user)", "line": 3},
            ],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    calls = [edge for edge in graph["edges"] if edge["relationship"] == "calls"]
    assert len(calls) == 1
    assert calls[0]["resolution"] == "imported_function"
    assert graph["call_resolution"]["resolved_calls"] == 1
