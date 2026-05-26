from dataclasses import dataclass, field
from typing import Optional
from termcolor import colored
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from data import * 


def str_bytes_to_list(data: str, bits: int = 8):
    """
Converts a string into packed integers.
Assumes hex escapes (\\xx), little-endian packing.
Input is trusted compiler output.
"""

    size = bits // 8
    byte_i = curr_num = char_i = 0
    result: list[str] = []

    while char_i < len(data):
        char = data[char_i]
        if char == "\\":
            if char_i + 2 >= len(data):
                raise ValueError(f"Invalid escape at position {char_i} in {data}")
            curr_num += int(data[char_i+1:char_i+3], 16) << (byte_i*8)
            char_i += 3
        else:
            curr_num += ord(char) << (byte_i*8)
            char_i += 1
        byte_i += 1

        if byte_i == size:
            result.append(str(curr_num))
            curr_num = byte_i = 0

    # Append remaining bytes if not full
    if byte_i > 0:
        result.append(str(curr_num))

    return result

def format_IR(ir:   list["IR | str"]):
    return [inst.pretty_IR() if isinstance(inst, IR) else inst for inst in ir]
def format_MIR(Mir: list["MIR | str"]):
    return [inst.pretty_MIR() if isinstance(inst, MIR) else inst for inst in Mir]

def error(compiler, message: str, line_i: Optional[int] = None, line_content: Optional[str] = None, highlight: str = "", is_warning = False, fatal_error = True):
    # Skip warnings if disabled

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
    full_error = f"{formatted_level}{location}:\n{formatted_msg}\n"

    # Print line content with highlighting
    if line_content:
        full_error += "\n" + colored(line_content, (144,213,255))
        if highlight and (idx := line_content.find(highlight)) >= 0:
            full_error += "\n" + (" " * idx) + colored("^" * len(highlight), "red")

    print(full_error)
    if fatal_error: raise CompileError


class CompileError(Exception):
    pass


class Table:
    def __init__(self, index, min_size, max_size, type) -> None:
        self.index: str = index
        self.label: str = f"table{index}"
        self.min_size: int = min_size
        self.max_size: int | None = max_size
        self.type: str = type
        self.items: list = []


@dataclass
class FuncType:
    params:  list[tuple[str, list[int] | list[str]]] = field(default_factory=list)
    results: list[tuple[str, list[int] | list[str]]] = field(default_factory=list)
    free_regs: list = field(default_factory=list)
    stack_offset: int = 0   # this is used for param alloc, then becomes funcs default stack offset
    used_regs: dict = field(default_factory=dict)


class TempVar:
    def __init__(self, name: str, regs: list[str] | None = None, spills: list[int] | None = None):
        self.name = name
        self.regs = regs if regs is not None else []
        self.spills = spills if spills is not None else []
        self.last_use_id: int = -1

    def is_dead(self, current_id: int | None) -> bool:
        return current_id is not None and self.last_use_id == current_id 

    def __str__(self) -> str:
        return self.name
    
    def __repr__(self) -> str:
        return self.name

class Func:
    def __init__(self, name: str, type, node: "WatNode") -> None:
        self.name = name
        self.type: FuncType = type
        self.locals: list[tuple[str, list[int]]] = [] # locals are always in stack
        self.node = node
        self.body: list[str] = node.args[1:]
        self.indirect_calls_args: list[WatNode] = []
        self.block: CodeBlock = None # pyright: ignore[reportAttributeAccessIssue]
        self.CF: list[CF_block] = []
        self.temp_stack: list[TempVar] = []
        self.free_slots: list[int] = []
        self.stack_offset = self.type.stack_offset
        self.free_regs = self.type.free_regs.copy()
        self.calls: list[Func] = []  # like children, the funcs this func calls
        self.temps_defs: dict[str, TempVar] = {}   # temp name: temp
        self.alive_temps: list[TempVar] = []   # temp name: temp
        self.temp_counter = 0
        self.used_regs: dict[str, TempVar] =  {}
        self.regs_to_push = []   # all the regs we temporarly use

    def new_temp(self):
        self.temp_stack.append(TempVar(f"t{self.temp_counter}"))
        self.temp_counter += 1
        return self.temp_stack[-1]

    def get_next_temp(self):
        return TempVar(f"t{self.temp_counter}")

    def get_local(self, i) -> tuple[str, list[int]]:
        return (self.type.params + self.locals)[i]
    
    def __repr__(self) -> str:
        return (
            f"Func("
            f"name: {self.name!r}, "
            f"params:  {len(self.type.params)}, "
            f"results: {len(self.type.results)}, "
            f"locals: {len(self.locals)}, "
            f"temps: {self.temp_counter}, "
            f"stack_offset: {self.stack_offset}, "
            f"calls: {[f.name for f in self.calls]}"
            f")"
        )   

    def trace(self) -> dict:
        return {
            "name": self.name,
            "params":  len(self.type.params),
            "results": len(self.type.results),
            "locals": len(self.locals),
            "temps": self.temp_counter,
            "stack_offset": self.stack_offset,
            "calls": [f.name for f in self.calls],
        }


class CF_block:
    def __init__(self, block, label = None) -> None:
        self.entry_label: str | None = label
        self.is_branch = False
        self.IR: list[IR] = []
        self.entrys: list[CF_block] = []
        self.exits: list[CF_block] = []  # target_block, exit stack
        self.output_stack: list[TempVar] = []
        self.input_stack: list[TempVar] = []   # for move insts move insts will move input stack to output stack
        self.entry_stack: list[TempVar] = []
        self.code_block: CodeBlock = block  # where it comes from

    def __repr__(self) -> str:
        exits_labels = [exit_.entry_label for exit_ in self.exits]
        return (f"CF_block(label: {self.entry_label!r}, "
                f"IR: {self.IR}, "
                f"exits: {exits_labels})")

class CodeBlock:
    def __init__(self, name, parent) -> None:
        self.label: str = name
        self.parent = parent
        self.IR: list[IR | CodeBlock | str] = []
        self.else_label: str = ""   # only in if-else
        self.MIR: list[MIR | CodeBlock | str] = []
        self.children:list[CodeBlock] = []
        self.CF: list[CF_block] = []
        self.end_label: str  = ""

    def get_block(self, parent_i):
        parent = self
        while parent_i and parent:
            parent = parent.parent
            parent_i -= 1
        return parent

    def get_IR(self):
        out = []
        for line in self.IR:
            if isinstance(line, CodeBlock): out += line.get_IR()
            else: out.append(line)
        return out

    def get_MIR(self):
        out = []
        for line in self.MIR:
            if isinstance(line, CodeBlock): out += line.get_MIR()
            else: out.append(line)
        return out

    def __repr__(self) -> str:
        return (
            f"CodeBlock("
            f"label: {self.label!r}, "
            f"end_label: {self.end_label!r}, "
            f"else_label: {self.else_label!r}, "
            f"IR_len: {len(self.IR)}, "
            f"MIR_len: {len(self.MIR)}, "
            f"children: {[c.label for c in self.children]}, "
            f"parent: {getattr(self.parent, 'label', None)!r}, "
            f")"
        )

    def trace(self, ret_ir) -> dict:   # ir = true then print ir else mir
        if ret_ir:
            opt = []
            for inst in self.IR:
                if isinstance(inst, CodeBlock): opt.append(inst.trace(ret_ir))
                elif isinstance(inst, IR): opt.append(inst.pretty_IR())
                else: opt.append(inst)
        else:
            opt = []
            for inst in self.MIR:
                if isinstance(inst, CodeBlock): opt.append(inst.trace(ret_ir))
                elif isinstance(inst, MIR): opt.append(inst.pretty_MIR())
                else: opt.append(inst)
        opt_str = "ir" if ret_ir else "mir"
        return {
            "label": self.label,
            "end_label": self.end_label,
            "else_label": self.else_label,
            opt_str: opt
        }
    

# represents the wasm
@dataclass
class IR:
    name: str = ""
    args: list[str] = field(default_factory=list)
    inputs:  list[TempVar] = field(default_factory=list) 
    outputs: list[TempVar] = field(default_factory=list) 
    id: int | None = None
    type: str | None = None
    # only in calls
    called_func_type: FuncType | None = None
    input_spills:  dict[str, TempVar | None] = field(default_factory=dict) # input temp[i]: spilled temp if any
    output_spills: dict[str, TempVar | None] = field(default_factory=dict) # output temp[i]: spilled temp if any


    def pretty_IR(self) -> str:
        args = self.args

        lhs = ", ".join(out.name for out in self.outputs)
        if lhs: lhs += " = "
        rhs_inputs = ", ".join(inp.name for inp in self.inputs) 
        rhs_args = ", ".join(args)
        if rhs_inputs and args: rhs_args += ", "

        return f"{self.id}: {lhs}{self.name} {rhs_args}{rhs_inputs}" + ("   # " + self.type if self.type else "")

    def __repr__(self) -> str:
        return (
            f"IR("
            f"id: {self.id}, "
            f"name: {self.name!r}, "
            f"args: {self.args}, "
            f"inputs: {self.inputs}, "
            f"outputs: {self.outputs}, "
            f"type: {self.type}"
            f")"
        )

# represents the custom isa
@dataclass
class MIR:
    name: str = ""
    args: list[str] = field(default_factory=list)
    definition: list[str] = field(default_factory=list) 
    inputs: list[list[str]] = field(default_factory=list) 
    outputs: list[list[str]] = field(default_factory=list) 
    inouts: list[list[str]] = field(default_factory=list) 
    spills: list[int] = field(default_factory=list)
    ir: IR | None = None
    type: str | None = None


    def pretty_MIR(self) -> str:
        fmt_clusters = lambda clusters: ", ".join(" + ".join(cluster) for cluster in clusters)
                
        # Treat inouts as both inputs and outputs
        all_inputs = self.inputs + self.inouts
        all_outputs = self.outputs + self.inouts

        if lhs := fmt_clusters(all_outputs):
            lhs += " = "

        rhs_parts = []

        if self.args:
            rhs_parts.append(", ".join(self.args))

        if all_inputs:
            rhs_parts.append(fmt_clusters(all_inputs))

        rhs = ", ".join(rhs_parts)

        return f"{lhs}{self.name} {rhs}".rstrip() + ("   # " + self.type if self.type else "")

    def __repr__(self) -> str:
        return (
            f"MIR("
            f"name: {self.name!r}, "
            f"args: {self.args}, "
            f"inputs: {self.inputs}, "
            f"outputs: {self.outputs}, "
            f"inouts: {self.inouts}, "
            f"type: {self.type}"
            f")"
        )


class Tracer:
    def __init__(self, enabled):
        self.enabled = enabled
        self.events = []

    def emit(self, event):
        if self.enabled:
            self.events.append(event)

    def __repr__(self) -> str:
        return "\n".join(self.events)


class WatNode:
    def __init__(self, tag, args=None, children=None, parent=None):
        self.tag = tag
        self.args = args or []
        self.children: list["WatNode"] = children or []
        self.parent: WatNode | None = parent

    def __repr__(self):
        return f"(tag: {self.tag}, args: {self.args}, children: {self.children})"


