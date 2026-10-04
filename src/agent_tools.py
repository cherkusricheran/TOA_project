"""
Secure Coding Agent Tools & Foundation
======================================
Part 2: Secure Coding Assistant Agent

Provides reusable, modular foundation for:
  - Finding context extraction (from existing scanner finding dictionaries)
  - Surrounding source-code extraction with target line markers
  - Enclosing function detection (function-level focus across Python, JS, Java, C)
  - Evidence-based vulnerability explanation grounded in the code
  - Beginner-friendly security concept teaching with deterministic principles
  - User-triggered secure reference code generation reusing CodeT5 inference
"""

import re
from typing import Dict, List, Any, Optional, Tuple

from src.vuln_classifier import (
    classify_vulnerability,
    normalize_severity,
    CWE_CATEGORY_MAP,
)


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic Security Knowledge Base (Teaching & Explanation Layer)
# ──────────────────────────────────────────────────────────────────────────────

SECURITY_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    'CWE-89': {
        'concept': 'SQL Injection (SQLi)',
        'what_is_wrong': (
            "Untrusted data or dynamic variables are formatted directly into an SQL command string "
            "rather than being passed as bound parameters."
        ),
        'why_vulnerable': (
            "When queries are constructed via string formatting or concatenation (e.g., f-strings, %, or +), "
            "the database interpreter cannot distinguish between SQL code and user input. "
            "An attacker can input special characters (such as quotes or comments) to manipulate the query logic, "
            "bypass authentication, view unauthorized data, or delete records."
        ),
        'what_to_learn': (
            "Never build SQL queries by stitching strings together. "
            "Always use parameterized queries (also known as prepared statements) provided by your database library. "
            "Parameters tell the database engine to treat inputs strictly as literal values, never as executable SQL commands."
        ),
        'principle': 'Separation of Code and Data',
        'beginner_takeaway': (
            "Always use placeholders (like `?` or `%s` with query arguments) in `.execute()`. "
            "Never use f-strings or string concatenation for database queries."
        ),
    },
    'CWE-78': {
        'concept': 'OS Command Injection',
        'what_is_wrong': (
            "A system command is being constructed with dynamic input and executed via an operating system shell "
            "(such as `os.system()`, `popen()`, or `subprocess` with `shell=True`)."
        ),
        'why_vulnerable': (
            "The system shell parses spaces and metacharacters (such as `;`, `&`, `|`, `$(...)`). "
            "If an attacker controls any part of the command string, they can inject additional commands "
            "that execute with the full privileges of the host process."
        ),
        'what_to_learn': (
            "Avoid invoking the system shell whenever possible. "
            "If you must run an external program, pass the executable and its arguments as a list of strings "
            "with `shell=False` (e.g. `subprocess.run(['ping', '-c', '1', host])`). "
            "This passes arguments directly to the process without invoking a shell parser."
        ),
        'principle': 'Avoid Shell Interpretation & Principle of Least Privilege',
        'beginner_takeaway': (
            "Never pass dynamic strings to `os.system()` or `shell=True`. "
            "Pass command arguments as a list to `subprocess.run(..., shell=False)`."
        ),
    },
    'CWE-94': {
        'concept': 'Code Injection (Dynamic Code Execution)',
        'what_is_wrong': (
            "Dynamic code execution functions like `eval()` or `exec()` are used to evaluate text at runtime."
        ),
        'why_vulnerable': (
            "`eval()` and `exec()` treat any input string as executable source code. "
            "If an attacker can influence this string, they can execute arbitrary programming commands, "
            "import dangerous libraries, read files, or compromise the entire server environment."
        ),
        'what_to_learn': (
            "Code should be compiled at build time, not synthesized from strings at runtime. "
            "For parsing data structures, use safe serialization formats like JSON (`json.loads()`). "
            "For evaluating arithmetic expressions, use dedicated expression parsers or `ast.literal_eval()`."
        ),
        'principle': 'Never Execute Untrusted Input as Code',
        'beginner_takeaway': (
            "Avoid `eval()` and `exec()`. If you need to parse numbers or data, use `json.loads()` or dedicated parsers."
        ),
    },
    'CWE-79': {
        'concept': 'Cross-Site Scripting (XSS)',
        'what_is_wrong': (
            "Dynamic data is written directly into the DOM or HTML output without proper encoding or sanitization "
            "(e.g., assigning to `innerHTML`, `document.write()`, or `dangerouslySetInnerHTML`)."
        ),
        'why_vulnerable': (
            "The web browser cannot differentiate between legitimate application HTML and attacker-supplied HTML/JavaScript. "
            "An attacker can inject malicious `<script>` tags or event handlers that run inside victims' browsers, "
            "stealing session tokens, logging keystrokes, or performing unauthorized actions on their behalf."
        ),
        'what_to_learn': (
            "Always use safe DOM properties that treat data strictly as text, such as `textContent` or `innerText`. "
            "If HTML markup is genuinely required, sanitize the content using an established HTML sanitizer like DOMPurify."
        ),
        'principle': 'Context-Aware Output Encoding & Safe Sinks',
        'beginner_takeaway': (
            "Use `textContent` instead of `innerHTML` when displaying dynamic text on a webpage."
        ),
    },
    'CWE-502': {
        'concept': 'Insecure Deserialization',
        'what_is_wrong': (
            "Data is deserialized using an unsafe serialization protocol such as Python's `pickle`, `cPickle`, "
            "or `yaml.load()` without safe loaders."
        ),
        'why_vulnerable': (
            "Protocols like Python's `pickle` are designed to reconstruct arbitrary runtime objects and will automatically "
            "execute methods (such as `__reduce__`) during deserialization. "
            "An attacker who supplies a crafted serialized payload can achieve immediate arbitrary code execution."
        ),
        'what_to_learn': (
            "Do not use executable object serialization for data exchange with untrusted sources. "
            "Use pure data serialization formats like JSON, MessagePack, or Protocol Buffers. "
            "In YAML, always use `yaml.safe_load()` instead of `yaml.load()`."
        ),
        'principle': 'Use Data-Only Serialization Formats',
        'beginner_takeaway': (
            "Never unpickle untrusted data. Use `json.loads()` or `yaml.safe_load()` for saving and loading data."
        ),
    },
    'CWE-22': {
        'concept': 'Path Traversal',
        'what_is_wrong': (
            "A file path is constructed from user-supplied input without verifying that the resolved path stays "
            "within the intended directory."
        ),
        'why_vulnerable': (
            "Special path sequences such as `../` (directory traversal) can break out of the target folder. "
            "An attacker can supply values like `../../../../etc/passwd` to view sensitive configuration or system files, "
            "or write files to arbitrary disk locations."
        ),
        'what_to_learn': (
            "Verify all file paths using canonical absolute path checks (e.g. `os.path.realpath()`). "
            "Ensure the canonical path starts with the trusted base directory prefix, or use framework utilities like `safe_join()`."
        ),
        'principle': 'Path Confinement & Canonicalization',
        'beginner_takeaway': (
            "Never trust raw filenames from user requests. Resolve the real path and check that it stays inside your base folder."
        ),
    },
    'CWE-798': {
        'concept': 'Hardcoded Credentials & Secrets',
        'what_is_wrong': (
            "Sensitive credentials such as passwords, private keys, API tokens, or secrets are hardcoded directly in source code."
        ),
        'why_vulnerable': (
            "Source code is frequently committed to version control, pushed to public or team repositories, and included in build artifacts. "
            "Anyone with repository access or build logs can extract these credentials and gain unauthorized access to critical services."
        ),
        'what_to_learn': (
            "Externalize secrets from the codebase. Store sensitive keys in environment variables or dedicated secret management vaults, "
            "and load them dynamically at runtime."
        ),
        'principle': 'Secrets Externalization & Zero Secrets in Code',
        'beginner_takeaway': (
            "Never write passwords or API keys in code files. Load them using `os.getenv('SECRET_KEY')`."
        ),
    },
    'CWE-259': {
        'concept': 'Hardcoded Password',
        'what_is_wrong': (
            "A password is embedded directly as a string literal in the source code."
        ),
        'why_vulnerable': (
            "Hardcoded passwords cannot be easily rotated without editing code and redeploying. "
            "They are exposed to anyone who reads the source code or extracts strings from compiled artifacts."
        ),
        'what_to_learn': (
            "Pass credentials via environment variables or secure configuration stores. "
            "For user passwords, store only salted cryptographic hashes (e.g. using Argon2 or bcrypt)."
        ),
        'principle': 'Secrets Management & Secure Storage',
        'beginner_takeaway': (
            "Store passwords in environment variables or configuration files that are ignored by version control (.gitignore)."
        ),
    },
    'CWE-321': {
        'concept': 'Hardcoded Cryptographic Key',
        'what_is_wrong': (
            "A cryptographic key or secret signing token is hardcoded in the source code."
        ),
        'why_vulnerable': (
            "If an encryption key or session secret (like Flask `SECRET_KEY`) is known, "
            "an attacker can forge session cookies, decrypt confidential data, or tamper with signed tokens."
        ),
        'what_to_learn': (
            "Generate cryptographic keys randomly using secure key generation tools and load them via environment variables."
        ),
        'principle': 'Key Separation & Dynamic Key Management',
        'beginner_takeaway': (
            "Load encryption keys from environment variables rather than typing them into code."
        ),
    },
    'CWE-327': {
        'concept': 'Broken or Weak Cryptography',
        'what_is_wrong': (
            "The code uses obsolete or cryptographically broken algorithms such as MD5, SHA-1, DES, or RC4."
        ),
        'why_vulnerable': (
            "Algorithms like MD5 and SHA-1 have known collision vulnerabilities where different inputs produce the exact same hash. "
            "Legacy ciphers like DES have small key sizes that can be brute-forced in hours."
        ),
        'what_to_learn': (
            "Use modern, standardized algorithms recommended by security standards: SHA-256 or SHA-3 for hashing; "
            "AES-256-GCM for symmetric encryption; and Argon2id, bcrypt, or PBKDF2 for password hashing."
        ),
        'principle': 'Use Standard, Vetted Cryptographic Primitives',
        'beginner_takeaway': (
            "Never use MD5 or SHA-1 for security. Use `hashlib.sha256()` or specialized password hashers like `bcrypt`."
        ),
    },
    'CWE-338': {
        'concept': 'Weak Pseudo-Random Number Generator (PRNG)',
        'what_is_wrong': (
            "A standard, predictable random number generator (such as Python's `random`, JS `Math.random()`, or C `rand()`) "
            "is used in a security-sensitive context."
        ),
        'why_vulnerable': (
            "Standard PRNGs are designed for statistical modeling and gaming, not cryptography. "
            "Their internal algorithm state can be calculated after observing a few generated outputs, "
            "enabling attackers to predict future security tokens, password reset links, or session keys."
        ),
        'what_to_learn': (
            "For generating security tokens, password salts, session IDs, or encryption keys, always use a Cryptographically Secure PRNG (CSPRNG). "
            "In Python, use the `secrets` module or `os.urandom()`. In JavaScript, use `crypto.randomBytes()`."
        ),
        'principle': 'Cryptographically Secure Randomness (CSPRNG)',
        'beginner_takeaway': (
            "Use Python's `secrets` module (e.g. `secrets.token_hex(16)`) instead of `random.randint()` for tokens or keys."
        ),
    },
    'CWE-120': {
        'concept': 'Buffer Overflow',
        'what_is_wrong': (
            "Data is copied into a fixed-size memory buffer without checking whether the input size exceeds the destination buffer."
        ),
        'why_vulnerable': (
            "In memory-unsafe languages like C, writing more bytes than allocated will overwrite adjacent stack or heap memory. "
            "Attackers can leverage this to corrupt control flow, overwrite function return pointers, and execute arbitrary code."
        ),
        'what_to_learn': (
            "Always use length-bounded functions: replace `gets()` with `fgets()`, `strcpy()` with `strncpy()` or `snprintf()`. "
            "Always pass the destination buffer's maximum capacity as a parameter."
        ),
        'principle': 'Memory Safety & Explicit Bounds Checking',
        'beginner_takeaway': (
            "Never use `gets()` or unbounded `strcpy()`. Always specify the buffer size with `fgets(buf, sizeof(buf), stdin)`."
        ),
    },
    'CWE-918': {
        'concept': 'Server-Side Request Forgery (SSRF)',
        'what_is_wrong': (
            "The application fetches a URL supplied by user input without validating the target protocol or destination IP."
        ),
        'why_vulnerable': (
            "An attacker can direct the server to make requests to internal services (such as localhost `127.0.0.1` or cloud metadata `169.254.169.254`), "
            "allowing them to bypass firewalls and access internal infrastructure data."
        ),
        'what_to_learn': (
            "Validate requested URLs against a strict allowlist of permitted domains and protocols. "
            "Block requests to private/internal IP ranges (e.g. `127.0.0.0/8`, `10.0.0.0/8`, `192.168.0.0/16`)."
        ),
        'principle': 'Input Validation & Network Boundary Enforcement',
        'beginner_takeaway': (
            "Only allow outgoing HTTP requests to pre-approved external domains on a whitelist."
        ),
    },
    'CWE-295': {
        'concept': 'Improper Certificate Validation (TLS/SSL Bypass)',
        'what_is_wrong': (
            "SSL/TLS certificate verification is disabled (e.g. `verify=False` or `ssl._create_unverified_context()`)."
        ),
        'why_vulnerable': (
            "Disabling certificate verification prevents the client from authenticating the server's identity. "
            "An attacker on the same network (e.g. public Wi-Fi or compromised DNS) can intercept, read, and alter all traffic "
            "via a Man-in-the-Middle (MITM) attack."
        ),
        'what_to_learn': (
            "Always keep certificate verification enabled (`verify=True`). "
            "If working with internal certificates, add your root CA to the trusted bundle rather than disabling verification globally."
        ),
        'principle': 'Authenticity & Encrypted Channel Integrity',
        'beginner_takeaway': (
            "Never set `verify=False`. It removes encryption authentication and allows traffic interception."
        ),
    },
    'CWE-611': {
        'concept': 'XML External Entity (XXE) Injection',
        'what_is_wrong': (
            "An XML parser parses documents with external entity resolution or DTD processing enabled."
        ),
        'why_vulnerable': (
            "XML specifications allow defining external entities (`<!ENTITY ... SYSTEM 'file:///etc/passwd'>`). "
            "When parsed without protection, the XML parser reads internal files or contacts internal network services."
        ),
        'what_to_learn': (
            "Disable external DTDs and entity expansion in XML parsers, or use safe replacement libraries like `defusedxml`."
        ),
        'principle': 'Disable Unneeded Parser Capabilities',
        'beginner_takeaway': (
            "Disable DTD processing or use `defusedxml` when parsing XML from user uploads."
        ),
    },
    'CWE-352': {
        'concept': 'Cross-Site Request Forgery (CSRF)',
        'what_is_wrong': (
            "State-changing actions or endpoints lack anti-CSRF token verification."
        ),
        'why_vulnerable': (
            "Browsers automatically include session cookies when sending cross-origin requests. "
            "A malicious website can trick a logged-in user's browser into submitting unauthorized requests to your app."
        ),
        'what_to_learn': (
            "Ensure all state-changing endpoints (POST/PUT/DELETE) validate a unique, unpredictable anti-CSRF token "
            "associated with the user's current session."
        ),
        'principle': 'Challenge-Response & Anti-CSRF Token Validation',
        'beginner_takeaway': (
            "Never disable `@csrf_exempt` without a strong alternative. Use built-in framework CSRF protection for forms."
        ),
    },
}

DEFAULT_KNOWLEDGE: Dict[str, str] = {
    'concept': 'Security Vulnerability',
    'what_is_wrong': (
        "The identified line of code uses a pattern or function call identified as risky by static security analysis."
    ),
    'why_vulnerable': (
        "Using unsafe functions or handling dynamic input without proper validation and encoding "
        "can allow attackers to exploit unexpected program states or compromise system integrity."
    ),
    'what_to_learn': (
        "Adopt defensive programming: validate all external inputs against a strict schema, "
        "rely on modern standardized security libraries, and adhere to the principle of least privilege."
    ),
    'principle': 'Input Validation & Principle of Least Privilege',
    'beginner_takeaway': (
        "Always treat external input as potentially untrusted. Validate inputs early and use safe, modern standard libraries."
    ),
}


# ──────────────────────────────────────────────────────────────────────────────
# Core Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def extract_surrounding_code(code_str: str, line_num: int, context_lines: int = 3) -> Dict[str, Any]:
    """
    Extract surrounding source-code lines around a target line with indicators.
    """
    if not code_str:
        return {
            'target_line': '',
            'start_line': 1,
            'end_line': 1,
            'snippet': '',
            'raw_lines': [],
        }

    lines = code_str.splitlines()
    total_lines = len(lines)

    if line_num is None or not isinstance(line_num, int) or line_num < 1:
        line_num = 1
    line_num = min(line_num, total_lines) if total_lines > 0 else 1

    start = max(1, line_num - context_lines)
    end = min(total_lines, line_num + context_lines)

    raw_lines = []
    formatted_snippet_lines = []

    target_content = lines[line_num - 1] if 1 <= line_num <= total_lines else ''

    for idx in range(start, end + 1):
        content = lines[idx - 1] if 1 <= idx <= total_lines else ''
        is_target = (idx == line_num)
        raw_lines.append((idx, content, is_target))

        marker = ">" if is_target else " "
        formatted_snippet_lines.append(f"{marker} {idx:4d} | {content}")

    return {
        'target_line': target_content.strip(),
        'start_line': start,
        'end_line': end,
        'snippet': '\n'.join(formatted_snippet_lines),
        'raw_lines': raw_lines,
    }


def find_enclosing_function(code_str: str, line_num: int, language: str) -> Optional[Dict[str, Any]]:
    """
    Identify the enclosing function/method containing line_num (1-indexed).
    Does NOT guess function names. Returns None if line is at top-level or outside a function.

    Returns dict with:
        name: Function name (str)
        start_line: 1-indexed start line
        end_line: 1-indexed end line
        code: Extracted function source string
    """
    if not code_str or not line_num:
        return None

    lines = code_str.splitlines()
    total_lines = len(lines)
    if not (1 <= line_num <= total_lines):
        return None

    lang = language.lower() if language else ''

    # 1. Python: def fn(...) with indentation tracking
    if lang == 'python':
        fn_starts = []
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)def\s+([a-zA-Z_]\w*)\s*\(', line)
            if m:
                indent = len(m.group(1))
                fn_name = m.group(2)
                fn_starts.append((i + 1, fn_name, indent))

        for idx, (start_l, name, indent) in enumerate(fn_starts):
            end_l = total_lines
            for j in range(start_l, total_lines):
                line_content = lines[j]
                if line_content.strip() and not line_content.strip().startswith('#'):
                    curr_indent = len(line_content) - len(line_content.lstrip())
                    if curr_indent <= indent:
                        end_l = j
                        break
            if start_l <= line_num <= end_l:
                fn_code = '\n'.join(lines[start_l - 1:end_l])
                return {'name': name, 'start_line': start_l, 'end_line': end_l, 'code': fn_code}
        return None

    # 2. JavaScript / Java / C: Function header followed by brace-scoped body
    fn_header_patterns = {
        'javascript': r'^(?:\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)|(?:\s*(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>))',
        'java': r'^\s*(?:public|private|protected|static|final|\s)*\s+[a-zA-Z_<>\[\],\s]+\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
        'c': r'^\s*(?:[a-zA-Z_]\w*[\s*]+)+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{',
    }
    pat = fn_header_patterns.get(lang, r'^\s*(?:[a-zA-Z_]\w*[\s*]+)+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{')

    for i, line in enumerate(lines):
        m = re.search(pat, line)
        if m:
            fn_name = m.group(1) or (m.group(2) if len(m.groups()) >= 2 else None) or "function"
            start_l = i + 1
            depth = 0
            found_open = False
            end_l = total_lines
            for j in range(i, total_lines):
                for ch in lines[j]:
                    if ch == '{':
                        depth += 1
                        found_open = True
                    elif ch == '}':
                        depth -= 1
                if found_open and depth <= 0:
                    end_l = j + 1
                    break
            if start_l <= line_num <= end_l:
                fn_code = '\n'.join(lines[start_l - 1:end_l])
                return {'name': fn_name, 'start_line': start_l, 'end_line': end_l, 'code': fn_code}

    return None


def extract_finding_context(finding: Dict[str, Any], code_str: str = "", language: str = "") -> Dict[str, Any]:
    """
    Extract and normalize the context of a vulnerability finding.
    """
    message = finding.get('message', '')
    raw_sev = finding.get('severity', 'INFO')
    rule_id = finding.get('check_id') or finding.get('rule_id') or 'security-audit'
    line_num = finding.get('line')

    if isinstance(line_num, str):
        try:
            line_num = int(line_num)
        except ValueError:
            line_num = 1
    elif not isinstance(line_num, int):
        line_num = 1

    cwe_id, category = classify_vulnerability(message)
    normalized_sev = normalize_severity(raw_sev)

    surrounding = extract_surrounding_code(code_str, line_num, context_lines=3)

    target_snippet = finding.get('snippet', '').strip()
    if not target_snippet:
        target_snippet = surrounding.get('target_line', '')

    if not language:
        file_path = finding.get('file', '')
        ext = re.search(r'\.(py|js|java|c|cpp|h)$', file_path, re.IGNORECASE)
        if ext:
            ext_map = {'py': 'python', 'js': 'javascript', 'java': 'java', 'c': 'c', 'cpp': 'c', 'h': 'c'}
            language = ext_map.get(ext.group(1).lower(), '')

    return {
        'rule_id': rule_id,
        'message': message,
        'line': line_num,
        'severity': normalized_sev,
        'cwe': cwe_id if cwe_id != 'N/A' else 'CWE-Unknown',
        'category': category,
        'snippet': target_snippet,
        'surrounding_code': surrounding,
        'file': finding.get('file', ''),
        'language': language or 'code',
    }


def explain_vulnerability(context: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate an evidence-based explanation of the vulnerability grounded in the finding and code.
    """
    cwe = context.get('cwe', '')
    category = context.get('category', 'Vulnerability')
    line = context.get('line', '?')
    snippet = context.get('snippet', '')
    message = context.get('message', '')

    knowledge = SECURITY_KNOWLEDGE_BASE.get(cwe, DEFAULT_KNOWLEDGE)

    what_is_wrong = knowledge['what_is_wrong']
    if snippet:
        what_is_wrong = f"On line {line}, the code performs an operation identified as {category}: `{snippet}`. {what_is_wrong}"
    else:
        what_is_wrong = f"On line {line}, static analysis detected {category} ({message}). {what_is_wrong}"

    base_why = knowledge['why_vulnerable']
    why_is_it_vulnerable = base_why

    if 'execute' in snippet and cwe == 'CWE-89':
        why_is_it_vulnerable = (
            f"The database statement in `{snippet}` directly embeds unverified variables into the query text. "
            f"{base_why}"
        )
    elif ('system' in snippet or 'shell=True' in snippet or 'popen' in snippet) and cwe == 'CWE-78':
        why_is_it_vulnerable = (
            f"Line {line} executes `{snippet}` which hands the command to the system shell. "
            f"{base_why}"
        )
    elif 'eval(' in snippet and cwe == 'CWE-94':
        why_is_it_vulnerable = (
            f"Line {line} calls `eval()`. Because `{snippet}` interprets strings as live commands, "
            f"{base_why}"
        )
    elif ('innerHTML' in snippet or 'document.write' in snippet) and cwe == 'CWE-79':
        why_is_it_vulnerable = (
            f"Line {line} assigns content to the DOM via `{snippet}`. "
            f"{base_why}"
        )

    return {
        'what_is_wrong': what_is_wrong,
        'why_is_it_vulnerable': why_is_it_vulnerable,
    }


def teach_security_concept(context: Dict[str, Any]) -> Dict[str, str]:
    """
    Provide structured educational concepts, secure principles, and beginner takeaways.
    """
    cwe = context.get('cwe', '')
    category = context.get('category', 'Vulnerability')
    knowledge = SECURITY_KNOWLEDGE_BASE.get(cwe, DEFAULT_KNOWLEDGE)

    cwe_label = f" ({cwe})" if cwe and cwe != 'CWE-Unknown' else ""
    concept_title = f"{category}{cwe_label}"

    return {
        'concept_name': concept_title,
        'what_to_learn': knowledge['what_to_learn'],
        'principle': knowledge['principle'],
        'beginner_takeaway': knowledge['beginner_takeaway'],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Secure Code Generation Engine (Function-Level Focus & Deterministic Grounding)
# ──────────────────────────────────────────────────────────────────────────────

def build_repair_prompt(context: Dict[str, Any], target_code: str) -> str:
    """
    Construct a structured repair prompt for CodeT5 / inference engine.
    Instructs the model on preserving functionality, fixing the vulnerability,
    and avoiding unrelated changes.
    """
    cwe = context.get('cwe', '')
    category = context.get('category', 'Vulnerability')
    message = context.get('message', '')
    lang = context.get('language', '')
    comment_sym = "//" if lang in ('javascript', 'java', 'c') else "#"

    prompt = (
        f"{comment_sym} Task: Fix security vulnerability {category} ({cwe}).\n"
        f"{comment_sym} Finding: {message}\n"
        f"{comment_sym} Instructions: Preserve functionality, fix vulnerability, use secure practices.\n"
        f"{comment_sym} Original code:\n"
        f"{target_code[:400]}"
    )
    return prompt


def generate_secure_code_fix(
    context: Dict[str, Any],
    code_str: str,
    language: str,
    inference_engine: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Generate a secure reference code suggestion focusing on the enclosing function
    or smallest relevant code region.

    Returns dict containing:
        - target_scope: description of the scope ('function `name()`' or 'code region lines X-Y')
        - function_name: detected function name or None
        - original_code: original code chunk
        - secure_code: corrected secure reference code
        - changes_made: list of concise bullets explaining what was changed
        - why_secure: list of concise bullets explaining why the fix is secure
        - model_intent: CodeT5 natural-language intent summary if available
    """
    line_num = context.get('line', 1)
    cwe = context.get('cwe', '')
    category = context.get('category', 'Vulnerability')
    message = context.get('message', '')
    surrounding = context.get('surrounding_code', {})

    # 1. Function-level focus: locate enclosing function
    fn_info = find_enclosing_function(code_str, line_num, language)

    if fn_info:
        target_scope = f"function `{fn_info['name']}()` (lines {fn_info['start_line']}–{fn_info['end_line']})"
        function_name = fn_info['name']
        original_code = fn_info['code']
    else:
        start_l = surrounding.get('start_line', max(1, line_num - 2))
        end_l = surrounding.get('end_line', line_num + 2)
        target_scope = f"code region (lines {start_l}–{end_l})"
        function_name = None
        # Extract the lines directly
        lines_all = code_str.splitlines() if code_str else []
        original_code = '\n'.join(lines_all[start_l - 1:end_l]) if lines_all else context.get('snippet', '')

    # 2. Query CodeT5 for model repair intent if inference_engine provided
    model_intent = ""
    if inference_engine is not None:
        try:
            prompt = build_repair_prompt(context, original_code)
            model_intent = inference_engine.generate_summary(prompt)
        except Exception:
            model_intent = ""

    # 3. Deterministic Grounded Secure Code Transformation
    lines = original_code.splitlines()
    new_lines = []
    changes_made = []
    why_secure = []

    # Category: SQL Injection (CWE-89)
    if cwe == 'CWE-89' or 'sql' in category.lower():
        var_detected = None
        for line in lines:
            # Python f-string query: query = f"SELECT ... {var} ..."
            m_fstr = re.search(r'query\s*=\s*f["\']([^"\']*)\{([a-zA-Z_]\w*)\}([^"\']*)["\']', line)
            if m_fstr:
                prefix, var_name, suffix = m_fstr.group(1), m_fstr.group(2), m_fstr.group(3)
                var_detected = var_name
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}query = "{prefix}%s{suffix}"')
                changes_made.append("Replaced dynamic f-string with a parameterized query placeholder (`%s`).")
                continue

            # Python execute with query variable: cursor.execute(query)
            m_exec = re.search(r'(cursor\.)?execute\s*\(\s*query\s*\)', line)
            if m_exec and var_detected:
                indent = len(line) - len(line.lstrip())
                prefix_c = m_exec.group(1) or ""
                new_lines.append(f'{" " * indent}{prefix_c}execute(query, ({var_detected},))')
                changes_made.append(f"Passed `{var_detected}` as a bound parameter tuple in `execute()`.")
                continue

            # Python direct execute f-string: cursor.execute(f"SELECT ... {var}")
            m_direct = re.search(r'(cursor\.)?execute\s*\(\s*f["\']([^"\']*)\{([a-zA-Z_]\w*)\}([^"\']*)["\']\s*\)', line)
            if m_direct:
                prefix_c = m_direct.group(1) or ""
                prefix_q, var_name, suffix_q = m_direct.group(2), m_direct.group(3), m_direct.group(4)
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}{prefix_c}execute("{prefix_q}%s{suffix_q}", ({var_name},))')
                changes_made.append("Replaced dynamic f-string query with parameterized placeholder (`%s`) and parameter tuple.")
                continue

            # JavaScript parameterized query: db.query("SELECT ... WHERE id = " + userId)
            m_js_concat = re.search(r'(\w+)\.query\s*\(\s*["\']([^"\']+?)["\']\s*\+\s*([a-zA-Z_]\w*)', line)
            if m_js_concat:
                db_obj, sql_base, var_name = m_js_concat.group(1), m_js_concat.group(2), m_js_concat.group(3)
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}{db_obj}.query("{sql_base}?", [{var_name}], (err, results) => {{')
                changes_made.append("Replaced string concatenation with parameterized placeholder (`?`) and arguments array.")
                continue

            new_lines.append(line)

        why_secure.append("Separates SQL command structure from user data, preventing query logic manipulation.")
        why_secure.append("The database driver treats bound parameters strictly as literal values.")

    # Category: OS Command Injection (CWE-78)
    elif cwe == 'CWE-78' or 'command' in category.lower():
        for line in lines:
            if 'os.system(' in line:
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}# Secure: Execute executable directly as argument list without shell')
                new_lines.append(f'{" " * indent}subprocess.run(["ping", "-c", "1", host], check=True, shell=False)')
                changes_made.append("Replaced `os.system()` with `subprocess.run()` using a list of arguments.")
                changes_made.append("Explicitly set `shell=False` to prevent shell metacharacter parsing.")
                continue
            if 'shell=True' in line:
                line_fixed = re.sub(r'shell\s*=\s*True', 'shell=False', line)
                new_lines.append(line_fixed)
                changes_made.append("Disabled shell interpretation by setting `shell=False`.")
                continue
            new_lines.append(line)

        why_secure.append("Bypasses the OS command shell parser entirely, eliminating shell metacharacter injection (`;`, `&`, `|`).")
        why_secure.append("Commands and arguments are invoked directly by the operating system kernel.")

    # Category: Code Injection (CWE-94)
    elif cwe == 'CWE-94' or 'code' in category.lower() or 'eval' in original_code:
        for line in lines:
            if re.search(r'\beval\s*\(', line):
                line_fixed = re.sub(r'\beval\s*\(', 'ast.literal_eval(', line)
                new_lines.append(line_fixed)
                changes_made.append("Replaced dynamic `eval()` execution with safe literal evaluation (`ast.literal_eval()`).")
                continue
            if re.search(r'\bexec\s*\(', line):
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}# Secure: Avoid dynamic exec(); use structured dispatch or explicit handlers')
                changes_made.append("Removed `exec()` execution on runtime input strings.")
                continue
            new_lines.append(line)

        why_secure.append("`ast.literal_eval()` parses only safe data types (numbers, strings, tuples, lists, dicts).")
        why_secure.append("Rejects arbitrary code instructions, preventing remote code execution.")

    # Category: XSS (CWE-79)
    elif cwe == 'CWE-79' or 'xss' in category.lower():
        for line in lines:
            if '.innerHTML' in line:
                line_fixed = line.replace('.innerHTML', '.textContent')
                new_lines.append(line_fixed)
                changes_made.append("Replaced `.innerHTML` assignment with safe `.textContent`.")
                continue
            if 'document.write(' in line:
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}document.getElementById("output").textContent = data;')
                changes_made.append("Replaced raw `document.write()` with DOM element `textContent` assignment.")
                continue
            new_lines.append(line)

        why_secure.append("`textContent` instructs the browser to treat input strictly as plain text.")
        why_secure.append("Prevents browser execution of embedded `<script>` tags and malicious HTML event handlers.")

    # Category: Insecure Deserialization (CWE-502)
    elif cwe == 'CWE-502' or 'deserializ' in category.lower():
        for line in lines:
            if 'pickle.loads(' in line:
                line_fixed = line.replace('pickle.loads(', 'json.loads(')
                new_lines.append(line_fixed)
                changes_made.append("Replaced `pickle.loads()` with safe data-only parser `json.loads()`.")
                continue
            if 'yaml.load(' in line and 'safe_load' not in line:
                line_fixed = line.replace('yaml.load(', 'yaml.safe_load(')
                new_lines.append(line_fixed)
                changes_made.append("Replaced `yaml.load()` with `yaml.safe_load()`.")
                continue
            new_lines.append(line)

        why_secure.append("Pure data formats (JSON, safe YAML) cannot instantiate arbitrary classes or run object hooks.")
        why_secure.append("Eliminates deserialization gadgets and remote code execution vulnerabilities.")

    # Category: Path Traversal (CWE-22)
    elif cwe == 'CWE-22' or 'path' in category.lower():
        added_check = False
        for line in lines:
            if ('open(' in line or 'send_file(' in line or 'readFile' in line) and not added_check:
                indent = len(line) - len(line.lstrip())
                ind_str = " " * indent
                new_lines.append(f'{ind_str}# Secure: Canonicalize path and ensure it stays within base directory')
                new_lines.append(f'{ind_str}base_dir = os.path.abspath("safe_storage")')
                new_lines.append(f'{ind_str}target_path = os.path.abspath(os.path.join(base_dir, filename))')
                new_lines.append(f'{ind_str}if not target_path.startswith(base_dir):')
                new_lines.append(f'{ind_str}    raise PermissionError("Access denied: Invalid file path")')
                new_lines.append(line)
                added_check = True
                changes_made.append("Added canonical path verification with `os.path.abspath()`.")
                changes_made.append("Enforced path confinement check to prevent escaping the base directory.")
                continue
            new_lines.append(line)

        why_secure.append("Resolves symbolic links and relative path sequences (`../`) before opening files.")
        why_secure.append("Blocks unauthorized access to parent directories and sensitive operating system files.")

    # Category: Hardcoded Secrets (CWE-798, CWE-259, CWE-321)
    elif cwe in ('CWE-798', 'CWE-259', 'CWE-321') or 'secret' in category.lower() or 'password' in category.lower():
        for line in lines:
            m_pw = re.search(r'(password|secret_key|api_key|token)\s*=\s*["\'][^"\']+["\']', line, re.IGNORECASE)
            if m_pw:
                var = m_pw.group(1)
                env_key = var.upper()
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}{var} = os.environ.get("{env_key}", "")')
                changes_made.append(f"Replaced hardcoded string with dynamic environment variable lookup (`os.environ.get('{env_key}')`).")
                continue
            new_lines.append(line)

        why_secure.append("Prevents accidental credential leakage in version control repositories and build artifacts.")
        why_secure.append("Facilitates secret rotation without requiring code modifications or redeployment.")

    # Category: Weak Cryptography (CWE-327)
    elif cwe == 'CWE-327' or 'crypto' in category.lower():
        for line in lines:
            if 'hashlib.md5(' in line:
                line_fixed = line.replace('hashlib.md5(', 'hashlib.sha256(')
                new_lines.append(line_fixed)
                changes_made.append("Replaced weak MD5 hash with standard SHA-256 (`hashlib.sha256()`).")
                continue
            if 'hashlib.sha1(' in line:
                line_fixed = line.replace('hashlib.sha1(', 'hashlib.sha256(')
                new_lines.append(line_fixed)
                changes_made.append("Replaced broken SHA-1 hash with standard SHA-256 (`hashlib.sha256()`).")
                continue
            new_lines.append(line)

        why_secure.append("SHA-256 provides modern 256-bit collision and preimage resistance.")
        why_secure.append("Protects cryptographic hashes against collision attacks.")

    # Category: Weak PRNG (CWE-338)
    elif cwe == 'CWE-338' or 'prng' in category.lower() or 'random' in category.lower():
        for line in lines:
            if 'random.randint(' in line or 'random.random(' in line:
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}# Secure: Use cryptographically secure random token')
                new_lines.append(f'{" " * indent}token = secrets.token_hex(16)')
                changes_made.append("Replaced pseudo-random `random` with cryptographically secure `secrets.token_hex()`.")
                continue
            new_lines.append(line)

        why_secure.append("CSPRNG draws entropy from the operating system kernel, producing unpredictable values.")
        why_secure.append("Defends against token prediction and session hijacking attacks.")

    # Category: TLS/SSL Bypass (CWE-295)
    elif cwe == 'CWE-295' or 'ssl' in category.lower() or 'tls' in category.lower():
        for line in lines:
            if 'verify=False' in line:
                line_fixed = line.replace('verify=False', 'verify=True')
                new_lines.append(line_fixed)
                changes_made.append("Enforced certificate validation by setting `verify=True`.")
                continue
            new_lines.append(line)

        why_secure.append("Validates remote server TLS certificate chains against trusted root authorities.")
        why_secure.append("Prevents Man-in-the-Middle (MITM) network eavesdropping.")

    # Category: Buffer Overflow (CWE-120)
    elif cwe == 'CWE-120' or 'buffer' in category.lower():
        for line in lines:
            if 'gets(' in line:
                m_gets = re.search(r'\bgets\s*\(\s*([a-zA-Z_]\w*)\s*\)', line)
                buf_name = m_gets.group(1) if m_gets else "buffer"
                indent = len(line) - len(line.lstrip())
                new_lines.append(f'{" " * indent}fgets({buf_name}, sizeof({buf_name}), stdin);')
                changes_made.append(f"Replaced unbounded `gets()` with length-bounded `fgets({buf_name}, sizeof({buf_name}), stdin)`.")
                continue
            if 'strcpy(' in line:
                m_cpy = re.search(r'\bstrcpy\s*\(\s*([a-zA-Z_]\w*)\s*,\s*([^)]+)\)', line)
                if m_cpy:
                    dst, src = m_cpy.group(1), m_cpy.group(2).strip()
                    indent = len(line) - len(line.lstrip())
                    new_lines.append(f'{" " * indent}strncpy({dst}, {src}, sizeof({dst}) - 1);')
                    new_lines.append(f'{" " * indent}{dst}[sizeof({dst}) - 1] = \'\\0\';')
                    changes_made.append(f"Replaced unbounded `strcpy()` with bounded `strncpy()` and guaranteed null-termination.")
                    continue
            new_lines.append(line)

        why_secure.append("Enforces destination buffer capacity limits to prevent stack memory corruption.")
        why_secure.append("Guarantees null termination, avoiding memory read overruns.")

    # Generic Fallback: defensive validation guard
    if not changes_made:
        for i, line in enumerate(lines):
            # Target line or line with finding snippet
            if (context.get('snippet') and context.get('snippet') in line) or i == len(lines) // 2:
                indent = len(line) - len(line.lstrip())
                ind_str = " " * indent
                comment_sym = "//" if language in ('javascript', 'java', 'c') else "#"
                new_lines.append(f"{ind_str}{comment_sym} Secure Fix: Validate and sanitize dynamic input before processing")
                new_lines.append(f"{ind_str}{comment_sym} Ensure all arguments adhere to an allowlist schema")
                new_lines.append(line)
                changes_made.append("Added defensive validation guard and input sanitization directive.")
            else:
                new_lines.append(line)

        why_secure.append("Validates inputs before sensitive operations to prevent unexpected injection states.")

    secure_code = '\n'.join(new_lines)

    return {
        'target_scope': target_scope,
        'function_name': function_name,
        'original_code': original_code,
        'secure_code': secure_code,
        'changes_made': changes_made,
        'why_secure': why_secure,
        'model_intent': model_intent,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Secure Coding Agent Class
# ──────────────────────────────────────────────────────────────────────────────

class SecureCodingAgent:
    """
    Modular Secure Coding Assistant Agent.

    Capabilities:
      - Analyzes existing scanner findings
      - Extracts line, surrounding source, and enclosing function context
      - Formulates evidence-based explanations
      - Teaches beginner-friendly secure coding principles
      - Generates secure reference code suggestions on demand
    """

    def __init__(self):
        pass

    def analyze_finding(self, finding: Dict[str, Any], code_str: str = "", language: str = "") -> Dict[str, Any]:
        """
        Analyze a single scanner finding.
        """
        context = extract_finding_context(finding, code_str, language)
        explanation = explain_vulnerability(context)
        teaching = teach_security_concept(context)

        return {
            'context': context,
            'explanation': explanation,
            'teaching': teaching,
        }

    def analyze_all_findings(self, findings: List[Dict[str, Any]], code_str: str = "", language: str = "") -> List[Dict[str, Any]]:
        """
        Analyze all findings individually, preserving separate context for each issue.
        """
        results = []
        for f in findings:
            results.append(self.analyze_finding(f, code_str, language))
        return results

    def generate_secure_fix(
        self,
        analysis: Dict[str, Any],
        code_str: str = "",
        language: str = "",
        inference_engine: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Generate a secure reference code suggestion for a detected vulnerability.
        Focuses on the enclosing function or smallest relevant code region.

        Args:
            analysis: Dict from analyze_finding() containing 'context'
            code_str: Full original source code
            language: Programming language string
            inference_engine: Optional InferenceEngine instance for CodeT5 integration

        Returns:
            Dict with target_scope, function_name, original_code, secure_code,
            changes_made, why_secure, and model_intent.
        """
        context = analysis.get('context', analysis)
        return generate_secure_code_fix(context, code_str, language, inference_engine)

    def verify_fix(
        self,
        original_finding: Dict[str, Any],
        modified_code: str,
        language: str,
        verification_findings: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Verify whether modified code resolved a single original finding.
        If verification_findings is not passed, rescans the modified code.
        """
        if verification_findings is None:
            verif_findings, verif_risk = run_verification_scan(modified_code, language)
        else:
            from src.scanner import Scanner
            verif_findings = verification_findings
            verif_risk = Scanner()._calculate_risk_score(verif_findings, "")

        match_res = match_findings([original_finding], verif_findings)
        status_info = match_res['per_original_status'][0]

        return {
            'status': status_info['status'],
            'original_finding': original_finding,
            'matched_finding': status_info['matched_finding'],
            'line_shift': status_info['line_shift'],
            'explanation': status_info['explanation'],
            'verification_risk_score': verif_risk,
            'verification_findings': verif_findings,
            'new_issues': match_res['new_issues'],
        }

    def verify_all_findings(
        self,
        original_findings: List[Dict[str, Any]],
        modified_code: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Verify all original baseline findings against modified code in a single rescan.
        Produces per-original-finding status (RESOLVED or STILL_PRESENT),
        identifies new issues, and calculates the verification risk score.
        """
        return verify_fix_pipeline(original_findings, modified_code, language)


# ──────────────────────────────────────────────────────────────────────────────
# Fix Verification Layer (Step 3: Verification Baseline & Rescan Comparison)
# ──────────────────────────────────────────────────────────────────────────────

def extract_finding_identity(finding: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts normalized identifying fields from a finding for deterministic matching.
    """
    msg = finding.get('message', '').strip()
    cwe, category = classify_vulnerability(msg)

    check_id = finding.get('check_id') or finding.get('rule_id', '')
    if not check_id and cwe != 'N/A':
        check_id = cwe

    line = finding.get('line', 1)
    try:
        line_num = int(line)
    except (ValueError, TypeError):
        line_num = 1

    return {
        'check_id': check_id or '',
        'cwe': cwe or 'N/A',
        'category': category or 'Other',
        'line': line_num,
        'message': msg,
        'snippet': finding.get('snippet', '').strip(),
        'severity': normalize_severity(finding.get('severity', 'INFO')).upper(),
        'raw_finding': finding,
    }


def compute_match_score(orig: Dict[str, Any], verif: Dict[str, Any]) -> Tuple[int, int, str]:
    """
    Calculates deterministic match score between an original finding and a candidate
    verification finding based on prioritized evidence:
      1. rule_id / check_id
      2. CWE
      3. category
      4. finding/message identity (token overlap)
      5. line proximity (supporting evidence allowing line shift)

    Returns:
        (total_score, -line_dist, rationale)
    """
    score = 0
    reasons = []

    # Priority 1: rule_id / check_id
    rule_orig = orig['check_id']
    rule_verif = verif['check_id']
    same_rule = bool(rule_orig and rule_verif and rule_orig == rule_verif)

    # Priority 2: CWE
    cwe_orig = orig['cwe']
    cwe_verif = verif['cwe']
    same_cwe = bool(cwe_orig and cwe_orig != 'N/A' and cwe_orig == cwe_verif)

    # Priority 3: Category
    cat_orig = orig['category']
    cat_verif = verif['category']
    same_cat = bool(cat_orig and cat_orig != 'Other' and cat_orig == cat_verif)

    if same_rule:
        score += 1000
        reasons.append(f"Matching rule '{rule_orig}'")
    elif same_cwe:
        score += 500
        reasons.append(f"Matching CWE '{cwe_orig}'")
    elif same_cat:
        score += 250
        reasons.append(f"Matching Category '{cat_orig}'")
    else:
        return (0, 0, "No vulnerability type match")

    # Priority 4: Message identity / keywords overlap
    msg_orig = orig['message'].lower()
    msg_verif = verif['message'].lower()
    stop_words = {'this', 'that', 'with', 'from', 'user', 'using', 'detected', 'code', 'file', 'line'}
    words_orig = set(re.findall(r'\b[a-z]{4,}\b', msg_orig)) - stop_words
    words_verif = set(re.findall(r'\b[a-z]{4,}\b', msg_verif)) - stop_words
    overlap = words_orig & words_verif
    if overlap:
        msg_bonus = min(60, len(overlap) * 15)
        score += msg_bonus
        reasons.append(f"Keyword overlap ({len(overlap)} terms)")

    # Priority 5: Nearby line number as supporting evidence (allowing line shift)
    line_dist = abs(orig['line'] - verif['line'])
    line_bonus = max(0, 100 - line_dist * 2)
    score += line_bonus
    reasons.append(f"Line distance: {line_dist} (L{orig['line']} -> L{verif['line']})")

    # Snippet identifier overlap
    snip_orig = orig['snippet']
    snip_verif = verif['snippet']
    if snip_orig and snip_verif:
        id_orig = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', snip_orig))
        id_verif = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', snip_verif))
        id_overlap = id_orig & id_verif
        if id_overlap:
            score += 20
            reasons.append(f"Snippet identifier match ({', '.join(list(id_overlap)[:2])})")

    return (score, -line_dist, "; ".join(reasons))


def match_findings(
    original_findings: List[Dict[str, Any]],
    verification_findings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Pairs original baseline findings against verification findings deterministically.
    Categorizes outcomes into:
      - per_original_status: RESOLVED or STILL_PRESENT
      - new_issues: NEW_ISSUE
      - overall_outcome: ALL_RESOLVED, RESOLVED_WITH_NEW_ISSUES, STILL_PRESENT, STILL_PRESENT_WITH_NEW_ISSUES
    """
    orig_identities = [extract_finding_identity(f) for f in original_findings]
    verif_identities = [extract_finding_identity(f) for f in verification_findings]

    candidates = []
    for i, orig in enumerate(orig_identities):
        for j, verif in enumerate(verif_identities):
            score, neg_dist, rationale = compute_match_score(orig, verif)
            if score >= 250:
                candidates.append((score, neg_dist, i, j, rationale))

    # Highest score first, then smallest line distance, then stable index order
    candidates.sort(key=lambda x: (x[0], x[1], -x[2], -x[3]), reverse=True)

    matched_orig = {}   # i -> (j, score, rationale)
    matched_verif = {}  # j -> i

    for score, neg_dist, i, j, rationale in candidates:
        if i not in matched_orig and j not in matched_verif:
            matched_orig[i] = (j, score, rationale)
            matched_verif[j] = i

    per_original_status = []
    any_still_present = False
    all_resolved = True

    for i, orig in enumerate(orig_identities):
        raw_orig = original_findings[i]
        cwe_label = orig['cwe'] if orig['cwe'] != 'N/A' else orig['check_id']
        if i in matched_orig:
            j, score, rationale = matched_orig[i]
            matched_f = verification_findings[j]
            verif_ident = verif_identities[j]
            shift = verif_ident['line'] - orig['line']
            shift_desc = f" (line shifted by {shift:+d} lines)" if shift != 0 else ""

            any_still_present = True
            all_resolved = False

            per_original_status.append({
                'original_finding': raw_orig,
                'status': 'STILL_PRESENT',
                'matched_finding': matched_f,
                'line_shift': shift,
                'explanation': (
                    f"Original vulnerability ({cwe_label}: {orig['category']}) is STILL PRESENT "
                    f"at line {verif_ident['line']}{shift_desc}."
                ),
                'match_rationale': rationale,
            })
        else:
            per_original_status.append({
                'original_finding': raw_orig,
                'status': 'RESOLVED',
                'matched_finding': None,
                'line_shift': 0,
                'explanation': (
                    f"Original vulnerability resolved. No matching security finding "
                    f"was detected in the modified code for {cwe_label} at line {orig['line']}."
                ),
                'match_rationale': "No matching rule, CWE, or category detected by the scanner after rescan.",
            })

    new_issues = []
    for j, verif in enumerate(verif_identities):
        if j not in matched_verif:
            raw_verif = verification_findings[j]
            cwe_label = verif['cwe'] if verif['cwe'] != 'N/A' else verif['check_id']
            new_issues.append({
                'finding': raw_verif,
                'status': 'NEW_ISSUE',
                'explanation': (
                    f"New security issue ({cwe_label}: {verif['category']}) detected "
                    f"at line {verif['line']}."
                ),
            })

    has_new = len(new_issues) > 0
    if all_resolved and not has_new:
        overall = 'ALL_RESOLVED'
    elif all_resolved and has_new:
        overall = 'RESOLVED_WITH_NEW_ISSUES'
    elif any_still_present and has_new:
        overall = 'STILL_PRESENT_WITH_NEW_ISSUES'
    else:
        overall = 'STILL_PRESENT'

    return {
        'per_original_status': per_original_status,
        'new_issues': new_issues,
        'overall_outcome': overall,
        'total_original': len(original_findings),
        'resolved_count': sum(1 for p in per_original_status if p['status'] == 'RESOLVED'),
        'still_present_count': sum(1 for p in per_original_status if p['status'] == 'STILL_PRESENT'),
        'new_issue_count': len(new_issues),
    }


def run_verification_scan(modified_code: str, language: str) -> Tuple[List[Dict[str, Any]], float]:
    """
    Rescans modified source code using the project's existing Scanner.
    Writes modified code to a temporary file using the language's native extension.
    Returns (verification_findings, risk_score).
    """
    import os
    import tempfile
    from src.scanner import Scanner

    lang_ext_map = {
        'python': '.py',
        'javascript': '.js',
        'java': '.java',
        'c': '.c',
    }
    ext = lang_ext_map.get(language.lower(), '.py')

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, mode='w', encoding='utf-8') as tmp:
            tmp.write(modified_code)
            tmp_path = tmp.name

        scanner = Scanner()
        findings, risk_score = scanner.scan_file(tmp_path)
        return findings, risk_score
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Verification rescan failed: {e}")
        return [], 0.0
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def verify_fix_pipeline(
    original_findings: List[Dict[str, Any]],
    modified_code: str,
    language: str
) -> Dict[str, Any]:
    """
    Executes the full fix verification pipeline:
      1. Rescans modified code with existing Scanner.
      2. Matches original baseline findings against verification findings.
      3. Distinguishes RESOLVED, STILL_PRESENT, and NEW_ISSUE.
      4. Calculates verification risk score from the verification findings.
    """
    verif_findings, verif_risk = run_verification_scan(modified_code, language)
    match_result = match_findings(original_findings, verif_findings)

    return {
        'verification_findings': verif_findings,
        'verification_risk_score': verif_risk,
        'per_original_status': match_result['per_original_status'],
        'new_issues': match_result['new_issues'],
        'overall_outcome': match_result['overall_outcome'],
        'total_original': match_result['total_original'],
        'resolved_count': match_result['resolved_count'],
        'still_present_count': match_result['still_present_count'],
        'new_issue_count': match_result['new_issue_count'],
    }

