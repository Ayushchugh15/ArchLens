# ArchLens

## AI-Powered Software Architecture & Knowledge Explorer

ArchLens analyzes source repositories, builds an architecture graph, indexes code, and provides repository-aware question answering.

## Language support

ArchLens uses Python's AST for Python, the official TypeScript compiler API for JavaScript/JSX/TypeScript/TSX, and Tree-sitter grammars for the other configured languages.

| Language | File extensions | Current support |
|---|---|---|
| Python | `.py` | AST analysis and declaration-aware chunks |
| JavaScript | `.js`, `.mjs`, `.cjs` | TypeScript compiler AST: imports, declarations, calls, class heritage, and declaration chunks |
| TypeScript | `.ts` | TypeScript compiler AST: imports, declarations, calls, class heritage, and declaration chunks |
| JSX / TSX | `.jsx`, `.tsx` | TypeScript compiler AST using JSX/TSX syntax mode |
| Java | `.java` | Generic syntax analysis and chunks |
| C# | `.cs` | Generic syntax analysis and chunks |
| Go | `.go` | Generic syntax analysis and chunks |
| C | `.c`, `.h` | Generic syntax analysis and chunks |
| C++ | `.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`, `.hxx` | Generic syntax analysis and chunks |
| Rust | `.rs` | Generic syntax analysis and chunks |
| PHP | `.php` | Generic syntax analysis and chunks |
| Ruby | `.rb` | Generic syntax analysis and chunks |
| Kotlin | `.kt`, `.kts` | Generic syntax analysis and chunks |
| Swift | `.swift` | Generic syntax analysis and chunks |

**Support-level note:** JavaScript/TypeScript parsing is performed by the TypeScript compiler API through Node.js; it no longer uses the native Tree-sitter Python binding. Java, C#, Go, C, C++, Rust, PHP, Ruby, Kotlin, and Swift use the generic Tree-sitter adapter, which currently extracts common declarations and imports. Generic-language parsing is not yet complete language-specific semantic analysis. C header files (`.h`) are currently treated as C; C++ header extensions are mapped to C++.

## Core capabilities

- Repository import from public GitHub HTTPS URLs
- Python AST, TypeScript compiler AST, and Tree-sitter source analysis
- File, class, interface, and function extraction where supported by the grammar
- Import statement extraction
- Architecture graph generation
- Language-tagged file and declaration chunks
- ChromaDB vector indexing
- Repository-scoped semantic retrieval
- RAG question answering with Ollama
- FastAPI backend and interactive web frontend

## Processing flow

```text
GitHub Repository
       |
       v
Language / Extension Registry
       |
       +--> Python AST Parser
       |
       +--> TypeScript compiler API (JS / JSX / TS / TSX)\n       |\n       +--> Tree-sitter Parsers (Java / C# / Go / C / C++ / Rust / PHP / Ruby / Kotlin / Swift)
       |
       v
Normalized Analysis Records
       |
       +--> Architecture Graph
       |
       +--> Language-aware Code Chunks
                    |
                    v
              Embeddings
                    |
                    v
                 ChromaDB
                    |
                    v
          Repository-aware Retrieval
                    |
                    v
               Ollama LLM
                    |
                    v
              FastAPI / UI
```

## Technology stack

- Python, FastAPI
- Python AST
- TypeScript compiler API (Node.js)\n- Tree-sitter Language Pack
- ChromaDB
- Ollama
- `nomic-embed-text` embeddings
- Qwen 2.5 Coder (configurable)
- HTML, CSS, JavaScript

## Run locally

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn backend.app:app --reload
```

For Docker, use:

```bash
docker compose up --build
```

The backend expects Ollama to be available at `OLLAMA_URL` (defaults to `http://localhost:11434`). In Docker Compose, the configured host URL is `http://host.docker.internal:11434`.

## Tests

Run the parser and language chunking tests:

```bash
pytest -q
```

The multi-language tests verify that configured grammars load and representative source files produce language-tagged chunks. They are not a substitute for evaluation on unfamiliar repositories.\n\n### Evaluate an unfamiliar repository\n\nRun the structural evaluation report against a local repository:\n\n```bash\npython scripts/evaluate_repository.py /path/to/target-repository --output archlens-evaluation.json\n```\n\nThe report includes parse success rate, files and declarations by language, chunk counts, graph relationship counts, unresolved calls/relationships, and any cross-language edges present in the graph. It is a coverage and diagnostics report, not a semantic-accuracy score. Review representative results manually before making accuracy claims.

## Current limitations

- Generic parser support is not equivalent to production-grade semantic analysis for every language. JavaScript/TypeScript uses the TypeScript compiler AST; other non-Python languages still use generic Tree-sitter extraction.
- Cross-file inheritance and interface implementation are resolved only when a referenced symbol has one unique definition; ambiguous matches are reported rather than guessed.\n- Python and JavaScript/TypeScript import-to-class links remain limited to the import forms currently extracted by their parsers.\n- Cross-file call resolution currently supports Python `from ... import ...` function/class aliases and JavaScript/TypeScript relative named imports for functions and class-qualified methods.\n- Python object-instance method resolution currently handles simple constructor assignments only; reassignment, factory-returned objects, and complex data flow are not modeled.\n- Python-to-Java (and other cross-language) call or service relationship resolution is not implemented. Parsing both languages in one repository does not mean ArchLens understands how their components communicate.\n- Default/namespace imports, re-exports, package-specific module rules, and cross-file calls for the generic Tree-sitter languages are not yet implemented.
- Code chunking and indexing are language-aware, but retrieval quality must be evaluated per language.
- Large repositories may require chunk-size limits, incremental indexing, and resource controls.
- Private GitHub repositories and authenticated Git providers are not currently supported by the import endpoint.
