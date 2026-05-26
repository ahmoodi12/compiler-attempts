# combines my compiler into one file
from pathlib import Path

current_folder = Path(__file__).parent
modules = ["main.py", "frontend.py", "controll_flow.py", "allocation.py", "translation.py", "compiler.py", "utils.py"]


modules_sect = [modules[:(len(modules)//2)], modules[(len(modules)//2):]]
for i in range(2):
    combined_str = ""
    for module in modules_sect[i]:
        module_path = Path(str(current_folder) + "\\" + module)
        if module_path.is_file():
            if combined_str: combined_str += "\n"*3
            combined_str += "#" + "-"*15 + module_path.name + "-"*15 + "\n"
            combined_str += module_path.read_text()

    Path(str(current_folder) + f"\\full_compiler{i}").write_text(combined_str)