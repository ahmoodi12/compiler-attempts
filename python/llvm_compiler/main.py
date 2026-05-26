from compiler import Compiler
from pathlib import Path
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble a program using a custom ISA.")
    parser.add_argument("program", type=Path, help="Path to the input program file")
    parser.add_argument("isa", type=Path, help="Path to the ISA definition file")
    parser.add_argument("-o", "--output", type=Path, help="Path for the output binary file")
    parser.add_argument("-t", "--trace", action="store_true", help="prints IR after each compiler stage.")
    parser.add_argument("-w", "--warn", action="store_true", default=False, help=" give any warnings if any occour.")

    args = parser.parse_args()

    # Resolve all paths to absolute
    program_path: Path = args.program.resolve()
    isa_path = args.isa.resolve()
    output_path = (args.output or program_path.with_suffix(".asm")).resolve()

    if not program_path.is_file():
        print(f"Program file not found: {args.program}")
        exit()
    if not isa_path.is_file():
        print(f"ISA file not found: {args.isa}")
        exit()

    compiler = Compiler(args.warn, args.trace)

    compiler.run(program_path, isa_path, output_path)