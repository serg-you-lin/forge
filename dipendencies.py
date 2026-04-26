import ast
from pathlib import Path

src = Path("dxf_forge")
for f in sorted(src.glob("*.py")):
    tree = ast.parse(f.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("dxf_forge") or \
               (node.level and node.level > 0):
                names = [a.name for a in node.names]
                imports.append(f"  from .{node.module or ''} import {', '.join(names)}")
    if imports:
        print(f"\n{f.name}")
        for i in imports:
            print(i)