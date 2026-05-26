import json, re, sys, math
import utils as ut
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import data 
from llvmlite import binding as llvm
from llvmlite import ir as llvm_ir

llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

required_isa_keys = ("hardware", "translation table", "inst spills")
required_hw_keys =  ("endianness", "data types", "regs", "address width", "data width", "reg width")

class Compiler:
    def __init__(self, show_warnings, trace) -> None:
        self.show_warnings = show_warnings
        self.translated_code = []   # list of lines
        self.trace = trace
        self.tracer = ut.Tracer(self.trace)
        self.label_nums = {}   
        self.isa: dict = {}
        self.hardware: dict = {}
        self.global_vars: dict[str, list[int]] = {}   # for emiting globals later

    def run(self, program_file: Path | None, isa_file: Path, output_file: Path):
        self.current_file = isa_file
        with open(isa_file, "r", encoding="utf-8") as f:
            try:
                isa = json.load(f)
            except json.decoder.JSONDecodeError as e:
                ut.error(self, f"error whilst loading json '{str(e)}'"); exit(1) # for pylance

        self.isa, self.hardware = self.load_isa(isa)
        
        regs = set(self.hardware["regs"]) - set(self.hardware.get("spec regs", []))
        def sort_key(r):
            m = re.match(r"([a-zA-Z]+)(\d+)$", r)
            if m:
                prefix, num = m.groups()
                return (prefix, int(num))
            return (r, 0)
        self.gprs = sorted(regs, key=sort_key)
        
        llvm_src = program_file
        if isinstance(program_file, Path):
            llvm_src = program_file.read_text("utf-8")  

        self.module = llvm.parse_assembly(llvm_src)

        funcs: list[ut.Func] = self.extract_funcs(self.module)
        
        self.tracer.emit({"extracted the llvm ir data out of the llvmlite module.": [func.trace() for func in funcs]})
        
        #for func in funcs:
        #    self.def_call_temps(func)
        
        trace_file = output_file.with_suffix(".json")
        with open(trace_file, "w") as f: json.dumps(self.tracer.events)
    
        pass

    
    def extract_funcs(self, module: llvm.ModuleRef):
        def create_temp(llvm_obj: llvm.ValueRef, parent = None):
                nonlocal temp_i
                new_t = ut.Temp(llvm_obj, llvm_obj.type, temp_i, self.get_bitwidth(llvm_obj), parent)
                self.made_temps[llvm_obj] = new_t
                temp_i += 1
                return new_t
            
        def flatten_llvm_type_to_temps(temp_type: llvm.TypeRef, temp: llvm.ValueRef, parent = None):
            nonlocal temp_i
            if temp not in self.made_temps:
                new_t = create_temp(temp, parent)
                if temp_type.is_array or temp_type.is_struct or temp_type.is_vector:
                    children = []
                    for elem in temp_type.elements:
                        children.append(flatten_llvm_type_to_temps(elem, temp, new_t))
                    new_t.children = children
            else:
                new_t = self.made_temps[temp]
            
            return new_t
        
        def link_blocks(blocks: list[ut.Block]):
            for block in blocks:
                for i, exit_b_ref in enumerate(block.llvm_exits):
                    if exit_b_ref.is_block:
                        exit_block = block_by_llvm[exit_b_ref]
                        block.exits[i] = exit_block
                        exit_block.entering_blocks.append(block)
                    else: raise RuntimeError(f"exit '{exit_b_ref.name}' isn't a block")

        def replace_labels(blocks: list[ut.Block]):
            # map LLVM basic blocks → our Block object
            for block in blocks:
                for inst in block.ir:

                    # clean up PHI inputs that come from dead predecessors
                    if inst.name == "phi":
                        new_inputs = []
                        new_args = []

                        for temp, block_ref in zip(inst.inputs, inst.args):
                            assert isinstance(block_ref, llvm.ValueRef), "phi expects block valueref"
                            target = block_by_llvm[block_ref]
                            if target.has_succesors:
                                new_inputs.append(temp)
                                new_args.append(f"label{target.id}")

                        inst.inputs = new_inputs
                        inst.args = new_args
                        continue

                    # replace block refs with label strings
                    for i, arg in enumerate(inst.args):
                        if isinstance(arg, llvm.ValueRef) and arg.is_block:
                            target = block_by_llvm[arg]
                            inst.args[i] = f"label{target.id}"

        def handle_branch(inst: llvm.ValueRef):
            # TODO handle branches, i need to record each target
            operands = tuple(inst.operands)
            inputs, args = [], []
            type = None
            
            inst.is_instruction
    

            if inst.opcode == "br":
                if len(operands) == 1:
                    # unconditional
                    type = "unconditional"
                    target = operands[0]

                    new_b.llvm_exits.append(target)
                    args.append(target)

                elif len(operands) == 3:
                    # conditional
                    type = "conditional"

                    cond, true_bb, false_bb = operands

                    inputs.append(cond)
        
                    new_b.llvm_exits += (true_bb, false_bb)

                    args.append(true_bb)

                else:
                    raise RuntimeError(f"Malformed br with operands: {operands}")

            elif inst.opcode == "switch":
                # [0] → selector value
                # [1] → BasicBlockRef (default)
                # [2] → case value 0
                # ...
                inputs.append(operands[0])
                # default target
                args.append(operands[1])  
                new_b.llvm_exits.append(operands[1])
                ops = operands[2:]
                assert len(ops) % 2 == 0, "malformed switch operands"
                for block_ref, case_val in zip(ops[0::2], ops[1::2]):
                    args += (block_ref, case_val)
                    new_b.llvm_exits.append(block_ref)
            
            elif inst.opcode == "indirectbr":
                # Jump to computed address. the blocks in operands are the only valid locs.
                inputs.append(operands[0])
                new_b.llvm_exits += operands[1:]

            elif inst.opcode == "invoke":
                # call that handles exceptions
                # works like a 'if exception else ...' after returning from func
                args.append(operands[0])  # target func
                inputs += operands[1:-2]  # call args
                new_b.llvm_exits += operands[-2:]  # block if exception and else block
                args += operands[-2:]
            
            elif inst.opcode == "callbr":
                # normal call but can return to multiple places, first block is the normal return.
                args.append(operands[0])   # target func
                for op in operands[1:]:
                    if op.is_block:
                        new_b.llvm_exits.append(op)
                    else:
                        inputs.append(op)
            
            elif inst.opcode in ("unreachable", "ret"): new_b.has_succesors = False
            # TODO handle 'resume' inst

            return type, inputs, args
                    
        def make_new_inst(inst: llvm.ValueRef, inputs: list[llvm.ValueRef] | tuple[llvm.ValueRef, ...], raw_args: list[llvm.ValueRef], type: str | None = None):
            # TODO handle args
            args = []
            for arg in raw_args:   # args are constant litteral values or labels (labels handled later) NOT ssa temps of any kind
                if arg.is_constant:   
                    args.append(str(arg.get_constant_value()))
                else:
                    args.append(arg)

            new_inputs = []
            for input in inputs:
                new_inputs.append(flatten_llvm_type_to_temps(input.type, input))

            # NOTE: inst is both the output AND the instruction
            if str(inst.type) != "void":
                output = flatten_llvm_type_to_temps(inst.type, inst)
            else:
                output = None
            new_b.ir.append(ut.IR(inst, new_inputs, output, args, type))


        self.made_temps: dict[llvm.ValueRef, ut.Temp] = {}
        block_i = temp_i = 0
        funcs: list[ut.Func] = []
        for func in module.functions:
            new_f = ut.Func(func, self.gprs.copy())
            
            for param in func.arguments:
                new_f.params.append((create_temp(param), self.def_func_arg(param, new_f, new_f.free_regs)))

            # get the returned temp if any
            if tuple(func.blocks) and tuple(tuple(func.blocks)[-1].instructions) and tuple(tuple(tuple(func.blocks)[-1].instructions)[-1].operands): 
                result = tuple(tuple(tuple(func.blocks)[-1].instructions)[-1].operands)[0]
                new_f.result = (create_temp(result), self.def_func_arg(result, new_f, self.gprs.copy()))
                
            funcs.append(new_f)

        for new_f, func in zip(funcs, module.functions):
            for block in func.blocks:
                new_b = ut.Block(block, block_i)
                insts = tuple(block.instructions)
                for inst in insts[:-1]:
                    args = []
                    type = None
                    operands = tuple(inst.operands)
                    inputs = []
                    if inst.opcode == "call":
                        if operands[0].is_function:
                            type = "direct"
                            inputs = operands[1:]
                        else:
                            type = "indirect"
                            inputs = operands

                    elif inst.opcode == "alloca": 
                        if operands:
                            if operands[0].is_constant:
                                type = "static"
                                args.append(operands[0])
                            else:
                                type = "dynamic"
                                inputs = operands

                    elif inst.opcode == "phi": 
                        # only parsing here, i need all blocks defined before i can do further handling
                        # only needed with optimazation -o1+
                        # NOTE: can violate your intuition. Keep this in mind when weird PHI bugs appear.
                        assert len(operands) % 2 == 0, "malformed phi operands"
                        ops = operands
                        args = list(inst.incoming_blocks)
                        inputs = ops[0::2]

                    else:
                        inputs = operands
                        
                    make_new_inst(inst, inputs, args, type)
                
                ty, inp, args = handle_branch(insts[-1])
                make_new_inst(insts[-1], inp, args, ty)

                new_f.blocks.append(new_b)
                block_i += 1
                
        block_by_llvm: dict[llvm.ValueRef, ut.Block] = {}
        for func in funcs:
            for b in func.blocks:
                assert b.llvm_obj.is_block, "block llvm obj must be a block"
                block_by_llvm[b.llvm_obj] = b 
        
        for func in funcs:
            link_blocks(func.blocks)
            replace_labels(func.blocks)
        return funcs


    def get_bitwidth(self, item: llvm.ValueRef, width = 0):
        potiential_width = self.hardware["address width"] if item.type.is_pointer else item.type.type_width
        if not potiential_width:
            if item.type.is_array or item.type.is_struct or item.type.is_vector:
                for elem in item.operands:
                    width = self.get_bitwidth(elem, width)
        else: 
            width += potiential_width
        return width
    

    def def_func_arg(self, arg: llvm.ValueRef, func: ut.Func, free_regs: list):
        """A func arg be a param or result, must be entirely in registers or entirely on stack.
        Registers are preferred if enough are available."""

        type_size = self.hardware["data types"].get(str(arg.type))
        if type_size is None:
            ut.error(self, f"data type '{str(arg.type)}' wasn't found in isa, trying to calculate amt regs/stack slots.", str(self.hardware["data types"]), fatal_error=False)
            type_width = self.get_bitwidth(arg)
            if type_width is None:
                ut.error(self, f"couldn't calculate data type '{str(arg.type)}' bit width.")
            amt_regs  = math.ceil(type_width / self.hardware["reg width"])
            amt_slots = math.ceil(type_width / self.hardware["data width"])
        else:
            amt_regs = type_size["reg"]
            amt_slots = type_size["stack"]

        locs = []
        if len(free_regs) >= amt_regs:
            locs = [free_regs.pop() for _ in range(amt_regs)]
        else:
            while amt_slots:
                locs.append(func.stack_offset)
                func.stack_offset += 1
                amt_slots -= 1

        return locs


    def def_call_temps(self, func: ut.Func):
        for block in func.blocks:
            for inst in block.ir:
                if inst.name in data.LLVM_CALLS:
                    ...


    def load_isa(self, raw_isa):
        isa = {}
        # --- Normalize ISA keys using data.ISA_KEYS ---
        for token, aliases in data.ISA_KEYS.items():
            for alias in aliases:
                if alias in raw_isa:
                    isa[token] = raw_isa[alias]
                    break
            else:
                if token in required_isa_keys:
                    ut.error(self, f"Missing required isa key '{token}'")

        # --- Normalize hardware subkeys ---
        hw_raw = isa.get("hardware", {})
        hardware = {}
        for token, aliases in data.HARDWARE_KEYS.items():
            for alias in aliases:
                if alias in hw_raw:
                    hardware[token] = hw_raw[alias]
                    break
            else:
                if token in required_hw_keys:
                    ut.error(self, f"Missing required hardware key '{token}'")

        isa["hardware"] = hardware

        if isinstance(hardware["regs"], int):
            hardware["regs"] = [f"r{i}" for i in range(hardware["regs"])]

        # --- data types validation ---
        data_types: dict = hardware["data types"]
        for type, val in data_types.items():
            if not re.match(r"i\d+", type) and type not in data.DATA_TYPES:
                ut.error(self, f"the data type '{type}' is unknown.", str(data_types))
            if not isinstance(val, dict):
                ut.error(self, f"the value of data type '{type}' should be a dict.", str(data_types))
            
            amt_regs =  val.get("reg")
            amt_slots = val.get("stack")
            if amt_regs is None or amt_slots is None:
                ut.error(self, f"the data type '{type}' doesn't have a '{'stack' if amt_slots is None else 'reg'}' value defined.", str(val))
            if not isinstance(amt_regs, int):
                ut.error(self, f"the reg value of data type '{type}' needs to be a integer", str(val), str(amt_regs))
            if not isinstance(amt_slots, int):
                ut.error(self, f"the stack value of data type '{type}' needs to be a integer", str(val), str(amt_slots))

        # --- Translation table validation ---
        t_table = isa.get("translation table", {})
        if not isinstance(t_table, dict):
            ut.error(self, "'translation table' must be a dictionary")

        for instr, translations in t_table.items():
            if not isinstance(instr, str):
                ut.error(self, "instruction names in 'translation table' must be strings")

            if isinstance(translations, list):
                # flat translation list
                if not all(isinstance(line, str) for line in translations):
                    ut.error(self, f"All lines in translation list for '{instr}' must be strings")
            elif isinstance(translations, dict):
                # subtable by type (e.g., stack/reg)
                for subkey, sublines in translations.items():
                    if not isinstance(sublines, list):
                        ut.error(self, 
                            f"subtable '{subkey}' for instruction '{instr}' must be a list"
                        )
                    if not all(isinstance(line, str) for line in sublines):
                        ut.error(self, 
                            f"All lines in subtable '{subkey}' for '{instr}' must be strings"
                        )
            else:
                ut.error(self, f"translation entry for '{instr}' must be a list or dict")

        # --- op reg count validation ---
        op_reg_count = isa.get("op reg count", {})
        if not isinstance(op_reg_count, dict):
            ut.error(self, "'op reg count' must be a dictionary")

        for instr, counts in op_reg_count.items():
            if not isinstance(instr, str):
                ut.error(self, "instruction names in 'op reg count' must be strings")

            if not isinstance(counts, dict):
                ut.error(self, f"'op reg count' for '{instr}' must be a dict")

            for port, width in counts.items():
                if not isinstance(port, str):
                    ut.error(self, f"invalid port name in 'op reg count' for '{instr}'")

                if not re.fullmatch(r"(in|out)\d+", port):
                    ut.error(self, 
                        f"invalid port '{port}' in 'op reg count' for '{instr}' "
                        "(expected inN / outN)"
                    )

                if not isinstance(width, int) or width <= 0:
                    ut.error(self, 
                        f"register count for '{instr}:{port}' must be a positive integer"
                    )

        return isa, isa["hardware"]

