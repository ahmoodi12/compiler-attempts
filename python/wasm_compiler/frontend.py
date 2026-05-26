import math
import re
import struct
from utils import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from compiler import Compiler

class Frontend:
    def __init__(self, compiler: "Compiler") -> None:
        self.compiler = compiler

    def walk_node(self, node: "WatNode", current_func: Func, current_func_type: FuncType | None = None): 
        def get_type_op_amount(var_type):
            if (amt_loc := self.compiler.isa["data types"].get(var_type)) is None:
                error(self.compiler, f"the data type '{var_type}' isn't defined in data types.", fatal_error=False)
                amt_loc = math.ceil(DATA_TYPES[var_type]/self.compiler.hardware["reg width"]) # inst bit width / reg bit width
            return amt_loc

        if node.tag == "type" and not current_func:
            current_func_type = FuncType(free_regs=self.compiler.gprs.copy())
            self.compiler.types[node.children[0].tag.replace(";", "")] = current_func_type
                
        if node.tag == "table" and not current_func:
            table_i = node.children[0].tag.replace(";", "")
            self.compiler.tables[table_i] = Table(table_i, int(node.args[0]), (int(node.args[1]) if len(node.args) > 1 else None), node.args[-1])
            return  

        if node.tag == "elem":
            table = self.compiler.tables[node.children[0].tag.replace(";", "")]
            len_items = len(table.items)
            for i, func_name in enumerate(node.args[1:], ):
                if len_items <= i:
                    table.items.append(func_name)
                else:
                    table.items.insert(int(node.children[1].args[0]) + i, func_name)
            return

        if node.tag == "memory":
            return   # skip
    
        if node.tag == "global":
            if node.args[0] == "__stack_pointer" and not self.compiler.stack_pointer:
                self.compiler.stack_pointer = int(node.children[1].args[0])
            elif node.args[0] in DATA_TYPES:
                self.compiler.global_vars[node.children[0].tag.replace(";", "")] = int(node.children[1].args[0])  # var_i: int is ptr. var_i: (ptr, data[ptr:]) is defined vars
            return
    
        if node.tag == "export":
            name = node.args[0].replace('"', '')
            child = node.children[0]
            description = child.tag
            if description == "global" and child.args[0] in self.compiler.global_vars:
                self.compiler.global_vars[name] = self.compiler.global_vars[child.args[0]]
                self.compiler.global_vars.pop(child.args[0])
            return   
    
        if node.tag == "data":
            address = int(node.children[0].args[0])
            data: list[str] = str_bytes_to_list(" ".join(node.args[1:]).replace('"', ''))

            for var_type, var_ptr in self.compiler.global_vars.items():
                if isinstance(var_ptr, int) and (address + len(data) > var_ptr >= address):  
                    self.compiler.global_vars[var_type] = (var_ptr, data[var_ptr-address:])
            return
        
        # all func vars are in stack for simplicity
        if node.tag == "param" and current_func_type:
            for var_type in node.args:
                amt = get_type_op_amount(var_type)
                locations = []
                if amt <= len(current_func_type.free_regs)//4:
                    locations.extend(current_func_type.free_regs.pop() for _ in range(amt))
                else:
                    while amt:
                        locations.append(current_func.stack_offset)
                        current_func_type.stack_offset += 1
                        amt -= 1
                current_func_type.params.append((var_type, locations))
            return

        if node.tag == "local" and current_func:
            for var_type in node.args:
                amt = get_type_op_amount(var_type)
                var_locs = []
                while amt:
                    var_locs.append(current_func.type.stack_offset)
                    current_func.type.stack_offset += 1
                    amt -= 1
                current_func.locals.append((var_type, var_locs))
            return

        if node.tag == "result" and current_func_type:
            # use param regs as results aswell to minimize overwritten regs.
            param_regs = []
            for (_, param_locs) in current_func_type.params:
                param_regs += [r for r in param_locs if isinstance(r, str)]
                
            residual_regs = current_func_type.free_regs

            for var_type in node.args:
                amt = get_type_op_amount(var_type)
                results = []
                if amt <= len(param_regs + residual_regs):
                    results = (param_regs + residual_regs)[:amt]
                else:
                    while amt:
                        results.append(current_func_type.stack_offset)
                        current_func_type.stack_offset += 1
                        amt -= 1

                current_func_type.results.append((var_type, results))
            return
        
        if node.tag in ["import", "func"] and not current_func_type:
            if imported := (node.tag == "import"):
                node = node.children[0]
            current_func = Func(node.args[0], self.compiler.types[node.children[0].args[0]], node)
            if imported:
                self.compiler.imported_funcs.append(current_func)
            else:
                self.compiler.funcs.append(current_func)
        
        elif current_func:
            current_func.indirect_calls_args.append(node)

        for child in node.children:
            self.walk_node(child, current_func, current_func_type)


    def cut_globals(self):
        for var, var_data in self.compiler.global_vars.items():
            # asigns its value to the global vars pointing to it. the value is the bytes between this var and the closest next var

            if isinstance(var_data, tuple):  # if this var is pointing inside this vals addr range
                var_ptr = var_data[0]
                closest_next_var_ptr = None

                for next_var, next_var_data in self.compiler.global_vars.items():
                    if next_var == var: continue
                    if next_var_data == var_data:
                        self.compiler.global_vars[next_var] = var
                    if isinstance(next_var_data, tuple): next_var_ptr = next_var_data[0]  
                    elif isinstance(next_var_data, int): next_var_ptr = next_var_data
                    else: continue

                    if (var_ptr + len(var_data[1]) > next_var_ptr > var_ptr) and\
                       (closest_next_var_ptr is None or closest_next_var_ptr > next_var_ptr):
                        closest_next_var_ptr = next_var_ptr

                if closest_next_var_ptr is not None:
                    self.compiler.global_vars[var] = (var_ptr, var_data[1][:closest_next_var_ptr - var_ptr])


    def emit_data(self):
        for var, var_data in self.compiler.global_vars.items():
            if isinstance(var_data, tuple):
                self.compiler.translated_code.append(f".org ${var_data[0]}")
                self.compiler.translated_code.append(var + ":")
                for var2, var_data2 in self.compiler.global_vars.items():
                    if isinstance(var_data2, str) and var_data2 == var:
                        self.compiler.translated_code.append(var2 + ":")
                self.compiler.translated_code.append(".num " + ", ".join(var_data[1]))
                self.compiler.translated_code.append("")

        for table in self.compiler.tables.values():
            self.compiler.translated_code.append(table.label)
            self.compiler.translated_code.append(f".num {", ".join(table.items)}")


    def generate_IR(self, func: Func):
        current_inst = None
        next_args = 0
        parsed_wasm = []
        for token in func.body:
            if current_inst:
                if token.startswith("offset="):
                    current_inst.args = [token.split("=")[1]]
                elif re.match(r"[fi]\d+\.(?:load|store)", current_inst.name):
                    current_inst.args.append("0")   # offset
                elif not token.startswith("align=") and next_args is None or next_args > 0:
                    current_inst.args.append(token)
                    if next_args is not None: next_args -= 1

            if token in WASM_INSTRUCTIONS:
                next_args = WASM_INSTRUCTIONS[token][0]
                current_inst = IR(token)
                if token == "call_indirect":
                    if not func.indirect_calls_args: error(self.compiler, "call_indirect expects at least 1 arg")
                    current_inst.args.append(func.indirect_calls_args.pop(0).args[0])
                    table = "0"
                    if func.indirect_calls_args and func.indirect_calls_args[0].tag == "table":
                        table = func.indirect_calls_args.pop(0).args[0]
                    current_inst.args.append(table)

            if next_args is not None and next_args == 0 and current_inst:
                parsed_wasm.append(current_inst)
                current_inst = None
        return parsed_wasm


    def assign_types__convert_floats(self, ir: list[IR], func: Func):
        for inst in ir:
            # WAT f32/f64 consts are in hex float notation (e.g., 0x1.8p+3)
            if inst.name == "f32.const":
                inst.args[0] = hex(struct.unpack('>I', struct.pack('>f', float.fromhex(inst.args[0])))[0])

            elif inst.name == "f64.const":
                inst.args[0] = hex(struct.unpack('>Q', struct.pack('>d', float.fromhex(inst.args[0])))[0])

            elif inst.name.startswith("local"): # get local type
                _, local_locs = func.get_local(int(inst.args[0]))
                inst.args = [str(loc) for loc in local_locs]
                if local_locs:
                    if isinstance(local_locs[0], int): inst.type = "stack"
                    else: inst.type = "reg"
            
            elif inst.name.startswith("global"):
                if inst.args[0] == "__stack_pointer":
                    inst.type = "sp"


class WatParser:
    def __init__(self, compiler: "Compiler") -> None:
        self.compiler = compiler
    def parse(self, text: str):
        lines = text.split("\n")
        return self.astify(self.tokenize(lines))


    def tokenize(self, lines):
        tokens = []
        for line in lines:
            tokens += re.sub(r";;.*", "", line).split()
        return tokens


    def astify(self, tokens: list[str]):
        current_node = None
        modules = []
        for token in tokens:
            token = token.replace("$", "")
            expr_end_count = token.count(")")

            if token.startswith("("):
                if current_node is None:
                    current_node = WatNode(token[1:].replace(")", ""))
                else:
                    current_node.children.append(WatNode(token[1:].replace(")", ""), parent=current_node))
                    current_node = current_node.children[-1]
            
            elif expr_end_count:
                ending_arg = token.split(")")[0]
                if ending_arg and current_node:
                    current_node.args.append(ending_arg)

            elif current_node:
                current_node.args.append(token)

            if expr_end_count:
                while expr_end_count:
                    if current_node:
                        if current_node.parent is None:
                            modules.append(current_node)
                        current_node = current_node.parent  
                    else:
                        break
                    expr_end_count -= 1
        
        if current_node is not None:
            error(self.compiler, "Unbalanced parentheses in WAT.")
        return modules
