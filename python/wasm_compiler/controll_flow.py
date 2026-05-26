from utils import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from compiler import Compiler

class ControlFlowPipeline:
    def __init__(self, compiler: "Compiler") -> None:
        self.compiler = compiler


    def make_code_blocks(self, ir: list[IR], func: Func):
        func.block = current_block = CodeBlock(func.name, None)
        self.compiler.label_nums = {label: 0 for label in list(WASM_BLOCK_MAKERS) + ["else", "end", "if_taken"]}

        for inst in ir:
            if inst.name in WASM_BLOCK_MAKERS:
                if current_block:
                    error(self.compiler, "missing end label.", line_content=inst.pretty_IR())
                    new_block = CodeBlock(f"{inst.name}{self.compiler.label_nums[inst.name]}", current_block)
                    current_block.children.append(new_block)
                    current_block.IR.append(new_block)
                    current_block = new_block
                    self.compiler.label_nums[inst.name] += 1

            elif inst.name == "end" and current_block:
                current_block.end_label = f"{inst.name}{self.compiler.label_nums[inst.name]}"
                self.compiler.label_nums[inst.name] += 1
                current_block = current_block.parent
            
            elif inst.name == "else": 
                current_block.else_label = f"{inst.name}{self.compiler.label_nums[inst.name]}:"
                current_block.IR.append(current_block.else_label)
                self.compiler.label_nums[inst.name] += 1
            
            current_block.IR.append(inst)
    

    def label_branches__make_cf_blocks(self, block: CodeBlock, func: Func):
        cf_block = CF_block(block, block.label)
        func.CF.append(cf_block)
        block.CF.append(cf_block)
        
        if block.label.startswith("if"):
            internal_label = "if_taken" + str(self.compiler.label_nums["if_taken"])
            self.compiler.label_nums["if_taken"] += 1
            
            block.IR.insert(0, IR("br_if", [internal_label]))
            block.IR.insert(1, IR("br", [block.else_label if block.else_label else block.end_label])) 
            block.IR.insert(2, internal_label)

        for inst in block.IR:
            if isinstance(inst, CodeBlock) or isinstance(inst, str):
                if isinstance(inst, CodeBlock):
                    self.label_branches__make_cf_blocks(inst, func)
                    label = inst.end_label
                else: label = inst
                cf_block = CF_block(block, label)
                func.CF.append(cf_block)
                block.CF.append(cf_block)

            elif isinstance(inst, IR):
                if inst.name in WASM_BRANCHES:
                    for i, arg in enumerate(inst.args):
                        target_block = block.get_block(int(arg))
                        if target_block.label.startswith("loop"): inst.args[i] = target_block.label
                        else: inst.args[i] = target_block.end_label

                    cf_block.is_branch = True
                    cf_block = CF_block(block)
                    func.CF.append(cf_block)
                    block.CF.append(cf_block)

                cf_block.IR.append(inst)


    def assign_temp_vars(self, cf_block: CF_block, func: Func, cf_block_i = 0, gone_over = None):
        def handle_call(inst: IR, target_func_type: FuncType):
            def def_spill_temp(defs: list):
                new_temp = func.get_next_temp()
                func.temp_counter += 1
                new_temp.spills = defs.copy()
                return new_temp
            
            inst.called_func_type = target_func_type

            param_temps = [func.temp_stack.pop() for _ in target_func_type.params][::-1] # stack param order: deepest = first, top = last
            for i, (_, p_defs) in enumerate(target_func_type.params):
                if p_defs:
                    if isinstance(p_defs[0], int):   # if param location is in stack
                        param_temps[i].last_use_id = self.compiler.id
                        internal_temp = def_spill_temp(p_defs)
                        internal_temp.spills = p_defs # pyright: ignore[reportAttributeAccessIssue]
                        inst.input_spills[param_temps[i].name] = internal_temp
            
            result_temps = [None if defs and isinstance(defs[0], int) else func.new_temp() for (_, defs) in target_func_type.results]
            for i, (_, r_defs) in enumerate(target_func_type.results):
                if r_defs:
                    if isinstance(r_defs[0], int):   # if result location is in stack
                        internal_temp = def_spill_temp(r_defs)
                        internal_temp.spills = r_defs # pyright: ignore[reportAttributeAccessIssue]
                        internal_temp.last_use_id = self.compiler.id
                        result_temp = func.new_temp()
                        inst.output_spills[internal_temp.name] = result_temp
                        assert result_temps[i] is None, "" # for debugging 
                        result_temps[i] = result_temp

            # the final input and output temps of this call, any internal temps for spilling are not included.
            return param_temps, result_temps # stack result/param order: deepest = first, top = last

        def enter_block(target_block: CF_block, block_i):
            nonlocal func
            cf_block.exits.append(target_block) 
            cf_block.input_stack = func.temp_stack.copy()   # what temps naturally get generated by this block
            target_block.entrys.append(cf_block)

            # if current block output stack not defined then we define it
            if not cf_block.output_stack:
                if target_block.entry_stack: cf_block.output_stack = target_block.entry_stack.copy()
                else: cf_block.output_stack = [func.new_temp() for _ in func.temp_stack]
            
            # if target block entry stack not defined then we define it
            elif not target_block.entry_stack:
                target_block.entry_stack = cf_block.output_stack.copy()
            
            elif any(entry != output for entry, output in zip(target_block.entry_stack, cf_block.output_stack)):
                error(self.compiler, "entry stack and output stack don't agree ")
            
            # assign temp vars in target then restore stack so that i can do the same for the next blocks
            self.assign_temp_vars(target_block, func, block_i, gone_over)

        # handling already gone over blocks
        if gone_over is None: gone_over = []
        if cf_block in gone_over: return
        else: gone_over.append(cf_block)

        for inst in cf_block.IR:
            _, pops, pushes, _ = WASM_INSTRUCTIONS[inst.name]
            if inst.name == "call":
                popped_temps, inst.outputs = handle_call(inst, next(f for f in self.compiler.funcs if f.name == inst.args[0]).type) # pyright: ignore[reportAttributeAccessIssue]
            elif inst.name == "call_indirect":
                popped_temps, inst.outputs = handle_call(inst, self.compiler.types[inst.args[0]]) # pyright: ignore[reportAttributeAccessIssue]
            else:
                popped_temps: list[TempVar] = [func.temp_stack.pop() for _ in range(pops)]
                inst.outputs = [func.new_temp() for _ in range(pushes)]
        
            inst.inputs = popped_temps
            inst.id = self.compiler.id
            self.compiler.id += 1

            for temp in popped_temps:
                temp.last_use_id = inst.id

        exit_inst = cf_block.IR[-1] if cf_block.IR else None
        org_stack = func.temp_stack.copy()
        if exit_inst and cf_block.is_branch:
            for arg in exit_inst.args:
                target_i, target = next(((i, b) for i, b in enumerate(func.CF) if b.entry_label == arg), (None, None))
                assert target is not None, "couldn't find target."
                enter_block(target, target_i)
                func.temp_stack = org_stack.copy()

            if exit_inst.name != "br_if": return   # unconditional branches don't go to the next block over
        
        if len(func.CF) > cf_block_i + 1:
            enter_block(func.CF[cf_block_i + 1], cf_block_i + 1)   # go through the next block
            func.temp_stack = org_stack


    def resolve_merge_nodes(self, block: CodeBlock):
        new_ir = []
        for cf_block in block.CF:
            assert len(cf_block.input_stack) == len(cf_block.output_stack), "stack mismatch."
            # add cf block ir to total ir, leave any branch insts out.
            new_ir += cf_block.IR[:-1] if cf_block.is_branch else cf_block.IR.copy()
            
            # emit moves.
            assert len(cf_block.input_stack) == len(cf_block.output_stack), "INTERNAL ERROR: input stack and output stack don't match."
                
            for inp, out in zip(cf_block.input_stack, cf_block.output_stack):
                new_ir.append(IR("move", [], [inp], [out]))
            
            # if block ended in branch add the branch back
            if cf_block.is_branch: new_ir.append(cf_block.IR[-1])
        
        block.IR = new_ir

        for child in block.children:
            self.resolve_merge_nodes(child)
