import ast, sys

def extract_signatures(path):
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = []
            for a in node.args.args:
                args.append(a.arg)
            defaults_offset = len(node.args.args) - len(node.args.defaults)
            result = []
            for i, a in enumerate(node.args.args):
                if i >= defaults_offset:
                    d = ast.unparse(node.args.defaults[i - defaults_offset])
                    result.append(f"{a.arg}={d}")
                else:
                    result.append(a.arg)
            print(f"def {node.name}({', '.join(result)})")

for path in sys.argv[1:]:
    print(f"\n# {path}")
    extract_signatures(path)