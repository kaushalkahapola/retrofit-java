import javalang

def parse_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    return javalang.parse.parse(content), content

def get_method_declarations(tree):
    methods = {}
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        params = [p.type.name for p in node.parameters]
        sig = f"{node.name}({', '.join(params)})"
        methods[sig] = node
    return methods

def get_lines_from_node(file_content, node):
    if not node.position: return ""
    lines = file_content.splitlines()
    start_line = node.position.line - 1
    return extract_block_by_braces(lines, start_line)

def extract_block_by_braces(lines, start_index):
    snippet = []
    open_braces = 0
    found_start = False
    for i in range(start_index, len(lines)):
        line = lines[i]
        snippet.append(line)
        open_braces += line.count('{')
        open_braces -= line.count('}')
        if '{' in line: found_start = True
        if found_start and open_braces == 0: break
    return "\n".join(snippet)

def get_ast_fingerprint(method_node):
    """
    Flattens a method body into a set of tokens for similarity comparison.
    Captures: Node Types, Variable Names, and Literals.
    """
    tokens = set()
    
    # 1. Capture Parameter Names (Context)
    for param in method_node.parameters:
        tokens.add(f"PARAM:{param.name}")

    # 2. Walk the descendants
    # FIX: Use .filter(javalang.tree.Node) to recursively walk the tree
    # instead of iterating over .body directly.
    if method_node.body:
        for path, node in method_node.filter(javalang.tree.Node):
            # Capture the Node Type (Structure)
            tokens.add(f"TYPE:{type(node).__name__}")
            
            # Capture Variable References (e.g., variable names used)
            if isinstance(node, javalang.tree.MemberReference):
                tokens.add(f"VAR:{node.member}")
            
            # Capture Literals (Very important for matching constants like '18')
            if isinstance(node, javalang.tree.Literal):
                tokens.add(f"LIT:{node.value}")
                
            # Capture Operators (Logic like >=, <, &&)
            if isinstance(node, javalang.tree.BinaryOperation):
                tokens.add(f"OP:{node.operator}")

    return tokens