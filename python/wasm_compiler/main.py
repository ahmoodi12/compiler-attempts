import argparse
import json
import tempfile
import subprocess
from utils import *
from compiler import Compiler

def main():
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

    wat_data = None
    if program_path.suffix == ".c":
        try:
            ast_proc = subprocess.run(
                    ["clang", "-Xclang", "-ast-dump=json", "-fsyntax-only", str(program_path.resolve())],
                    check=True,
                    capture_output=True
                )
            
            a = json.loads(ast_proc.stdout)
            
            # Use a temporary directory to hold intermediate files
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_o = Path(tmp_dir) / "tmp.o"
                tmp_wasm = Path(tmp_dir) / "tmp.wasm"

                # Compile C → WASM object
                subprocess.run(
                    ["clang", "--target=wasm32", "-c", str(program_path), "-o", str(tmp_o)],
                    check=True,
                    stderr=sys.stderr
                )

                # Link WASM object → WASM binary
                subprocess.run(
                    ["wasm-ld", "--no-entry", "--export-all", "--allow-undefined",
                    str(tmp_o), "-o", str(tmp_wasm)],
                    check=True,
                    stderr=sys.stderr
                )

                # Convert WASM binary → WAT text
                wat_proc = subprocess.run(
                    ["wasm2wat", str(tmp_wasm)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=sys.stderr,
                    text=True
                )

                wat_data = wat_proc.stdout

                # If --trace, save WAT to a file
                if args.trace:
                    wat_file = program_path.with_suffix(".wat")
                    wat_file.write_text(wat_data)

        except subprocess.CalledProcessError as e:
            print(f"Error during compilation: {e}", file=sys.stderr)
            exit(1)

        # If --trace, optionally save WAT file
        if args.trace:
            with open(program_path.with_suffix(".wat"), "w") as wat: wat.write(wat_data)

    Compiler(args.warn, args.trace).run(program_path, isa_path, output_path, wat_data)

if __name__ == "__main__":
    main()


