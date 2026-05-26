from __future__ import annotations
from forge.state import ForgeState, log_step
import tree_sitter_c as tsc
import tree_sitter as ts

try:
    _C_LANGUAGE = ts.Language(tsc.language(), "c")
except TypeError:
    _C_LANGUAGE = ts.Language(tsc.language())

def _parse(content: bytes) -> ts.Tree:
    parser = ts.Parser(_C_LANGUAGE)
    return parser.parse(content)

def _find_function_name(node) -> str | None:
    for child in node.children:
        if child.type == "function_declarator":
            for c in child.children:
                if c.type == "identifier":
                    return c.text.decode()
        elif child.type == "pointer_declarator":
                return _find_function_name(child)
    return None 

def _get_signature(func_node, source_bytes: bytes) -> str:
    for child in func_node.children:
        if child.type == "compound_statement":
            return source_bytes[func_node.start_byte:child.start_byte].decode().strip()
    return source_bytes[func_node.start_byte:child.end_byte].decode().strip()

def _collect_calls(node) -> set[str]:
    calls = set()
    if node.type == "call_expression" and node.children:
        callee = node.children[0]
        if callee.type == "identifier":
            calls.add(callee.text.decode())
    for child in node.children:
        calls |= _collect_calls(child)
    return calls

_BRANCH_TYPES = {"if_statement", "for_statement", "while_statement", 
                 "switch_statement", "case_statement", "do_statement", "conditional_expression"}
def _complexity_count(node) -> int:
    count = 1 if node.type in _BRANCH_TYPES else 0
    for child in node.children:
        count += _complexity_count(child)
    return count

def _parse_file(filename: str, content: bytes) -> tuple[list, list, list, list]:
    tree = _parse(content)
    functions, includes, globals_, structs = [], [], [], []

    def _process_node(node):
        if node.type == "function_definition":
            name = _find_function_name(node)
            if not name:
                return
            body = next((c for c in node.children if c.type == "compound_statement"), None)
            functions.append({
                "name": name,
                "file": filename,
                "signature": _get_signature(node, content),
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "calls": sorted(_collect_calls(body) if body else set()),
                "called_by": [],
                "complexity": _complexity_count(body) if body else 1,
            })
        elif node.type == "preproc_include":
            for child in node.children:
                if child.type in ("string_literal", "system_lib_string"):
                    includes.append(child.text.decode().strip('"<>'))
        elif node.type == "struct_specifier":
            for child in node.children:
                if child.type == "type_identifier":
                    structs.append({
                        "name": child.text.decode(),
                        "file": filename,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                    })
        elif node.type == "type_definition":
            for child in node.children:
                if child.type == "type_identifier":
                    structs.append({
                        "name": child.text.decode(),
                        "file": filename,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                    })
        elif node.type == "declaration":
            name = _find_function_name(node)
            if name:
                sig = node.text.decode().rstrip(";").strip()
                functions.append({
                    "name": name,
                    "file": filename,
                    "signature": sig,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "calls": [],
                    "called_by": [],
                    "complexity": 0,
                    "declaration_only": True,
                })
            else:
                for child in node.children:
                    if child.type == "identifier":
                        globals_.append(child.text.decode())
        elif node.type in ("preproc_ifdef", "preproc_if", "preproc_ifndef"):
            # Recurse into #ifdef / #ifndef / #if blocks
            for child in node.children:
                _process_node(child)

    for node in tree.root_node.children:
        _process_node(node)

    return functions, includes, globals_, structs

_ENTRY_NAMES = {"main", "userinit", "scheduler", "forkret"}

def recon_agent(state: ForgeState) -> ForgeState:
    source_files = state.get("source_files", {})
    log_step(state, "recon", f"parsing {len(source_files)} file(s)")

    all_functions, all_includes, all_globals, all_structs = [], {}, [], []
    for filename, content in source_files.items():
        funcs, incs, globs, structs = _parse_file(filename, content.encode())
        all_functions.extend(funcs)
        all_includes[filename] = incs
        all_globals.extend(globs)
        all_structs.extend(structs)

    for func in all_functions:
        func["called_by"] = [other["name"] for other in all_functions if func["name"] in other["calls"] and other["name"] != func["name"]]

    entry_points = [f["name"] for f in all_functions if f["name"] in _ENTRY_NAMES or f["name"].startswith("sys_")]
    state["recon_map"] = {
        "files": list(source_files.keys()),
        "functions": all_functions,
        "entry_points": entry_points,
        "includes": all_includes,
        "globals": all_globals,
        "structs": all_structs,
    }
    log_step(state, "recon", f"found {len(all_functions)} functions, {len(entry_points)} entry point(s)")
    return state
        

