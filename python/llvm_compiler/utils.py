from dataclasses import dataclass, field
import math
from typing import Optional
from termcolor import colored
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import data
from llvmlite import binding as llvm


def split_num(num, bitwidth, num_bitwidth, endian="little"):
    if num < 0:
        raise ValueError("num must be non-negative")
    if bitwidth <= 0:
        raise ValueError("bitwidth must be positive")

    chunks = []
    mask = (1 << bitwidth) - 1
    while num > 0:
        chunks.append(num & mask)
        num >>= bitwidth

    expected_chunks = math.ceil(num_bitwidth/bitwidth)
    while len(chunks) < expected_chunks:
        chunks.append(0)

    if endian == "big":
        chunks.reverse()

    return chunks or [0]


def _short(obj, maxlen=80):
    s = repr(obj)
    return s if len(s) <= maxlen else s[:maxlen - 3] + "..."

def _trace_list(xs):
    return [x.trace() if hasattr(x, "trace") else x for x in xs]

def _trace_kv(**kw):
    return {k: v for k, v in kw.items() if v not in (None, [], {}, "")}


def error(compiler, message: str, line_content: Optional[str] = None, highlight: str = "", is_warning = False, fatal_error = True, line_i: Optional[int] = None):
    # Severity
    level_text = "Warning" if is_warning else "Error"
    level_color = (255, (not fatal_error)*80 + is_warning*160, 0)
    formatted_level = colored(level_text, level_color, attrs=["bold"])

    # Build context info
    location = ""
    location += f" in file {colored(compiler.current_file.name, (0xF4, 0xB2, 0x66), attrs=['underline'])}"
    
    if line_i is not None:
        location += f" at line {colored(line_i+1, 'cyan')}"

    formatted_msg = colored(f">>> {message} <<<", "grey")

    # Print header
    full_error = f"\n{formatted_level}{location}:\n{formatted_msg}\n"

    # Print line content with highlighting
    if line_content:
        full_error += "\n" + colored(line_content, (144,213,255))
        if highlight and (idx := line_content.find(highlight)) >= 0:
            full_error += "\n" + (" " * idx) + colored("^" * len(highlight), "red")

    if fatal_error: raise CompileError(full_error)
    elif compiler.show_warnings and is_warning: print(full_error)



class CompileError(Exception):
    pass


@dataclass
class Temp:
    llvm_obj: llvm.ValueRef
    type: llvm.TypeRef
    id: int
    bitwidth: int
    parent: Optional['Temp']
    children: list['Temp'] = field(default_factory=list)
    trace_id: int = 0  # only for tracing

    def trace(self) -> dict:
        return _trace_kv(
            id=self.id,
            type=self.type.name,
            bitwidth=self.bitwidth,
            children=_trace_list(self.children) if self.children else None,
        )

    def __repr__(self):
        child_ids = [c.id for c in self.children] if self.children else None
        parent_id = self.parent.id if self.parent else None
        return (f"Temp(id={self.id}, type={self.type}, bitwidth={self.bitwidth}, "
                f"parent={parent_id}, children={child_ids})")

    
class Func:
    def __init__(self, llvm_obj: llvm.ValueRef, free_regs) -> None:
        assert llvm_obj.is_function, "tried creating a func with a non func valueref"
        self.name = llvm_obj.name
        self.llvm_obj = llvm_obj
        self.blocks: list[Block] = []
        self.params:  list[tuple[Temp, list[int] | list[str]]] = []  # type, [registers] or [stack slots]
        self.result: tuple[Temp, list[int] | list[str]] | None = None # pyright: ignore[reportAttributeAccessIssue]
        self.stack_offset: int = 0
        self.free_regs = free_regs   # starts as not used in params, then later used in temp defs
        self.free_slots = []
        self.spilled_temps: list[Temp] = []
        self.stack_offset = 0
        self.locals:  list[tuple[Temp, list[int] | list[str]]] = []  # the ssa temps
        self._trace_id_map: dict[Temp, int] = {}

    def __repr__(self) -> str:
            return (
                f"Func({self.name}, "
                f"blocks={len(self.blocks)}, "
                f"locals={len(self.locals)}, "
                f"spills={len(self.spilled_temps)}, "
                f"stack={self.stack_offset}, "
                f"params={len(self.params)}, "
                f"result={self.result}, "
                f"stack={self.stack_offset})"
            )

    def assign_trace_ids(self):
        """Assign sequential trace IDs to all temps in execution order"""
        next_id = 0

        def visit(temp: Temp):
            nonlocal next_id
            if temp not in self._trace_id_map:
                self._trace_id_map[temp] = next_id
                temp.trace_id = next_id
                next_id += 1
            for c in temp.children:
                visit(c)

        # first params
        for t, _ in self.params:
            visit(t)

        # result
        if self.result:
            visit(self.result[0])

        # locals in blocks, in order
        for block in self.blocks:
            for inst in block.ir:
                if inst.output:
                    visit(inst.output)
                for inp in inst.inputs:
                    visit(inp)
                    
    def trace(self) -> dict:
        return _trace_kv(
            name=self.name,
            blocks=[b.trace() for b in self.blocks],
            locals=[(t.trace(), loc) for t, loc in self.locals] or None,
            free_regs=self.free_regs or None,
            free_slots=self.free_slots or None,
            spills=[t.trace() for t in self.spilled_temps] or None,
            params=[(t.trace(), loc) for t, loc in self.params] or None,
            result=(self.result[0].trace(), self.result[1]) if self.result else None,
            stack=self.stack_offset,
        )

@dataclass
class Block:
    llvm_obj: llvm.ValueRef
    id: int
    entering_blocks: list[Block] = field(default_factory=list) 
    exits: list[Block] = field(default_factory=list) 
    llvm_exits: list[llvm.ValueRef] = field(default_factory=list) 
    entry_temps: list[Temp] = field(default_factory=list) 
    resulted_temps: list[Temp] = field(default_factory=list) 
    exit_temps: list[Temp] = field(default_factory=list) 
    ir: list[IR] = field(default_factory=list) 
    mir: list[MIR] = field(default_factory=list) 
    has_succesors = True

    def get_ir(self):
        return "\n".join(ir.pretty_ir() for ir in self.ir)
    def get_mir(self):
        return "\n".join(mir.pretty_mir() for mir in self.mir)
    
    def trace(self) -> dict:
        return _trace_kv(
            id=self.id,
            preceding=[b.id for b in self.entering_blocks],
            exits=[b.id for b in self.exits],
            entry_temps=_trace_list(self.entry_temps),
            resulted_temps=_trace_list(self.resulted_temps),
            exit_temps=_trace_list(self.exit_temps),
            ir=[i.pretty_ir() for i in self.ir],
            mir=[m.pretty_mir() for m in self.mir],
        )

    def __repr__(self) -> str:
        return (
            f"Block({self.id}, "
            f"pred={[b.id for b in self.entering_blocks]}, "
            f"succ={[b.id for b in self.exits]}, "
            f"ir={self.get_ir()},"
            f"mir={self.get_mir()})"
        )


class IR:
    def __init__(self, llvm_obj: llvm.ValueRef, inp, out, args, type = None) -> None:
        assert llvm_obj.is_instruction, "tried creating a inst with a non inst valueref"
        self.llvm_obj = llvm_obj
        self.name: str = llvm_obj.opcode # pyright: ignore[reportAttributeAccessIssue]
        self.inputs:  list[Temp] = inp
        self.output: Temp | None = out
        self.args: list[str] = args
        self.type: str | None = type

    def pretty_ir(self):
        ins = ", ".join(f"%{t.trace_id}" for t in self.inputs)
        if self.args: ins += ", ".join(t for t in self.args)
        if self.type: ins += f"     # {self.type}"
        return f"{f'%{self.output.trace_id} = ' if self.output else ''}{self.name} {ins}"

    def __repr__(self) -> str:
        return self.pretty_ir()


@dataclass
class MIR:
    name: str = ""
    args: list[str] = field(default_factory=list)
    definition: list[str] = field(default_factory=list) 
    inputs: list[list[str]] = field(default_factory=list) 
    output: list[str] = field(default_factory=list) 
    inouts: list[list[str]] = field(default_factory=list) 
    spills: list[int] = field(default_factory=list)
    type: str | None = None

    def pretty_mir(self):
        inp = ", ".join(" + ".join(inp) for inp in self.inputs)
        if self.args: inp += ", ".join(t for t in self.args)
        if self.type: inp += f"     # {self.type}"
        out = " + ".join(self.output) + " = " if self.output else ""
        return f"{out}{self.name} {inp}"

    def __repr__(self) -> str:
        return (
            f"MIR({self.name}, "
            f"in={len(self.inputs)}, "
            f"out={len(self.output)}, "
            f"inout={len(self.inouts)}, "
            f"spills={self.spills})"
        )


class Tracer:
    def __init__(self, enabled):
        self.enabled = enabled
        self.events = []

    def emit(self, event):
        if self.enabled:
            self.events.append(event)

    def __repr__(self) -> str:
        return "\n".join(map(str, self.events))

    def trace(self) -> list:
        return list(self.events)
