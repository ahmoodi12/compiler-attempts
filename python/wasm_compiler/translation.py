import re
from utils import *
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from compiler import Compiler

class translator:
    def __init__(self, compiler: "Compiler") -> None:
        self.compiler = compiler
    

    def emit_blocks(self, block: CodeBlock):
        self.compiler.translated_code.append(block.label + ":")
        for line in block.MIR:
            if isinstance(line, CodeBlock):
                self.emit_blocks(line)
            elif isinstance(line, str):
                self.compiler.translated_code.append(line + ":")
            else:
                self.compiler.translated_code.extend(line.definition)
        self.compiler.translated_code.append(block.end_label)
        self.compiler.translated_code += ["", ""]
        

    def translate(self, block: CodeBlock, func: Func):
        for inst in block.MIR:
            if isinstance(inst, CodeBlock):
                self.translate(inst, func)
            elif not isinstance(inst, str):
                self.translate_inst(inst)


    def translate_inst(self, inst: MIR):
        def validate_ops(inst: MIR, line: str):
            # validate inputs, outputs, inouts
            for m in re.finditer(r"(in|out|spill)\[(\d+)\](?:\[(\d+)\])?", line):
                type = m.group(1); i = int(m.group(2)); ri = m.group(3)
                if ri: ri = int(ri)
                if type == "in":
                    if len(inst.inputs) <= i: error(self.compiler, "input index too high.", line_content="wasm inst:\n" + inst.pretty_MIR() + "\n\ntranlation error line:\n" + line)
                    if ri and len(inst.inputs[i]) <= ri: error(self.compiler, "input reg index too high.", line_content="wasm inst:\n" + inst.pretty_MIR() + "\n\ntranlation error line:\n" + line, highlight=f"in[{i}][{ri}]")
                if type == "out":
                    if len(inst.outputs) <= i: error(self.compiler, "output index too high.", line_content="wasm inst:\n" + inst.pretty_MIR() + "\n\ntranlation error line:\n" + line)
                    if ri and len(inst.outputs[i]) <= ri: error(self.compiler, "output reg index too high.", line_content="wasm inst:\n" + inst.pretty_MIR() + "\n\ntranlation error line:\n" + line, highlight=f"out[{i}][{ri}]")
                if type == "spill":
                    if len(inst.spills) <= i: error(self.compiler, "spill index too high.", line_content="wasm inst:\n" + inst.pretty_MIR() + "\n\ntranlation error line:\n" + line)

        def replace_ops(inst: MIR, line: str):
            # replace inputs, outputs. TODO inouts
            for i, inp in enumerate(inst.inputs):
                for r_i, reg in enumerate(inp):
                    line = line.replace(f"in[{i}][{r_i}]", reg)

            for i, out in enumerate(inst.outputs):
                for r_i, reg in enumerate(out):
                    line = line.replace(f"out[{i}][{r_i}]", reg)
            
            for i, arg in enumerate(inst.args):
                line = line.replace(f"arg[{i}]", arg)

            for i, spill in enumerate(inst.spills):
                line = line.replace(f"spill[{i}]", str(spill))
            return line
            
        # Look up the translation in your ISA table
        translation = self.compiler.isa["translation table"].get(inst.name, {})
        
        if inst.type: 
            if inst.type not in translation: error(self.compiler, f"translation for '{inst.name}' doesn't have type '{inst.type}'.")
            if isinstance(translation, dict):
                translation = translation[inst.type]
        
        # check translation
        if not translation:
            error(self.compiler, f"No translation for {inst.name}", fatal_error=False)
            return []

        for line in translation:
            validate_ops(inst, line)
            line_def = replace_ops(inst, line)
            inst.definition.append(line_def)
