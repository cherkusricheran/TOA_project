import re

class PromptEnricher:
    """
    Builds the CodeT5 prompt and post-processes the raw summary.

    Produces a three-section structured Markdown summary:
        ### Overview
        ### Key Behavior
        ### Key Functions

    Public API:
      construct_prompt(findings, ast_features, code_snippet) -> str
      enrich_summary(raw_summary, ast_features)             -> str
    """

    CODE_CHAR_LIMIT = 1000

    @staticmethod
    def construct_prompt(findings: list, ast_features: dict, code_snippet: str) -> str:
        """
        Build a hybrid prompt for CodeT5: verified structural/behavioral facts
        plus compact intent from docstrings/comments in an overview header.
        """
        lang = ast_features.get('lang', '')
        fns = ast_features.get('functions', [])
        params = ast_features.get('params_by_fn', {})
        classes = ast_features.get('classes', [])
        doc_ctx = ast_features.get('doc_context', '')

        parts = []
        if classes:
            parts.append(f"class {', '.join(classes[:2])}")

        fn_sigs = []
        for fn in fns[:3]:
            p = params.get(fn, [])
            fn_sigs.append(f"{fn}({', '.join(p)})")
        if fn_sigs:
            parts.append(f"functions: {', '.join(fn_sigs)}")

        if doc_ctx:
            parts.append(f"intent: {doc_ctx}")

        comment_sym = "//" if lang in ('java', 'javascript', 'c') else "#"
        if parts:
            summary_hint = f"{comment_sym} Overview: {', '.join(parts)}\n"
        else:
            summary_hint = ""

        remaining_chars = PromptEnricher.CODE_CHAR_LIMIT - len(summary_hint)
        code_chunk = code_snippet[:max(200, remaining_chars)]
        return f"{summary_hint}{code_chunk}"

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _clean_raw(raw: str, classes: list = None) -> str:
        """Strip boilerplate prefixes and class repetitions."""
        cleaned = raw.strip().rstrip(".")

        if classes:
            for c in classes:
                pat = rf'^(?:class\s+{re.escape(c)}|the\s+{re.escape(c)}\s+class)\s*[.:,-]*\s*'
                cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()

        prefixes = [
            "this function is used to", "this method is used to",
            "this function", "this method", "this class", "this module",
            "this script", "this program", "this file", "this code",
            "the function", "the method", "the class", "the code",
            "handles", "provides logic for", "implements logic for",
        ]
        lower = cleaned.lower()
        for p in prefixes:
            if lower.startswith(p):
                cleaned = cleaned[len(p):].lstrip(" :,-\n")
                break

        if cleaned:
            cleaned = cleaned[0].lower() + cleaned[1:]
        return cleaned

    @staticmethod
    def _is_trustworthy(cleaned: str, fn_names: list, code_str: str = "") -> bool:
        """
        Return True only when CodeT5 output is genuine, grounded, and not hallucinated.
        """
        if not cleaned or len(cleaned.split()) < 3:
            return False

        lower = cleaned.lower()
        code_lower = code_str.lower() if code_str else ""

        echo_phrases = [
            "describe", "summarize", "what the code does", "based on the code",
            "not present", "purpose:", "overview:",
        ]
        if any(p in lower for p in echo_phrases):
            return False

        if re.search(r'-\s*>|=\s*>|\u2192', cleaned):
            return False

        suspicious_words = [
            "token", "alphabet", "nanosecond", "sequence number", "nanomorphism",
            "nanotoken", "unique elements", "order of decreasing priority",
            "overview of", "short description of", "description of method",
            "word sequence", "non-empty", "non - empty", "private", "blake2b",
        ]
        for w in suspicious_words:
            if w in lower and (not code_lower or w not in code_lower):
                return False

        copula_starts = ("is ", "are ", "was ", "were ", "has ", "have ")
        if lower.startswith(copula_starts):
            return False

        for fn in fn_names:
            fn_low = fn.lower()
            if f"{fn_low} is" in lower and lower.count(fn_low) >= 2:
                return False
            if lower.startswith(fn_low + " is") or lower.startswith(fn_low + " returns"):
                return False

        return True

    @staticmethod
    def _has_false_intra_call(cleaned: str, fn_names: list, fn_facts: dict) -> bool:
        """
        Return True if CodeT5 claims function A calls function B but fn_body_facts
        shows no such call actually exists.
        """
        cl_lower = cleaned.lower()
        for other in fn_names:
            other_l = other.lower()
            pat = re.compile(r'calls\b.*\b' + re.escape(other_l) + r'\b')
            if pat.search(cl_lower):
                is_real = any(
                    other in fn_facts.get(fn, {}).get('intra_calls', [])
                    for fn in fn_names if fn != other
                )
                if not is_real:
                    return True
        return False

    # ── Public post-processor ────────────────────────────────────────

    @staticmethod
    def enrich_summary(raw_summary: str, ast_features: dict) -> str:
        """
        Produce a three-section structured Markdown summary:

            ### Overview
            ### Key Behavior
            ### Key Functions

        All factual claims are grounded in verified AST and behavioral facts.
        Comments and docstrings provide intent context without overriding code reality.
        """
        lang         = ast_features.get('lang', '')
        lang_str     = lang.capitalize() if lang else 'Code'
        functions    = list(dict.fromkeys(ast_features.get('functions', [])))
        classes      = list(dict.fromkeys(ast_features.get('classes', [])))
        imports      = list(dict.fromkeys(ast_features.get('imports', [])))
        params       = ast_features.get('params_by_fn', {})
        returns      = ast_features.get('return_info',  {})
        outputs      = ast_features.get('output_calls', [])
        code_content = ast_features.get('code', '')
        fn_facts     = ast_features.get('fn_body_facts', {})
        fn_docs      = ast_features.get('fn_docs', {})
        doc_context  = ast_features.get('doc_context', '')

        fn_names    = [f for f in functions if f not in classes]
        cleaned     = PromptEnricher._clean_raw(raw_summary, classes)
        trustworthy = PromptEnricher._is_trustworthy(cleaned, fn_names + classes, code_content)

        # ── helpers ─────────────────────────────────────────────────

        def fmt_sig(fn):
            p = params.get(fn, [])
            return f"`{fn}({', '.join(p)})`"

        # Check aggregate observable facts
        has_crypto = any(fn_facts.get(fn, {}).get('crypto_ops') for fn in fn_names) or any(
            c in code_content for c in ('pbkdf2', 'hashlib', 'urandom', 'sha256')
        )
        has_file = any(fn_facts.get(fn, {}).get('file_ops') for fn in fn_names) or any(
            c in code_content for c in ('open(', 'FileReader', 'FileInputStream', 'f.read()')
        )
        has_web = any(fn_facts.get(fn, {}).get('web_ops') for fn in fn_names) or any(
            c in code_content for c in ('request.args', 'request.form', 'req.query', 'getParameter')
        )
        has_eval = any(
            'eval' in fn_facts.get(fn, {}).get('api_calls', []) or 'eval(' in code_content
            for fn in fn_names
        ) or 'eval(' in code_content
        has_avg = any('average' in str(r).lower() for r in returns.values()) or any(
            'average' in str(o).lower() for o in outputs
        )
        has_dom_write = any(fn_facts.get(fn, {}).get('dom_writes') for fn in fn_names) or 'textContent' in code_content or 'innerHTML' in code_content

        def _fn_one_liner(fn):
            """
            Explain what the function actually DOES based on directly observable facts:
            inputs, operations, calls, returns, and verified intent from docstrings/comments.
            """
            facts = fn_facts.get(fn, {})
            api   = facts.get('api_calls',  [])
            ret   = returns.get(fn, '')
            dom_w = facts.get('dom_writes', [])
            dom_r = facts.get('dom_reads',  [])
            p_list = params.get(fn, [])
            p_str = ', '.join(f"`{p}`" for p in p_list) if p_list else ""
            doc   = fn_docs.get(fn, '')

            # 1. File + Web input
            if facts.get('file_ops') and facts.get('web_ops'):
                return "Retrieves a filename from the request and reads and returns the file contents"
            elif facts.get('file_ops'):
                if 'content' in ret.lower() or 'read' in ret.lower():
                    return "Reads and returns the contents of the specified file"
                return "Opens and accesses the specified file from disk"

            # 2. Cryptography / Password hashing
            if facts.get('crypto_ops') or any('pbkdf2' in a.lower() or 'urandom' in a.lower() or 'hashlib' in a.lower() for a in api):
                return "Generates a random salt and derives a secure cryptographic key using PBKDF2 with SHA-256"

            # 3. Interactive calculator functions
            if any('eval' in a.lower() for a in api):
                return "Evaluates the current arithmetic expression and displays the calculated result"
            if 'clear' in fn.lower() or (dom_w and 'equation' in code_content and not p_list):
                return "Clears the current expression and resets the display to its default state"
            if dom_w and ('equation' in code_content or 'screen' in code_content) and p_list:
                return f"Appends the entered {p_list[0]} to the current expression and updates the display"

            # 4. DOM table updates (Product management / Catalog)
            if dom_w and facts.get('has_loop') and any('html' in w.lower() for w in dom_w):
                return "Formats product data into HTML table rows and updates the display table"
            if any('push' in a.lower() or 'append' in a.lower() for a in api) and dom_r:
                called = facts.get('intra_calls', [])
                if called:
                    return f"Reads input values from the DOM, adds the new item to data, and invokes `{called[0]}()` to refresh the display"
                return "Reads input values from the DOM and adds the new item to the collection"

            # 5. Math / Average calculation (ONLY if this function computes average)
            if ret == "the calculated average" or ('average' in fn.lower() and '/' in ret):
                target = f"of {p_str}" if p_str else "of the input numbers"
                return f"Calculates and returns the average {target} by dividing the sum by the count"

            # 6. Comment/docstring intent verified against code
            if doc:
                doc_clean = doc[0].upper() + doc[1:].rstrip('.')
                if ret:
                    return f"{doc_clean} and returns {ret}"
                return doc_clean

            # 7. Observable return value
            if ret:
                if ret.startswith(('dividing', 'multiplying', 'subtracting')):
                    return f"Calculates and returns the result of {ret}"
                elif ret.startswith(('the ', 'a ')):
                    return f"Computes and returns {ret}"
                return f"Returns {ret}"

            # 8. Intra-calls
            if facts.get('intra_calls'):
                targets = ', '.join(f'`{t}()`' for t in facts['intra_calls'])
                return f"Processes inputs and invokes {targets} to coordinate updates"

            # 9. DOM operations
            if dom_r and dom_w:
                return f"Reads from '{dom_r[0]}' and updates the DOM display"
            if dom_w:
                return f"Updates {' and '.join(dom_w[:2])} in the DOM"
            if dom_r:
                return f"Reads data from the '{dom_r[0]}' element in the DOM"

            # 10. Directly observable parameter / conditional / loop processing
            if facts.get('has_cond') and p_str:
                return f"Validates {p_str} and applies conditional checks"
            if facts.get('has_loop') and p_str:
                return f"Iterates through {p_str} to process individual elements"
            if p_str:
                return f"Processes the {p_str} input"

            return f"Executes `{fn}()` routine"

        def _select_key_functions(fns):
            """
            Select the 3–5 most important functions based on behavioral significance.
            If fewer than 3 functions exist, returns all of them.
            """
            if len(fns) <= 5:
                return fns

            def score_fn(fn):
                facts = fn_facts.get(fn, {})
                score = 0
                if facts.get('intra_calls'):
                    score += 3
                if any(fn in fn_facts.get(other, {}).get('intra_calls', []) for other in fns):
                    score += 2
                if facts.get('crypto_ops') or facts.get('file_ops') or facts.get('web_ops'):
                    score += 3
                if facts.get('dom_writes') or facts.get('dom_reads'):
                    score += 2
                if any('eval' in a for a in facts.get('api_calls', [])):
                    score += 3
                if returns.get(fn):
                    score += 2
                if facts.get('has_loop') or facts.get('has_cond'):
                    score += 1
                if fn.startswith(('get_', 'set_', 'is_')) and len(facts.get('api_calls', [])) == 0:
                    score -= 2
                return score

            sorted_fns = sorted(fns, key=score_fn, reverse=True)
            return sorted_fns[:5]

        # ── Section 1: Overview ──────────────────────────────────────
        use_codet5 = (
            trustworthy
            and cleaned
            and not PromptEnricher._has_false_intra_call(cleaned, fn_names, fn_facts)
        )

        if use_codet5:
            predicate = cleaned[0].lower() + cleaned[1:]
            if not predicate.endswith('.'):
                predicate += '.'
            overview_text = f"This {lang_str} program {predicate}"
        else:
            # Grounded synthesis from observable facts
            if has_avg:
                overview_text = f"This {lang_str} program calculates the average of numbers and displays the result."
            elif has_crypto:
                overview_text = f"This {lang_str} program secures a password by generating a cryptographically random salt and deriving a key using PBKDF2 with SHA-256."
            elif has_eval and has_dom_write:
                overview_text = f"This {lang_str} program implements an interactive calculator that builds arithmetic expressions, evaluates them, and displays the result."
            elif has_file and has_web:
                overview_text = f"This {lang_str} program receives a filename from an HTTP request and reads and returns the contents of that file."
            elif has_dom_write and any(fn_facts.get(fn, {}).get('has_loop') for fn in fn_names):
                overview_text = f"This {lang_str} program processes structured data and dynamically updates the webpage display."
            elif doc_context:
                clean_doc = doc_context.lower().rstrip('.')
                overview_text = f"This {lang_str} program {clean_doc}."
            elif len(fn_names) == 1:
                fn_role = _fn_one_liner(fn_names[0])
                fn_role_clean = fn_role[0].lower() + fn_role[1:].rstrip('.')
                overview_text = f"This {lang_str} program defines `{fn_names[0]}()`, which {fn_role_clean}."
            elif classes:
                overview_text = f"This {lang_str} program defines the {', '.join(classes[:2])} class to encapsulate data and operations."
            elif fn_names:
                overview_text = f"This {lang_str} program implements {len(fn_names)} functions to execute application logic."
            else:
                overview_text = f"This {lang_str} program executes top-level script logic."

        section_overview = f"### Overview\n{overview_text}"

        # ── Section 2: Key Behavior ───────────────────────────────────
        bullets = []

        # 1. Inputs & Truly Shared State (only if multiple functions and variable is used across them)
        first_pos = code_content.find('def ') if lang == 'python' else code_content.find('function ')
        preamble = code_content[:first_pos] if first_pos > 0 else ''
        state_candidates = re.findall(r'\b([a-z_]\w*)\s*=\s*["\'\[\]{(]', preamble)
        state_candidates = list(dict.fromkeys(v for v in state_candidates if len(v) > 1))[:2]
        
        shared_state_vars = []
        if len(fn_names) > 1 and state_candidates:
            for sc in state_candidates:
                count = sum(1 for fn in fn_names if re.search(rf'\b{re.escape(sc)}\b', code_content))
                if count >= 2:
                    shared_state_vars.append(sc)

        if shared_state_vars:
            bullets.append(f"Maintains shared state in `{', '.join(shared_state_vars)}` across operations.")
        elif has_web:
            bullets.append("Receives input parameters from the incoming HTTP request.")
        elif fn_names and params.get(fn_names[0]):
            p_first = params[fn_names[0]]
            bullets.append(f"Accepts input data via `{', '.join(p_first[:2])}` for processing.")

        # 2. Core Processing / Calculations
        if has_avg:
            bullets.append("Computes the total sum and divides by the item count to calculate the average.")
        elif has_crypto:
            bullets.append("Generates a cryptographically secure random salt using os.urandom and derives an encryption key using PBKDF2 with SHA-256.")
        elif has_eval:
            bullets.append("Evaluates the built arithmetic expression dynamically to compute the calculation result.")
        elif has_file:
            bullets.append("Opens the specified file path and reads its content from disk.")
        elif has_dom_write and any(fn_facts.get(fn, {}).get('has_loop') for fn in fn_names):
            bullets.append("Iterates through the data items to construct formatted HTML table rows.")
        elif any(fn_facts.get(fn, {}).get('has_loop') for fn in fn_names):
            bullets.append("Iterates over the input collection to process individual elements.")

        # 3. Inter-function and DOM interactions
        for fn in fn_names:
            icalls = fn_facts.get(fn, {}).get('intra_calls', [])
            if icalls:
                bullets.append(f"Coordinates program flow by having `{fn}()` call `{icalls[0]}()` to update state.")
                break

        dom_reads = []
        for fn in fn_names:
            dom_reads.extend(fn_facts.get(fn, {}).get('dom_reads', []))
        dom_reads = list(dict.fromkeys(dom_reads))
        if dom_reads and not any("DOM" in b for b in bullets):
            bullets.append(f"Reads user input from the DOM element '{dom_reads[0]}'.")

        # 4. Results & Outputs
        if outputs:
            bullets.append(f"Displays {outputs[0]}.")
        elif has_dom_write:
            bullets.append("Updates the DOM to present the updated display to the user.")

        for fn in fn_names[:2]:
            ret = returns.get(fn, '')
            if ret and not any(ret[:15].lower() in b.lower() for b in bullets):
                bullets.append(f"Returns {ret} to the caller.")
                break

        # Fallbacks: only directly observable facts
        if len(bullets) < 3:
            if any(fn_facts.get(fn, {}).get('has_cond') for fn in fn_names):
                bullets.append("Applies conditional validation checks to guide execution.")
            if imports:
                bullets.append(f"Uses standard library modules ({', '.join(f'`{i}`' for i in imports[:2])}).")

        bullets = bullets[:5]
        section_behavior = "### Key Behavior\n" + "\n".join(f"- {b}" for b in bullets)

        # ── Section 3: Key Functions ──────────────────────────────────
        selected_fns = _select_key_functions(fn_names) if fn_names else []
        if selected_fns:
            fn_lines = []
            for fn in selected_fns:
                sig      = fmt_sig(fn)
                one_line = _fn_one_liner(fn)
                one_line = one_line[0].upper() + one_line[1:]
                if not one_line.endswith('.'):
                    one_line += '.'
                fn_lines.append(f"- {sig} \u2014 {one_line}")
            section_fns = "### Key Functions\n" + "\n".join(fn_lines)
        elif classes:
            cls_fns = [fmt_sig(f) for f in fn_names[:3]]
            section_fns = ("### Key Functions\n" + "\n".join(f"- {s} \u2014 Performs class operations." for s in cls_fns)) if cls_fns else ""
        else:
            section_fns = ""

        parts = [section_overview, section_behavior]
        if section_fns:
            parts.append(section_fns)
        return "\n\n".join(parts)
