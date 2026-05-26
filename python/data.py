
# pointers not included
# pointers are annotated with "*" OR
# named with ptr
DATA_TYPES: dict[str, int | None] = {
    # floating-point
    "half": 16,
    "float": 32,
    "double": 64,
    "fp128": 128,
    "x86_fp80": 80,
    "ppc_fp128": 128,

    # typeless / non-sized
    "void": None,
    "label": None,
    "metadata": None,
    "token": None,

    # general pointer type, all pointers will be the size of the addr width.
    "ptr": None
}

LLVM_BLOCK_GENERATING_INSTS = [
    "br",          # unconditional or conditional branch
    "cond_br",     # alias sometimes used for conditional branch
    "switch",      # multi-way branch
    "indirectbr",  # branch to computed address
    "invoke",      # function call with normal/unwind destinations
    "callbr",      # call with multiple destinations
    "ret",         # return from function (ends block)
    "resume",      # resumes unwinding in exception handling
    "catchswitch", # exception handling, can branch to multiple handlers
    "catchret",    # branch to catch handler
    "unreachable", # marks code that is not reachable
]

LLVM_INSTS = {
    # Terminators
    "ret": 0,
    "br": 0,
    "switch": 0,
    "indirectbr": 0,
    "call": None,
    "callbr": None,
    "invoke": None,       
    "resume": 0,
    "unreachable": 0,
    "cleanupret": 0,
    "catchret": 0,
    "catchswitch": 0,

    # Arithmetic (integer & floating)
    "add": 1, "fadd": 1, "sub": 1, "fsub": 1, "mul": 1, "fmul": 1,
    "udiv": 1, "sdiv": 1, "fdiv": 1, "urem": 1, "srem": 1, "frem": 1,

    # Bitwise/logical
    "shl": 1, "lshr": 1, "ashr": 1, "and": 1, "or": 1, "xor": 1,

    # Memory
    "alloca": 1,
    "load": 1,
    "store": 0,
    "fence": 0,
    "cmpxchg": 1,      # returns {old, success} struct
    "atomicrmw": 1,
    "getelementptr": 1,

    # Casts and Conversions
    "trunc": 1, "zext": 1, "sext": 1, "fptrunc": 1, "fpext": 1,
    "fptoui": 1, "fptosi": 1, "uitofp": 1, "sitofp": 1,
    "ptrtoint": 1, "inttoptr": 1, "bitcast": 1, "addrspacecast": 1,

    # Comparisons
    "icmp": 1,
    "fcmp": 1,

    # Vector operations
    "extractelement": 1, "insertelement": 1, "shufflevector": 1,

    # Aggregate operations
    "extractvalue": 1, "insertvalue": 1,

    # Misc
    "phi": 1,
    "select": 1,
    "va_arg": 1,
    "landingpad": 1,
}

LLVM_CALLS = [
    "call",
    "invoke",
    "callbr"
]

LLVM_BUILTINS = {
    "llvm.memcpy": 0,
    "llvm.memmove": 0,
    "llvm.memset": 0,
    "llvm.va_start": 0,
    "llvm.va_end": 0,
    "llvm.va_copy": 0,
    "llvm.sqrt": 1,
    "llvm.sin": 1,
    "llvm.cos": 1,
    "llvm.exp": 1,
    "llvm.log": 1,
    "llvm.pow": 1,
    "llvm.fma": 1,
    "llvm.ffloor": 1,
    "llvm.fceil": 1,
    "llvm.ftrunc": 1,
    "llvm.frint": 1,
    "llvm.shufflevector": 1,
    "llvm.x86.sse.add.ps": 1,
    "llvm.x86.sse.sub.ps": 1,
    "llvm.x86.avx.mul.pd": 1,
    "llvm.atomic.load": 1,
    "llvm.atomic.store": 0,
    "llvm.atomic.cmpxchg": 1,
    "llvm.atomic.rmw": 1,
    "llvm.ctpop": 1,
    "llvm.ctlz": 1,
    "llvm.cttz": 1,
    "llvm.sadd.with.overflow": 1,
    "llvm.uadd.with.overflow": 1,
    "llvm.smul.with.overflow": 1,
    "llvm.umul.with.overflow": 1,
    "llvm.trap": 0,
    "llvm.expect": 0,
    "llvm.prefetch": 0,
    "llvm.assume": 0,
    "llvm.dbg.declare": 0,
    "llvm.dbg.value": 0,
}



ISA_KEYS = {
    "opcodes": ("opcodes", "instructions", "insts"),
    "syntax": (
        "syntax", "instruction syntax", "cpu syntax",
        "instruction_syntax", "cpu_syntax",
    ),
    "encoding": (
        "encoding", "instruction encodings", "encodings",
        "instruction_encodings",
    ),
    "hardware": (
        "hardware", "cpu config", "arch config",
        "cpu_config", "arch_config",
    ),
    "pseudo": (
        "pseudo instructions", "pseudo", "pseudo inst", "pseudo insts",
        "pseudo_instructions", "pseudo_inst", "pseudo_insts",
    ),
    "syntax temp": (
        "syntax temp", "syntax templates", "syn templates",
        "syntax_templates", "syn_templates",
    ),
    "encoding temp": (
        "encoding temp", "encoding templates", "enc templates",
        "encodings templates", "enc_templates", "encoding_templates",
        "encodings_templates", "enc temp", "enc_temp",
    ),
    "translation table": (
        "instruction_map", "instruction table",
        "translation table", "inst translation", "t table",
    ),
    "inst spills": (
        "spills", "instruction spills", "spill table", "spill map", "inst_spills",
        "inst spills", "spill_instructions", "spill", "instruction spill", "spill table", "spill map",
        "inst_spill", "spill_insts"
        ),
    "op types": (
        "op types", "operand types", "op_types", "operand_types",
    ),
}

HARDWARE_KEYS = {
    "endianness": (
        "endianness", "byte order", "byte_order", 
        "memory order", "memory_order", "endian", "endianess"
    ),
    "data types": ("data types", "d types", "d type regs"),
    "stack start": (
        "stack start", "stack start address", "stack base",
        "stack base address", "stack bottom", "stack bottom address",
        "stack low", "stack low address", "stack min"
    ),

    "stack end": (
        "stack end", "stack end address", "stack limit",
        "stack limit address", "stack top", "stack top address",
        "stack high", "stack high address", "stack max"
    ),

    "regs": (
        "reg file size", "register file size",
        "reg_file_size", "register_file_size",
        "reg_file", "register_file",
        "num registers", "num_regs",
        "rf size", "rf_size",
        "regs", "registers", "reg file",
    ),
    "spec regs": (
        "special registers", "spec_regs",
        "special_registers", "spec regs", "special regs",
    ),
    "address width": (
        "address width", "addr width",
        "address_bits", "addr_bits",
        "address size", "addr_size",
    ),
    "data width": (
        "data width", "data_width",
        "data bits", "data_bits",
        "data size", "data_size",
    ),
    "reg width": (
        "reg width", "register width",
        "reg_width", "register_width",
        "reg bits", "register bits",
        "reg_bitwidth", "register_bitwidth",
        "reg size", "register size",
        "reg_size", "register_size",
    ),
    "opcode size": (
        "instruction length", "instruction size",
        "opcode width", "opcode len", "len opcode",
    ),
}


DEFAULT_OP_TYPES = {
    "relative address": {
            "aliases": ["rel addr", "relative address", "rel_addr", "relative_address"],
            "re": "\\%([+-]?(?:0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\\d+))",
            "size": 16,
            "convertable": True,
            "can be evaluated": True
        },
    "value": {
            "aliases": ["val", "value"],
            "re": "([+-]?(?:0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\\d+))",
            "size": 16,
            "convertable": True,
            "can be evaluated": True
        },
    "address": {
            "aliases": ["addr", "address"],
            "re": "\\$([+-]?(?:0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\\d+))",
            "size": 16,
            "convertable": True,
            "can be evaluated": True
        },
    "variable": {"aliases": ["var", "variable"], "re": "(\\w+)", "convertable": False, "can be evaulated": False}, 

}

dir_op_types = {
        "value": {
            "aliases": ["val", "value"],
            "re": "([+-]?(?:0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\\d+))",
            "size": 16,
            "convertable": True,
            "can be evaluated": True
        },
        "address": {
            "aliases": ["addr", "address"],
            "re": "\\$([+-]?(?:0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|\\d+))",
            "size": 16,
            "convertable": True,             
            "can be evaluated": True
        },
        "file": {
            "aliases": ["file", "filename"],
            "re": r'["\']?((?:[a-zA-Z]:)?(?:[/\\]\w+|\w+[/\\])*\w+\.\w+)["\']?',
            "convertable": False,
            "can be evaluated": False
        },
        "variable": {"aliases": ["var", "variable"], "re": "(\\w+)", "convertable": False, "can be evaulated": True},
}

STAGES = {0: "loading and checking isa", 1: "making blocks", 2: "expanding pseudo and defining vars", 3: "addressing lines, includes and imports", 4: "processing includes", 5: "evaluating expressions", 6: "parsing nums", 7: "parsing instructions and assembling encoding", 8: "doing final checks and saving file"}

DIR_SYNTAX = {".virt_sect": ["val"], ".virt_end": [], ".raw": ["file"], ".import": ["file"], ".reserv": ["val"], ".def": ["variable", "operand"], ".num": ["value"], ".org": ["address"], ".include": ["file"]}
