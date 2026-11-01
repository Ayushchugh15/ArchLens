#!/usr/bin/env node
// Parse non-Python, non-JavaScript/TypeScript sources with Tree-sitter WebAssembly.
// The parser runs in a separate Node process; Python never loads the native binding.
const fs = require("node:fs");
const path = require("node:path");

const CLASS_NODES = new Set([
  "class_declaration", "interface_declaration", "enum_declaration",
  "record_declaration", "struct_declaration", "type_declaration",
  "type_spec", "struct_specifier", "class_specifier", "struct_item",
  "enum_item", "trait_item", "impl_item", "mod_item", "trait_declaration",
  "class", "module", "object_declaration", "protocol_declaration",
  "enum_specifier", "namespace_definition"
]);
const INTERFACE_NODES = new Set([
  "interface_declaration", "trait_item", "trait_declaration",
  "protocol_declaration"
]);
const FUNCTION_NODES = new Set([
  "function_declaration", "generator_function_declaration",
  "method_definition", "method_declaration", "constructor_declaration",
  "function_definition", "function_item", "method", "singleton_method"
]);
const IMPORT_NODES = new Set([
  "import_declaration", "using_directive", "preproc_include",
  "use_declaration", "namespace_use_declaration"
]);

const GRAMMAR_CANDIDATES = {
  csharp: ["c_sharp", "csharp"],
  cpp: ["cpp"],
  c: ["c"],
  java: ["java"],
  go: ["go"],
  rust: ["rust"],
  php: ["php"],
  ruby: ["ruby"],
  kotlin: ["kotlin"],
  swift: ["swift"]
};

function makeResult(file, language) {
  return {
    file, language, imports: [], import_details: [], classes: [],
    interfaces: [], functions: [], calls: [], inheritance: [],
    implementations: [], declaration_chunks: []
  };
}

function nodeText(node, source) {
  if (!node) return "";
  const start = node.startIndex ?? node.startByte;
  const end = node.endIndex ?? node.endByte;
  return source.slice(start, end);
}

function getName(node, source) {
  let nameNode = null;
  try {
    nameNode = node.childForFieldName("name");
  } catch (_) {}
  if (nameNode) return nodeText(nameNode, source).trim();

  for (const child of node.namedChildren || []) {
    if (["identifier", "type_identifier", "constant",
         "namespace_identifier", "name"].includes(child.type)) {
      return nodeText(child, source).trim();
    }
  }
  return null;
}

async function main() {
  const [, , filePath, language] = process.argv;
  const result = makeResult(filePath, language);
  try {
    const { Parser: ExportedParser, Language } = require("web-tree-sitter");
    const Parser = ExportedParser || require("web-tree-sitter");
    const wasmPackage = await import("tree-sitter-wasm");
    const getWasmPath = wasmPackage.getWasmPath;
    if (typeof getWasmPath !== "function") {
      throw new Error("tree-sitter-wasm does not expose getWasmPath().");
    }

    const source = fs.readFileSync(filePath, "utf8");
    await Parser.init();
    const parser = new Parser();
    const candidates = GRAMMAR_CANDIDATES[language] || [language];
    let grammarPath = null;
    let loadError = null;
    let grammar = null;
    for (const candidate of candidates) {
      try {
        const candidatePath = getWasmPath(candidate);
        grammar = await (Language || Parser.Language).load(candidatePath);
        grammarPath = candidatePath;
        break;
      } catch (error) {
        loadError = error;
      }
    }
    if (!grammar) {
      throw new Error(
        `No compatible WASM grammar found for '${language}': ${loadError?.message || "not packaged"}`
      );
    }

    parser.setLanguage(grammar);
    const tree = parser.parse(source);
    const root = tree.rootNode;
    if (root.hasError) result.parse_errors = true;

    function visit(node, enclosingClass = null) {
      const type = node.type;
      const line = (node.startPosition?.row ?? 0) + 1;
      const endLine = (node.endPosition?.row ?? 0) + 1;

      if (IMPORT_NODES.has(type)) {
        const statement = nodeText(node, source).trim();
        if (statement) {
          result.imports.push(statement);
          result.import_details.push({
            type: "import", module: statement, name: null, alias: null,
            import_kind: "statement", line, level: 0
          });
        }
      }

      let currentClass = enclosingClass;
      if (CLASS_NODES.has(type)) {
        const name = getName(node, source);
        if (name) {
          const target = INTERFACE_NODES.has(type)
            ? result.interfaces : result.classes;
          target.push({ name, line });
          currentClass = name;
          result.declaration_chunks.push({
            code: nodeText(node, source), type: "interface" in target ? "interface" : "class",
            name, class_name: enclosingClass, line, end_line: endLine
          });
        }
      }

      if (FUNCTION_NODES.has(type)) {
        const name = getName(node, source) || "<anonymous>";
        result.functions.push({
          name, line, arguments: [], class: currentClass
        });
        result.declaration_chunks.push({
          code: nodeText(node, source), type: "function", name,
          class_name: currentClass, line, end_line: endLine
        });
      }

      for (const child of node.namedChildren || []) {
        visit(child, currentClass);
      }
    }

    visit(root);
    parser.delete();
    grammar.delete();
  } catch (error) {
    result.error = error?.stack || String(error);
  }
  process.stdout.write(JSON.stringify(result));
}

main().catch(error => {
  process.stderr.write(error?.stack || String(error));
  process.exitCode = 1;
});
