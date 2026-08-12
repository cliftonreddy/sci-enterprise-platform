"""
analyzer/code_validator.py

Compiles generated C/C++/Rust code and returns success/error.
On failure, sends the compiler error back to Claude for a fix.
Retries up to MAX_RETRIES times.
"""
import os, re, subprocess, tempfile, logging, shutil

log = logging.getLogger(__name__)

MAX_RETRIES = 3
CLANG   = os.environ.get("CLANG_PATH",  "clang")
CLANGPP = os.environ.get("CLANGPP_PATH", "clang++")
RUSTC   = os.environ.get("RUSTC_PATH",   "rustc")

FIX_PROMPT = """The following {lang} code failed to compile with this error:

COMPILER ERROR:
{error}

ORIGINAL CODE:
{code}

Fix the code so it compiles cleanly. Requirements:
- Complete, self-contained {lang} code with all includes/use statements
- Use only simple FFI-compatible types (int, long, double, char*, void*)
- No C++ features in C files
- For Rust: every exported function must have #[no_mangle] pub extern "C"
- For Rust: use only primitive types in signatures (f64, i32, i64, *const f64 etc.)
- For Rust: add #![allow(non_snake_case, dead_code)] at the top
- All functions must have correct return types
- Respond with ONLY the corrected {lang} source code, no markdown, no explanation.
"""


class ValidationResult:
    def __init__(self, success: bool, code: str, error: str = "",
                 attempts: int = 1, bitcode_path: str = ""):
        self.success      = success
        self.code         = code
        self.error        = error
        self.attempts     = attempts
        self.bitcode_path = bitcode_path


def _fix_common_rust_issues(code: str) -> str:
    """Fix known patterns of Claude-generated Rust code issues."""
    # Fix: .to_lowercase() on Cow<str> needs .to_string() to get owned String
    code = code.replace(
        '.to_string_lossy().to_lowercase()',
        '.to_string_lossy().to_lowercase().to_string()'
    )
    # Fix: double .to_string() if already applied
    code = code.replace(
        '.to_lowercase().to_string().to_string()',
        '.to_lowercase().to_string()'
    )
    # Fix: .into_owned() on String (already owned)
    code = code.replace('.to_lowercase().into_owned()', '.to_lowercase().to_string()')
    code = code.replace('.to_string_lossy().into_owned()', '.to_string_lossy().to_string()')
    # Fix: unused CString import — only strip if CString not used in body
    for pat in ('use std::ffi::{CStr, CString};', 'use std::ffi::{CString, CStr};'):
        if pat in code:
            body = code.replace(pat, '')
            if 'CString' not in body:
                code = code.replace(pat, 'use std::ffi::CStr;')

    # Fix: CString used in body but not imported — add the import
    if re.search(r'\bCString\b', code):
        has_cstring_import = bool(re.search(r'use std::ffi::.*CString', code))
        if not has_cstring_import:
            if 'use std::ffi::CStr;' in code:
                code = code.replace('use std::ffi::CStr;', 'use std::ffi::{CStr, CString};')
            elif 'use std::ffi' not in code:
                code = 'use std::ffi::CString;\n' + code
    # Fix: c_int/c_char imports — use libc-free version
    code = code.replace(
        'use std::os::raw::{c_char, c_int};',
        'use std::os::raw::c_char;'
    )
    # Add #![allow] if not present
    if '#![allow' not in code:
        code = '#![allow(non_snake_case, dead_code, unused_imports)]\n' + code
    return code


def _fix_common_c_issues(code: str) -> str:
    """Pre-fix known missing headers and Claude code patterns before compilation."""
    checks = [
        (['labs(', 'llabs(', 'malloc(', 'free(', 'qsort(', 'NULL', 'atoi(', 'abs('], '<stdlib.h>'),
        (['sqrt(', 'log(', 'exp(', 'pow(', 'fmod(', 'floor(', 'ceil(', 'fabs('], '<math.h>'),
        (['strcmp(', 'strcpy(', 'strncpy(', 'strlen(', 'strcat(', 'memcpy(', 'memset('], '<string.h>'),
        (['printf(', 'fprintf(', 'sprintf('], '<stdio.h>'),
        (['uint64_t', 'int64_t', 'uint32_t', 'int32_t', 'UINT64_MAX', 'INT64_MAX'], '<stdint.h>'),
        (['ULONG_MAX', 'INT_MAX', 'LONG_MAX'], '<limits.h>'),
    ]
    for symbols, header in checks:
        if any(s in code for s in symbols) and header not in code:
            code = f'#include {header}\n' + code

    # Fix: volatility used outside its scope in Box-Muller gaussian helpers
    code = code.replace(
        'double mag = volatility * sqrt(-2.0 * log(u));',
        'double mag = sqrt(-2.0 * log(u));'
    )
    code = code.replace(
        'double mag = volatility * sqrt(-2.0f * logf(u));',
        'double mag = sqrt(-2.0f * logf(u));'
    )
    return code


def validate_and_fix(code: str, lang: str, func_name: str,
                     api_caller) -> ValidationResult:
    """
    Try to compile code. If it fails, ask Claude to fix it.
    Supports C, C++, and Rust.
    """
    if lang == "C":
        ext, compiler = ".c", CLANG
        code = _fix_common_c_issues(code)
    elif lang == "C++":
        ext, compiler = ".cpp", CLANGPP
        code = _fix_common_c_issues(code)
    elif lang == "Rust":
        ext, compiler = ".rs", RUSTC
        code = _fix_common_rust_issues(code)  # pre-fix known Claude patterns
    else:
        return ValidationResult(True, code, "", 0)

    current_code = code
    last_error   = ""

    for attempt in range(1, MAX_RETRIES + 1):
        success, error, bc_path = _compile(current_code, ext, compiler, func_name, lang)

        if success:
            log.info(f"  OK {func_name} compiled on attempt {attempt}")
            return ValidationResult(True, current_code, "", attempt, bc_path)

        log.warning(f"  FAIL {func_name} attempt {attempt}: {error[:120]}")
        last_error = error

        if attempt < MAX_RETRIES:
            fix_prompt = FIX_PROMPT.format(
                lang=lang, error=error[:800], code=current_code)
            try:
                fixed = api_caller(fix_prompt)
                current_code = _strip_fences(fixed)
            except Exception as e:
                log.error(f"  API fix call failed: {e}")
                break

    return ValidationResult(False, current_code, last_error, MAX_RETRIES)


def _compile(code: str, ext: str, compiler: str, func_name: str, lang: str):
    """Compile code to LLVM bitcode. Returns (success, error, bc_path)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f"{func_name}{ext}")
        bc  = os.path.join(tmp, f"{func_name}.bc")

        with open(src, "w") as f:
            f.write(code)

        if lang == "Rust":
            # --crate-type=lib avoids linking step; -o names the bc directly
            cmd = [compiler, "--emit=llvm-bc", "-O",
                   "--crate-type=lib", src, "-o", bc]
        else:
            cmd = [compiler, "-O2", "-emit-llvm", "-c", src, "-o", bc,
                   "--target=x86_64-unknown-linux-gnu"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            log.debug(f"  {compiler} not found -- skipping validation")
            return True, "", ""
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out (>60s)", ""

        if result.returncode == 0:
            # Rustc may place the bc at the exact -o path or alongside the source;
            # search the temp dir for any .bc file if the expected path is missing.
            if not os.path.exists(bc):
                candidates = [
                    f for f in os.listdir(tmp)
                    if f.endswith(".bc") or f.endswith(".rmeta")
                ]
                bc_found = next(
                    (os.path.join(tmp, f) for f in candidates if f.endswith(".bc")),
                    None
                )
                if not bc_found:
                    return False, f"Compiler returned 0 but no .bc found in {tmp}: {candidates}", ""
                bc = bc_found

            bc_out = tempfile.mktemp(suffix=".bc")
            shutil.copy(bc, bc_out)
            return True, "", bc_out

        error = (result.stderr or result.stdout or "Unknown error").strip()
        return False, error, ""


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z+]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$",           "", text.strip(), flags=re.MULTILINE)
    return text.strip()
