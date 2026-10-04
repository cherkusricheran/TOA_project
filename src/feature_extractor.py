from tree_sitter import Node
from src.ast_parser import ASTParser

class FeatureExtractor:
    def __init__(self):
        self.parser_interface = ASTParser()
        
        self.queries = {
            'python': """
                (call function: (identifier) @func)
                (call function: (attribute) @func)
                (if_statement) @branch
                (for_statement) @branch
                (while_statement) @branch
                (except_clause) @branch
                (elif_clause) @branch
                (boolean_operator) @branch
            """,
            'javascript': """
                (call_expression function: (identifier) @func)
                (call_expression function: (member_expression) @func)
                (if_statement) @branch
                (for_statement) @branch
                (while_statement) @branch
                (switch_case) @branch
                (catch_clause) @branch
                (binary_expression operator: "||" @branch)
                (binary_expression operator: "&&" @branch)
            """,
            'java': """
                (method_invocation name: (identifier) @func)
                (method_invocation object: (identifier) name: (identifier) @func)
                (if_statement) @branch
                (for_statement) @branch
                (while_statement) @branch
                (catch_clause) @branch
                (switch_label) @branch
                (binary_expression operator: "||" @branch)
                (binary_expression operator: "&&" @branch)
            """,
            'c': """
                (call_expression function: (identifier) @func)
                (if_statement) @branch
                (for_statement) @branch
                (while_statement) @branch
                (case_statement) @branch
                (binary_expression operator: "||" @branch)
                (binary_expression operator: "&&" @branch)
            """
        }

        # ── Structural extraction queries (NEW) ──────────────────────
        # Pull function/method definition names and class names from the AST.
        self._struct_queries = {
            'python': """
                (function_definition name: (identifier) @fn_name)
                (class_definition name: (identifier) @cls_name)
            """,
            'javascript': """
                (function_declaration name: (identifier) @fn_name)
                (method_definition name: (property_identifier) @fn_name)
                (class_declaration name: (identifier) @cls_name)
            """,
            'java': """
                (method_declaration name: (identifier) @fn_name)
                (class_declaration name: (identifier) @cls_name)
                (interface_declaration name: (identifier) @cls_name)
            """,
            'c': """
                (function_definition declarator: (function_declarator
                    declarator: (identifier) @fn_name))
            """,
        }

        self.sources = {
            'python': {'input', 'sys.argv', 'request.args', 'request.form', 'open'},
            'javascript': {'prompt', 'process.argv', 'req.body', 'req.query'},
            'java': {'Scanner', 'System.in', 'getParameter'},
            'c': {'scanf', 'gets', 'read'}
        }
        self.sinks = {
            'python': {
                'eval', 'exec', 'os.system', 'subprocess.call', 'pickle.loads', 'subprocess.Popen', 
                'cursor.execute', 'execute', 'subprocess.run', 'os.popen', 'yaml.load', 'tarfile.open'
            },
            'javascript': {
                'eval', 'setTimeout', 'child_process.exec', 'document.write', 'child_process.spawn', 'element.innerHTML'
            },
            'java': {
                'Runtime.exec', 'ProcessBuilder', 'Statement.execute', 'Runtime.loadLibrary'
            },
            'c': {
                'system', 'execl', 'popen', 'strcpy', 'strcat', 'sprintf', 'memcpy', 'gets'
            }
        }

    # ── Structural helpers (NEW) ─────────────────────────────────────

    def _extract_imports_regex(self, code_str: str, language: str) -> list:
        """Extract import/include module names via lightweight regex (no AST needed)."""
        import re
        names = []
        if language == 'python':
            # "import X", "import X as Y", "from X import ..."
            for m in re.finditer(
                r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))',
                code_str, re.MULTILINE
            ):
                raw = (m.group(1) or m.group(2) or '').strip()
                for part in raw.split(','):
                    mod = part.strip().split()[0].split('.')[0]
                    if mod:
                        names.append(mod)
        elif language == 'javascript':
            # require('X') or import ... from 'X'
            for m in re.finditer(
                r"""(?:require\s*\(\s*['"]([^'"]+)['"]|from\s+['"]([^'"]+)['"]\s*;?)""",
                code_str
            ):
                raw = (m.group(1) or m.group(2) or '').strip()
                mod = raw.split('/')[0].lstrip('@')
                if mod:
                    names.append(mod)
        elif language == 'java':
            # "import com.example.Foo;" -> "Foo"
            for m in re.finditer(r'^\s*import\s+(?:static\s+)?([\w.]+)\s*;', code_str, re.MULTILINE):
                parts = m.group(1).split('.')
                names.append(parts[-1])
        elif language == 'c':
            # #include <stdio.h> or #include "local.h"
            for m in re.finditer(r'^\s*#include\s*[<"]([^>"]+)[>"]', code_str, re.MULTILINE):
                names.append(m.group(1))
        # Deduplicate, preserve order, cap at 8
        seen = set()
        result = []
        for n in names:
            if n not in seen:
                seen.add(n)
                result.append(n)
            if len(result) >= 8:
                break
        return result

    def _extract_struct_ast(self, tree, code_str: str, language: str) -> tuple:
        """
        Extract function names and class names from the AST using structural queries.
        Returns (functions: list[str], classes: list[str]).
        Falls back to empty lists on any error — never breaks the pipeline.
        """
        functions = []
        classes   = []

        if language not in self._struct_queries:
            return functions, classes

        lang_obj = self.parser_interface.get_language(language)
        if not lang_obj:
            return functions, classes

        try:
            from tree_sitter import Query, QueryCursor
            query   = Query(lang_obj, self._struct_queries[language])
            cursor  = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
            code_bytes = code_str.encode('utf-8')

            for capture_name, nodes in captures.items():
                for node in nodes:
                    name = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore').strip()
                    if not name:
                        continue
                    if capture_name == 'fn_name':
                        if name not in functions:
                            functions.append(name)
                    elif capture_name == 'cls_name':
                        if name not in classes:
                            classes.append(name)
        except Exception:
            pass  # best-effort; structural extraction never breaks the pipeline

        return functions[:10], classes[:5]

    # ── Behavioral extraction helpers ────────────────────────────────

    def _extract_params(self, code_str: str, language: str) -> dict:
        """
        Extract parameter names for each function definition.
        Returns dict: {function_name: [param1, param2, ...]}.
        Uses regex for reliability across all 4 languages.
        """
        import re
        params_by_fn = {}

        if language == 'python':
            # def func_name(param1, param2, ...):
            for m in re.finditer(
                r'def\s+(\w+)\s*\(([^)]*)\)\s*(?:->.*?)?:',
                code_str
            ):
                fn_name = m.group(1)
                raw_params = m.group(2).strip()
                if not raw_params:
                    params_by_fn[fn_name] = []
                    continue
                params = []
                for p in raw_params.split(','):
                    p = p.strip()
                    if not p or p == 'self' or p == 'cls':
                        continue
                    # Strip type hints (x: int = 5 -> x), defaults, *args, **kwargs
                    name = re.split(r'[:=]', p)[0].strip().lstrip('*')
                    if name and name.isidentifier():
                        params.append(name)
                params_by_fn[fn_name] = params[:5]

        elif language == 'javascript':
            # function name(a, b) or name(a, b) {  (method)
            for m in re.finditer(
                r'(?:function\s+(\w+)|(\w+)\s*(?:=\s*(?:function|async\s+function)?\s*)?)\s*\(([^)]*)\)\s*[{]',
                code_str
            ):
                fn_name = m.group(1) or m.group(2)
                if not fn_name or fn_name in ('if', 'for', 'while', 'switch', 'catch', 'return'):
                    continue
                raw = m.group(3).strip()
                params = []
                for p in raw.split(','):
                    name = p.strip().split('=')[0].strip().lstrip('.')
                    if name and re.match(r'^[a-zA-Z_]\w*$', name):
                        params.append(name)
                params_by_fn[fn_name] = params[:5]

        elif language == 'java':
            # returnType methodName(Type param, Type param)
            for m in re.finditer(
                r'(?:public|private|protected|static|\s)+\s+\w[\w<>\[\],\s]*\s+(\w+)\s*\(([^)]*)\)',
                code_str
            ):
                fn_name = m.group(1)
                if fn_name in ('if', 'for', 'while', 'switch', 'catch', 'return', 'class'):
                    continue
                raw = m.group(2).strip()
                params = []
                for p in raw.split(','):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        params.append(parts[-1])  # last word is param name
                    elif len(parts) == 1 and parts[0].isidentifier():
                        params.append(parts[0])
                params_by_fn[fn_name] = params[:5]

        elif language == 'c':
            # returnType functionName(type param, type param)
            for m in re.finditer(
                r'\b(\w+)\s*\(([^)]+)\)\s*\{',
                code_str
            ):
                fn_name = m.group(1)
                if fn_name in ('if', 'for', 'while', 'switch', 'sizeof', 'return'):
                    continue
                raw = m.group(2).strip()
                if raw == 'void' or raw == '':
                    params_by_fn[fn_name] = []
                    continue
                params = []
                for p in raw.split(','):
                    parts = p.strip().replace('*', ' ').split()
                    if parts:
                        name = parts[-1]
                        if re.match(r'^[a-zA-Z_]\w*$', name) and name not in ('int', 'char', 'void', 'float', 'double', 'const', 'unsigned'):
                            params.append(name)
                params_by_fn[fn_name] = params[:5]

        return params_by_fn

    def _extract_returns(self, code_str: str, language: str, functions: list) -> dict:
        """
        For each function, extract a simplified description of what is returned.
        Returns dict: {function_name: 'description'}.
        Only captures simple, reliable patterns. Complex expressions → generic.
        """
        import re
        return_info = {}

        if language in ('python', 'javascript', 'java', 'c'):
            lines = code_str.split('\n')
            current_fn = None

            for line in lines:
                stripped = line.strip()

                # Detect function definition
                if language == 'python':
                    m = re.match(r'def\s+(\w+)\s*\(', stripped)
                elif language == 'javascript':
                    m = re.match(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|async\s+function))', stripped)
                elif language == 'java':
                    m = re.match(r'(?:public|private|protected|static|\s)+\s+\w[\w<>\[\],\s]*\s+(\w+)\s*\(', stripped)
                elif language == 'c':
                    m = re.match(r'\b\w+[\s*]+(\w+)\s*\([^)]*\)\s*\{', stripped)
                else:
                    m = None

                if m:
                    current_fn = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
                    continue

                # Detect return statement
                ret_match = re.match(r'return\s+(.+?)[\s;]*$', stripped)
                if ret_match and current_fn and current_fn not in return_info:
                    expr = ret_match.group(1).rstrip(';').strip()
                    desc = self._describe_return_expr(expr, language, code_str)
                    if desc:
                        return_info[current_fn] = desc

        return return_info

    @staticmethod
    def _describe_return_expr(expr: str, language: str, code_str: str = "") -> str:
        """Convert a return expression into a brief English description."""
        import re
        e = expr.strip()

        if not e or e == 'None' or e == 'null' or e == 'undefined':
            return ''
        if e in ('True', 'true', 'False', 'false'):
            return 'a boolean value'
        if re.match(r'^[\d.]+$', e):
            return f'the value {e}'
        if e.startswith('[') or e.startswith('new Array') or e.startswith('Arrays.'):
            return 'a list'
        if e.startswith('{') or e.startswith('new Map') or e.startswith('new Object'):
            return 'an object'
        if e.startswith('"') or e.startswith("'") or e.startswith('f"') or e.startswith("f'"):
            return 'a string'

        # Arithmetic: a / b, a + b, a * b, a - b, a % b
        arith = re.match(r'^(.+?)\s*([+\-*/%])\s*(.+)$', e)
        if arith:
            left = arith.group(1).strip()
            op = arith.group(2)
            right = arith.group(3).strip()

            # Check if left or right is assigned nearby in code_str
            assignments = dict(re.findall(r'\b([a-zA-Z_]\w*)\s*=\s*([^=\n;]+)', code_str)) if code_str else {}
            if left in assignments and len(assignments[left].strip()) < 30:
                left_desc = f"{left} ({assignments[left].strip()})"
            else:
                left_desc = left

            if op == '/':
                if any(w in left_desc.lower() for w in ('total', 'sum', 'add')) and any(w in right.lower() for w in ('len', 'count', 'size', 'length')):
                    return "the calculated average"
                return f"dividing {left_desc} by {right}"
            elif op == '+':
                if ('salt' in left_desc.lower() and 'key' in right.lower()) or ('key' in left_desc.lower() and 'salt' in right.lower()):
                    return "the combined salt and derived cryptographic key"
                return f"the sum of {left_desc} and {right}"
            elif op == '-':
                return f"subtracting {right} from {left_desc}"
            elif op == '*':
                return f"multiplying {left_desc} by {right}"
            elif op == '%':
                return f"the remainder of {left_desc} divided by {right}"

        # File read or lookup matches
        if 'read()' in e or 'readLines()' in e or 'read_text()' in e:
            return "the contents of the file"
        if ('seen[' in e or 'map[' in e) and ('[' in e and ']' in e):
            return "the indices of the matching pair"

        # Function call: sorted(...), len(...), etc.
        call_match = re.match(r'^(\w[\w.]*)\s*\(', e)
        if call_match:
            fn = call_match.group(1)
            return f'the result of {fn}()'

        # Simple variable
        if re.match(r'^[a-zA-Z_]\w*$', e):
            return f'the value of {e}'

        # Fallback: too complex to describe reliably
        return 'a computed result'

    def _extract_output_calls(self, code_str: str, language: str) -> list:
        """
        Extract arguments from print/output calls, distinguishing literal labels
        from actual expressions and values being output.
        """
        import re
        outputs = []

        patterns = {
            'python':     r'\bprint\s*\((.+?)\)\s*$',
            'javascript': r'\bconsole\.log\s*\((.+?)\)\s*;?\s*$',
            'java':       r'\bSystem\.out\.print(?:ln)?\s*\((.+?)\)\s*;',
            'c':          r'\bprintf\s*\((.+?)\)\s*;',
        }
        pattern = patterns.get(language)
        if not pattern:
            return outputs

        for m in re.finditer(pattern, code_str, re.MULTILINE):
            args_str = m.group(1).strip()
            # Check for label string + variable expression, e.g. print("Average:", average)
            labeled_comma = re.match(r"""^[fF]?["']([^"']+)["']\s*,\s*([a-zA-Z_]\w*(?:\([^)]*\))?)""", args_str)
            labeled_concat = re.match(r"""^[fF]?["']([^"']+)["']\s*\+\s*([a-zA-Z_]\w*(?:\([^)]*\))?)""", args_str)
            labeled_match = labeled_comma or labeled_concat

            if labeled_match:
                lbl = labeled_match.group(1).rstrip(':').strip()
                expr = labeled_match.group(2).strip()
                if expr.lower() in ('average', 'avg') or 'average' in lbl.lower():
                    outputs.append("the calculated average")
                elif expr.lower() in ('result', 'res', 'total', 'output', 'sum', 'ans'):
                    outputs.append(f"the calculated {expr}")
                elif expr:
                    outputs.append(f"the {expr}")
                elif lbl:
                    outputs.append(f"'{lbl}'")
            elif re.match(r'^[a-zA-Z_]\w*$', args_str):
                var_name = args_str
                if var_name.lower() in ('average', 'avg'):
                    outputs.append("the calculated average")
                elif var_name.lower() in ('result', 'res', 'total', 'output', 'sum'):
                    outputs.append(f"the calculated {var_name}")
                else:
                    outputs.append(f"the {var_name}")
            else:
                str_match = re.match(r"""^[fF]?["']([^"']+)["']""", args_str)
                if str_match:
                    label = str_match.group(1).rstrip(':').strip()
                    if label and '{' not in label and '}' not in label and len(label) <= 60:
                        outputs.append(f"'{label}'")
            if len(outputs) >= 3:
                break

        return outputs


    def _extract_fn_body_facts(self, code_str: str, language: str,
                               declared_fns: list) -> dict:
        """
        For each declared function extract lightweight, grounded behavioral facts:
          api_calls   – external/library calls found in the function body
                        (e.g. hashlib.pbkdf2_hmac, os.urandom, eval, document.getElementById)
          intra_calls – calls to OTHER declared functions in this program
                        (ONLY recorded when the body literally contains that call)
          has_loop    – True when the body contains a for/while loop
          has_cond    – True when the body contains an if/switch
          dom_reads   – element IDs passed to getElementById (JS only)
          dom_writes  – DOM properties written inside the body (JS only)

        All extraction is regex-only and best-effort.  Never raises.
        """
        import re
        declared_set = set(declared_fns)
        result = {}

        # Map language → regex that finds the start of each function definition
        if language == 'python':
            hpat = re.compile(r'^def\s+(\w+)\s*\(', re.MULTILINE)
        elif language == 'javascript':
            hpat = re.compile(r'^(?:async\s+)?function\s+(\w+)\s*\(', re.MULTILINE)
        elif language == 'java':
            hpat = re.compile(
                r'(?:public|private|protected|static|\s)+\s+\w[\w<>\[\],\s]*\s+(\w+)\s*\(',
                re.MULTILINE)
        elif language == 'c':
            hpat = re.compile(r'^\w[\w\s*]*\s+(\w+)\s*\([^)]*\)\s*\{', re.MULTILINE)
        else:
            return result

        headers = list(hpat.finditer(code_str))
        for i, hm in enumerate(headers):
            fn_name = hm.group(1)
            if fn_name not in declared_set:
                continue
            body = code_str[hm.start():
                            headers[i + 1].start() if i + 1 < len(headers) else len(code_str)]

            facts = {
                'api_calls':   [],
                'intra_calls': [],
                'has_loop':    bool(re.search(r'\b(?:for|while)\b', body)),
                'has_cond':    bool(re.search(r'\b(?:if|switch)\b', body)),
                'dom_reads':   [],
                'dom_writes':  [],
                'file_ops':    bool(re.search(r'\b(?:open|FileReader|FileInputStream|fopen|\.read\(|fread)\b', body)),
                'web_ops':     bool(re.search(r'\b(?:request\.(?:args|form|values|json|get)|req\.(?:query|body|params)|getParameter)\b', body)),
                'crypto_ops':  bool(re.search(r'\b(?:hashlib|urandom|pbkdf2|sha256|sha512|aes|bcrypt|hmac|MessageDigest)\b', body, re.IGNORECASE)),
                'lookup_ops':  bool(re.search(r'\b[a-zA-Z_]\w*\[[a-zA-Z_]\w*\]|\.containsKey\(|\bdict\.get\(', body)),
            }

            all_calls = re.findall(r'\b([\w.]+)\s*\(', body)

            # Intra-calls: calls to other declared functions actually present in body
            for c in all_calls:
                base = c.split('.')[-1]
                if base in declared_set and base != fn_name and base not in facts['intra_calls']:
                    facts['intra_calls'].append(base)

            # API / library calls
            NOTABLE_BUILTINS = {
                'eval', 'exec', 'open', 'sum', 'len', 'sorted',
                'map', 'filter', 'zip', 'enumerate', 'range', 'hash',
            }
            for c in all_calls:
                if '.' in c and not c.startswith('self.') and not c.startswith('super.'):
                    if c not in facts['api_calls'] and len(facts['api_calls']) < 6:
                        facts['api_calls'].append(c)
                elif c in NOTABLE_BUILTINS and c not in facts['api_calls'] and len(facts['api_calls']) < 6:
                    facts['api_calls'].append(c)

            # JS DOM access
            if language == 'javascript':
                for gm in re.finditer(
                        r'document\.getElementById\s*\(\s*["\']([^"\' ]+)["\']\s*\)', body):
                    eid = gm.group(1)
                    if eid not in facts['dom_reads']:
                        facts['dom_reads'].append(eid)
                for wm in re.finditer(
                        r'\b\w+\.(textContent|innerHTML|value)\s*\+?=', body):
                    prop = wm.group(1)
                    if prop not in facts['dom_writes']:
                        facts['dom_writes'].append(prop)

            result[fn_name] = facts
        return result

    def _extract_comments(self, code_str: str, language: str, declared_fns: list) -> tuple:
        """
        Extract relevant comments and docstrings from source code as supporting intent context.
        Filters out noise (license, pragma, todo) and keeps compact intent.
        Returns (doc_context: str, fn_docs: dict[str, str]).
        """
        import re
        doc_context = ""
        fn_docs = {}

        # 1. Top-level docstring / file header intent
        top_chunk = code_str[:600].strip()
        if language == 'python':
            top_doc = re.match(r'^(?:#[^\n]*\n\s*)*(?:"""|\'\'\')([\s\S]*?)(?:"""|\'\'\')', top_chunk)
            if top_doc:
                raw = top_doc.group(1).strip().split('\n')[0].strip()
                if raw and not any(raw.lower().startswith(b) for b in ('copyright', 'license', 'author', 'todo', 'pylint')):
                    doc_context = raw[:120]
        elif language in ('javascript', 'java', 'c'):
            top_block = re.match(r'^\s*/\*\*?([\s\S]*?)\*/', top_chunk)
            if top_block:
                lines_blk = [re.sub(r'^\s*\*+\s*', '', l).strip() for l in top_block.group(1).split('\n')]
                lines_blk = [l for l in lines_blk if l and not any(l.lower().startswith(b) for b in ('copyright', 'license', 'author', 'todo', '@'))]
                if lines_blk:
                    doc_context = lines_blk[0][:120]

        if not doc_context:
            prefix = '#' if language == 'python' else '//'
            lead_comments = []
            for line in top_chunk.split('\n')[:8]:
                s = line.strip()
                if s.startswith(prefix):
                    c = s.lstrip('#/ \t').strip()
                    if c and not any(c.lower().startswith(b) for b in ('!', 'copyright', 'license', 'author', 'todo', 'type:', 'eslint', 'pragma', '---', '===')):
                        lead_comments.append(c)
                elif s and not s.startswith(prefix):
                    break
            if lead_comments:
                doc_context = ' '.join(lead_comments)[:120]

        # 2. Per-function intent (comments immediately preceding or inside function definition)
        for fn in declared_fns:
            fn_esc = re.escape(fn)
            if language == 'python':
                pattern = rf'((?:[ \t]*#[^\n]*\n)*)[ \t]*def\s+{fn_esc}\s*\([^)]*\)[^:]*:\s*\n((?:[ \t]*(?:"""|\'\'\')[\s\S]*?(?:"""|\'\'\')|[ \t]*#[^\n]*\n)*)'
            elif language == 'javascript':
                pattern = rf'((?:[ \t]*//[^\n]*\n|[ \t]*/\*[\s\S]*?\*/\s*\n)*)[ \t]*(?:async\s+)?function\s+{fn_esc}\s*\([^)]*\)\s*\{{((?:[ \t]*//[^\n]*\n)*)'
            elif language == 'java':
                pattern = rf'((?:[ \t]*//[^\n]*\n|[ \t]*/\*[\s\S]*?\*/\s*\n)*)[ \t]*(?:public|private|protected|static|\s)+\s+\w[\w<>\[\],\s]*\s+{fn_esc}\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\{{((?:[ \t]*//[^\n]*\n)*)'
            elif language == 'c':
                pattern = rf'((?:[ \t]*//[^\n]*\n|[ \t]*/\*[\s\S]*?\*/\s*\n)*)[ \t]*\w[\w\s*]*\s+{fn_esc}\s*\([^)]*\)\s*\{{((?:[ \t]*//[^\n]*\n)*)'
            else:
                continue

            m = re.search(pattern, code_str)
            if not m:
                continue

            pre_comment = m.group(1).strip()
            inside_comment = m.group(2).strip()

            intent = ""
            if language == 'python' and inside_comment:
                doc_m = re.search(r'(?:"""|\'\'\')([\s\S]*?)(?:"""|\'\'\')', inside_comment)
                if doc_m:
                    intent = doc_m.group(1).strip().split('\n')[0].strip()
                elif inside_comment.startswith('#'):
                    intent = inside_comment.lstrip('# \t').split('\n')[0].strip()

            if not intent and pre_comment:
                for line in reversed(pre_comment.split('\n')):
                    cleaned = re.sub(r'^[/#*\s]+|[/*\s]+$', '', line).strip()
                    if cleaned and not any(cleaned.lower().startswith(b) for b in ('todo', '@', 'param', 'return', 'throws', 'copyright', 'license')):
                        intent = cleaned
                        break

            if not intent and inside_comment:
                for line in inside_comment.split('\n'):
                    cleaned = re.sub(r'^[/#*\s]+|[/*\s]+$', '', line).strip()
                    if cleaned and not any(cleaned.lower().startswith(b) for b in ('todo', '@')):
                        intent = cleaned
                        break

            if intent and len(intent) > 4 and not any(intent.lower().startswith(b) for b in ('todo', 'fixme')):
                fn_docs[fn] = intent[:100]

        return doc_context, fn_docs

    # ── Main public method ───────────────────────────────────────────

    def extract_features(self, tree, code_str: str, language: str):
        """this will extract sources, sinks, complexity, functions, classes, imports, and behavioral info."""
        features = {
            'sources':    [],
            'sinks':      [],
            'complexity': 0,
            # ── structural keys ──
            'functions':  [],
            'classes':    [],
            'imports':    [],
            # ── behavioral keys (NEW) ──
            'params_by_fn': {},
            'return_info':  {},
            'output_calls': [],
            'doc_context':  '',
            'fn_docs':      {},
        }
        
        lang_obj = self.parser_interface.get_language(language)
        if not lang_obj or language not in self.queries:
            return features

        # ── Existing sinks / sources / complexity extraction (UNCHANGED) ─
        try:
            from tree_sitter import Query, QueryCursor

            query   = Query(lang_obj, self.queries[language])
            cursor  = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
            
            code_bytes = code_str.encode('utf-8')
            
            for capture_name, nodes in captures.items():
                for node in nodes:
                    if capture_name == 'branch':
                        features['complexity'] += 1
                    elif capture_name == 'func':
                        func_name_bytes = code_bytes[node.start_byte:node.end_byte]
                        func_name = func_name_bytes.decode('utf-8', errors='ignore')
                        
                        if func_name in self.sources.get(language, set()):
                            features['sources'].append(func_name)
                        
                        if func_name in self.sinks.get(language, set()):
                            features['sinks'].append(func_name)
                        
        except Exception as e:
            print(f"Feature extraction error: {e}")

        # ── Structural extraction ────────────────────────────────────
        try:
            fns, cls = self._extract_struct_ast(tree, code_str, language)
            features['functions'] = fns
            features['classes']   = cls
        except Exception:
            pass  # best-effort

        try:
            features['imports'] = self._extract_imports_regex(code_str, language)
        except Exception:
            pass  # best-effort

        # ── Behavioral extraction (NEW) ──────────────────────────────
        try:
            features['params_by_fn'] = self._extract_params(code_str, language)
        except Exception:
            pass

        try:
            features['return_info'] = self._extract_returns(code_str, language, features['functions'])
        except Exception:
            pass

        try:
            features['output_calls'] = self._extract_output_calls(code_str, language)
        except Exception:
            pass

        try:
            features['fn_body_facts'] = self._extract_fn_body_facts(
                code_str, language, features.get('functions', []))
        except Exception:
            features['fn_body_facts'] = {}

        try:
            doc_context, fn_docs = self._extract_comments(
                code_str, language, features.get('functions', []))
            features['doc_context'] = doc_context
            features['fn_docs'] = fn_docs
        except Exception:
            features['doc_context'] = ""
            features['fn_docs'] = {}

        features['code'] = code_str
        return features


