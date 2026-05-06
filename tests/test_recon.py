# Tests for the Recon Agent.

import json
from forge.state import initial_state
from forge.agents.recon import recon_agent


def test_leak_c():
    # Test recon against the basic leak.c sample.
    state = initial_state(source_files={"leak.c": open("samples/easy/leak.c").read()})
    result = recon_agent(state)
    rmap = result["recon_map"]

    print(json.dumps(rmap, indent=2))

    # Basic checks
    assert "leak.c" in rmap["files"]
    assert len(rmap["functions"]) == 2

    names = {f["name"] for f in rmap["functions"]}
    assert names == {"make_buffer", "main"}

    # Signatures
    for f in rmap["functions"]:
        assert "signature" in f, f"{f['name']} missing signature"

    # Call graph
    main = next(f for f in rmap["functions"] if f["name"] == "main")
    assert "make_buffer" in main["calls"]
    assert "free" in main["calls"]

    mb = next(f for f in rmap["functions"] if f["name"] == "make_buffer")
    assert "malloc" in mb["calls"]
    assert "main" in mb["called_by"]

    # Entry points
    assert rmap["entry_points"] == ["main"]

    # Includes
    assert "stdlib.h" in rmap["includes"]["leak.c"]

    print("leak.c PASSED")


def test_header_file():
    # Test recon against a .h file with prototypes, structs, globals
    header = """
#include "types.h"

struct proc {
    int pid;
    char name[16];
};

typedef struct {
    int lock;
} spinlock_t;

int allocproc(void);
char* make_buffer(int size);
void sys_fork(void);

extern int initproc;
"""
    state = initial_state(source_files={"defs.h": header})
    result = recon_agent(state)
    rmap = result["recon_map"]

    print(json.dumps(rmap, indent=2))

    # Function declarations from header
    names = {f["name"] for f in rmap["functions"]}
    assert "allocproc" in names, f"missing allocproc, got {names}"
    assert "make_buffer" in names, f"missing make_buffer, got {names}"
    assert "sys_fork" in names, f"missing sys_fork, got {names}"

    # All should be declaration_only
    for f in rmap["functions"]:
        assert f.get("declaration_only") is True, f"{f['name']} should be declaration_only"

    # Structs
    struct_names = {s["name"] for s in rmap["structs"]}
    assert "proc" in struct_names, f"missing struct proc, got {struct_names}"
    assert "spinlock_t" in struct_names, f"missing spinlock_t, got {struct_names}"

    # Entry points (sys_fork starts with sys_)
    assert "sys_fork" in rmap["entry_points"]

    # Includes
    assert "types.h" in rmap["includes"]["defs.h"]

    print("header PASSED")


if __name__ == "__main__":
    test_leak_c()
    test_header_file()
    print("\nAll tests passed!")