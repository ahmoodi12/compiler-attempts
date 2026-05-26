import json
from pathlib import Path
import re
from utils import *

required_isa_keys = ("data types", "hardware", "syntax", "translation table", "inst spills")
required_hw_keys =  ("regs", "address width", "data width", "reg width")

class Compiler:
    def __init__(self, show_warnings, trace) -> None:
        self.show_warnings = show_warnings
        self.translated_code = []   # list of lines
        self.trace = trace
        self.tracer = Tracer(self.trace)
        self.label_nums = {}   
        self.isa, self.hardware = {}, {}
        
    def init_vars(self):
        self.id = 0
        self.global_vars = {}
        self.op_reg_count_cache = {}
        self.tables: dict[str, Table] = {}
        self.types = {}
        self.imported_funcs: list = []
        self.funcs: list[Func] = []
        self.stack_pointer = self.hardware.get("stack end")


    def run(self, program: Path, isa_file: Path, output_file: Path, wat_src):
        import frontend as FE
        import controll_flow as CFP
        import allocation as ALLOC
        import translation as TRANS

        self.current_file = isa_file
        with open(isa_file, "r", encoding="utf-8") as f:
            isa = json.load(f)

        self.isa, self.hardware = self.load_isa(isa)
        self.gprs = list(set(self.hardware["regs"]) - set(self.hardware.get("spec regs", [])))

        if program.suffix == ".wat":
            self.current_file = program
            wat_src = program.read_text()

        parser = FE.WatParser(self)
        frontend = FE.Frontend(self)
        controll_flow = CFP.ControlFlowPipeline(self)
        allocation = ALLOC.Allocator(self)
        translation = TRANS.translator(self)

        asts = parser.parse(wat_src)   # now you have a full WAT AST
        
        for ast in asts:
            self.init_vars()

            frontend.walk_node(ast, None) # type: ignore
            frontend.cut_globals()
            self.tracer.emit({"generated": {"funcs": [f.trace() for f in self.funcs], "globals": self.global_vars}})

            for func in self.funcs:
                ir = frontend.generate_IR(func)
                if not ir: 
                    self.tracer.emit({f"{func.name}: func empty, skipping steps.": {"ir": format_IR(ir)}})
                    continue
                self.tracer.emit({f"{func.name}: generated": {"ir": format_IR(ir)}})
                frontend.assign_types__convert_floats(ir, func)
                self.tracer.emit({f"{func.name}: lowered local insts, assigned types": {"ir": format_IR(ir), "params": func.type.params, "locals": func.locals}})
                controll_flow.make_code_blocks(ir, func)
                self.tracer.emit({f"{func.name}: generated func_main_block": {"func_main_block": func.block.trace(1)}})
                controll_flow.label_branches__make_cf_blocks(func.block, func)
                self.tracer.emit({f"{func.name}: converted branch targets to labels, resolved 'if' and made controll flow blocks": {"func_main_block": func.block.trace(1)}})
                controll_flow.assign_temp_vars(func.CF[0], func) 
                self.tracer.emit({f"{func.name}: asigned temporary vals to ir": {"func_main_block": func.block.trace(1)}})
                controll_flow.resolve_merge_nodes(func.block)
                self.tracer.emit({f"{func.name}: ressolved merge nodes into moves.": {"func_main_block": func.block.trace(1)}})
                allocation.def_call_temps(func.block, func)
                self.tracer.emit({f"{func.name}: defined call instructions temp vals to params and results": func.block.trace(1)})
                allocation.def_temps(func.block, func)
                self.tracer.emit({f"{func.name}: defined temp vals": {"func_main_block": func.block.trace(0)}})
                translation.translate(func.block, func)
                self.tracer.emit({f"{func.name}: translated ir into mir": {"func_main_block": func.block.trace(0)}})
                translation.emit_blocks(func.block)
                self.translated_code += [""*2]

                if self.trace:
                    with open(str(output_file.with_suffix("")) + "_trace.json", "w") as f:
                        json.dump(self.tracer.events, f)
            frontend.emit_data()

        with open(output_file, "w") as f:
            f.write("\n".join(self.translated_code))
        

        pass


    def load_isa(self, raw_isa):
        isa = {}
        # --- Normalize ISA keys using ISA_KEYS ---
        for token, aliases in ISA_KEYS.items():
            for alias in aliases:
                if alias in raw_isa:
                    isa[token] = raw_isa[alias]
                    break
            else:
                if token in required_isa_keys:
                    error(self, f"Missing required isa key '{token}'")

        # --- Normalize hardware subkeys ---
        hw_raw = isa.get("hardware", {})
        hardware = {}
        for token, aliases in HARDWARE_KEYS.items():
            for alias in aliases:
                if alias in hw_raw:
                    hardware[token] = hw_raw[alias]
                    break
            else:
                if token in required_hw_keys:
                    error(self, f"Missing required hardware key '{token}'")

        isa["hardware"] = hardware

        if isinstance(hardware["regs"], int):
            hardware["regs"] = [f"r{i}" for i in range(hardware["regs"])]

        # --- Syntax validation ---
        syntax = isa.get("syntax", {})
        if not isinstance(syntax, dict):
            error(self, "Syntax must be a dictionary")
        for instr, ops in syntax.items():
            if not isinstance(ops, str) and not isinstance(ops, list):
                error(self, f"Syntax for '{instr}' must be a string or list of strings")
            if isinstance(ops, list):
                if not all(isinstance(op, str) for op in ops):
                    error(self, f"All elements in syntax list for '{instr}' must be strings")

        # --- Translation table validation ---
        t_table = isa.get("translation table", {})
        if not isinstance(t_table, dict):
            error(self, "'translation table' must be a dictionary")

        for instr, translations in t_table.items():
            if not isinstance(instr, str):
                error(self, "instruction names in 'translation table' must be strings")

            if isinstance(translations, list):
                # flat translation list
                if not all(isinstance(line, str) for line in translations):
                    error(self, f"All lines in translation list for '{instr}' must be strings")
            elif isinstance(translations, dict):
                # subtable by type (e.g., stack/reg)
                for subkey, sublines in translations.items():
                    if not isinstance(sublines, list):
                        error(self, 
                            f"subtable '{subkey}' for instruction '{instr}' must be a list"
                        )
                    if not all(isinstance(line, str) for line in sublines):
                        error(self, 
                            f"All lines in subtable '{subkey}' for '{instr}' must be strings"
                        )
            else:
                error(self, f"translation entry for '{instr}' must be a list or dict")

        # --- op reg count validation ---
        op_reg_count = isa.get("op reg count", {})
        if not isinstance(op_reg_count, dict):
            error(self, "'op reg count' must be a dictionary")

        for instr, counts in op_reg_count.items():
            if not isinstance(instr, str):
                error(self, "instruction names in 'op reg count' must be strings")

            if not isinstance(counts, dict):
                error(self, f"'op reg count' for '{instr}' must be a dict")

            if instr not in WASM_INSTRUCTIONS and instr not in CUSTOM_INSTS:
                error(self, f"'op reg count' refers to unknown instruction '{instr}'")

            for port, width in counts.items():
                if not isinstance(port, str):
                    error(self, f"invalid port name in 'op reg count' for '{instr}'")

                if not re.fullmatch(r"(in|out)\d+", port):
                    error(self, 
                        f"invalid port '{port}' in 'op reg count' for '{instr}' "
                        "(expected inN / outN)"
                    )

                if not isinstance(width, int) or width <= 0:
                    error(self, 
                        f"register count for '{instr}:{port}' must be a positive integer"
                    )

        return isa, isa["hardware"]

