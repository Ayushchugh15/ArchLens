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
        "java", "c_sharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    assert all("error" not in item for item in results)


def test_chunker_creates_language_tagged_chunks(tmp_path):
    for filename, source in SAMPLES.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    chunks = create_chunks(str(tmp_path))
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert len(chunks) >= len(SAMPLES)
    assert {
        "java", "c_sharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    assert all(chunk["document"].strip() for chunk in chunks)


def test_javascript_and_typescript_receive_language_tagged_chunks():
    chunks = create_chunks("tests/fixtures")
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert "javascript" in languages
    assert "typescript" in languages
    assert all(chunk["metadata"].get("file") for chunk in chunks)
