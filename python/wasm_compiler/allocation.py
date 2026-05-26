import math
import re
from utils import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from compiler import Compiler

class Allocator:
    def __init__(self, compiler: "Compiler") -> None:
        self.compiler = compiler


    def def_temps(self, block: CodeBlock, func: Func):
        def get_reg_count(op: tuple[str, int], inst_name: str):
            if self.compiler.op_reg_count_cache.get(inst_name, {}).get(op[0], {}).get(op[1]) is not None:
                return self.compiler.op_reg_count_cache[inst_name][op[0]][op[1]]
            if inst_name in self.compiler.isa["translation table"]: 
                highest = 0
                for line in self.compiler.isa["translation table"][inst_name]:
                    for reg_i in re.findall(fr"{op[0]}\[{op[1]}\](?:\[(\d+)\])?", line):
                        if reg_i and int(reg_i) > highest: highest = int(reg_i)
                highest += 1
                self.compiler.op_reg_count_cache[inst_name] = {op[0]: {op[1]: highest}}
                return highest

            # fallback, get inst bit width if it has bitwidth else default to 32
            inst_width = WASM_INSTRUCTIONS[inst_name][2]
            if inst_width is None: inst_width = 32
            return math.ceil(inst_width/self.compiler.hardware["reg width"]) # inst bit width / reg bit width

        def kill_temp(temp: TempVar):
            # NOTE im not removing temp out of the system just delcaring it's slots clear, useful later if i want it back
            func.free_regs += temp.regs
            for r in temp.regs: func.used_regs.pop(r)
            func.free_slots += temp.spills
            temp.spills, temp.regs = [], []
            func.alive_temps.remove(temp)

        def spill_temp(temp: TempVar):
            nonlocal block
            slot_n = len(temp.regs)
            regs = temp.regs
            kill_temp(temp)
            temp.spills = self.assign_stack_slots(func, slot_n)
            block.MIR += self.emit_spill_insts("store", regs, temp.spills)

        def get_regs(amt, temp: TempVar):
            nonlocal regs_to_push_if_used, func
            regs = []
            while amt:
                if func.free_regs: 
                    reg = func.free_regs.pop()
                    func.used_regs[reg] = temp
                    regs.append(reg)
                    amt -= 1
                    continue
                
                # no free regs, spill regs
                # shouldn't spill current temp, check is needed for multi reg assignment
                victim: TempVar = max((t for t in func.alive_temps if temp != t), key=lambda t: t.last_use_id) 
                spill_temp(victim)
            if regs_to_push_if_used:
                for reg in regs:
                    if reg in regs_to_push_if_used:
                        func.regs_to_push.append(reg)
                        regs_to_push_if_used.remove(reg)
            return regs

        def alloc_temp(temp: TempVar, amt_regs: int):
            regs = get_regs(amt_regs, temp)
            temp.regs = regs
            func.alive_temps.append(temp)
            return regs

        # define what regs need to be saved if their used.
        # free regs contains the regs that params didn't use.
        regs_to_push_if_used = func.type.free_regs.copy()
        for (_, res) in func.type.results:
            for loc in res: 
                # if result is using a temp reg then that reg isn't temporary and is meant to be overwritten.
                if isinstance(loc, str) and loc in regs_to_push_if_used: regs_to_push_if_used.remove(loc)
        
        for inst in block.IR:
            if isinstance(inst, CodeBlock): 
                self.def_temps(inst, func)
                block.MIR.append(inst)
                continue
            if isinstance(inst, str):
                block.MIR.append(inst)
                continue
            
            # if inst definition needs to spill vals temporarly.
            spills = self.assign_stack_slots(func, self.compiler.isa["inst spills"].get(inst.name, 0))

            inputs = []
            for i, temp in enumerate(inst.inputs):
                if inst.called_func_type:
                    internal_temp = inst.input_spills.get(temp.name)
                    if internal_temp: # means input for call is in stack, store input temp into internal temp which simply goes to the call
                        self.emit_spill_insts("store", temp.regs, internal_temp.spills)

                if temp.regs:
                    inputs.append(temp.regs)
                
                elif temp not in func.alive_temps:   # bring temp back from spill.
                    regs = alloc_temp(temp, get_reg_count(("in", i), "load"))
                    inputs.append(regs)

                    block.MIR += self.emit_spill_insts("load", regs, temp.spills)
                    
                    temp.spills = []  # not in spill longer.
                
                if temp.is_dead(inst.id): # this was the last use.
                    kill_temp(temp)
            
            outputs = []
            for i, temp in enumerate(inst.outputs):
                if not temp.regs and not temp.spills:
                    # normal undefined temp
                    outputs.append(alloc_temp(temp, get_reg_count(("out", i), inst.name)))
                
                # if temp already defined, happens with calls
                elif temp.regs:
                    # spill any temps defined to this temps regs
                    for r in temp.regs:
                        if r in func.used_regs: spill_temp(func.used_regs[r])
                    
                    # add temp to alive temps
                    if temp not in func.alive_temps: func.alive_temps.append(temp)
                    
                    outputs.append(temp.regs)
                
                if inst.called_func_type:
                    internal_temp = inst.output_spills.get(temp.name)
                    if internal_temp: # means output is in stack, load it back from internal temp to output temp
                        self.emit_spill_insts("load", temp.regs, internal_temp.spills)
                
            block.MIR.append(MIR(inst.name, inst.args, [""], inputs, outputs, type=inst.type, ir=inst, spills=spills))


    def def_call_temps(self, block: CodeBlock, func: Func):
        def def_temp(temp:TempVar, defs):
            if defs:
                if isinstance(defs[0], str):
                    temp.regs = defs
        
        for (_, result) in func.type.results[::-1]:
            def_temp(func.temp_stack.pop(), result)

        for inst in block.IR:
            if isinstance(inst, CodeBlock): 
                self.def_call_temps(inst, func)
                continue
            if isinstance(inst, str):
                continue
            
            if inst.called_func_type:
                for i, temp in enumerate(inst.inputs):
                    def_temp(temp, inst.called_func_type.params[i][1])
                for i, temp in enumerate(inst.outputs):
                    def_temp(temp, inst.called_func_type.results[i][1])


    def emit_spill_insts(self, inst_name: str, regs, slots):
        if len(regs) != len(slots): error(self.compiler, "load emission failed because amount of regs didn't match amount of slots to store in.")
        mir = []
        for slot, reg in zip(slots, regs):
            mir.append(MIR(inst_name, [reg, str(slot)]))
        return mir


    def assign_stack_slots(self, func: Func, num_slots):
        slots = []
        while num_slots:
            if func.free_slots: slot = func.free_slots.pop()
            else:
                slot = func.stack_offset
                func.stack_offset += 1
            slots.append(slot)
            num_slots -= 1
        return slots
