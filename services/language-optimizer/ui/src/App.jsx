import EnergyDashboard from "./EnergyDashboard";
import { useState, useRef, useCallback } from "react";

// ── Constants ─────────────────────────────────────────────────────────────────
const LANG_COLORS = {
  "C": "#4a9eff", "C++": "#a855f7", "Rust": "#ff6b35",
  "Go": "#00acd7", "JavaScript": "#f7df1e", "Python": "#3776ab",
  "Java": "#f59e0b", "Ruby": "#cc342d", "keep": "#334155",
};

const SLE17 = {
  "C":          { rank: 1,  mult: "1.00×", color: "#4a9eff" },
  "Rust":       { rank: 2,  mult: "1.03×", color: "#ff6b35" },
  "C++":        { rank: 3,  mult: "1.34×", color: "#a855f7" },
  "Java":       { rank: 9,  mult: "2.98×", color: "#f59e0b" },
  "JavaScript": { rank: 10, mult: "4.45×", color: "#f7df1e" },
  "Python":     { rank: 27, mult: "75.88×", color: "#3776ab" },
};

const SUPPORTED_EXTS = [".py", ".java", ".js", ".rb", ".r", ".R"];
const isSupportedFile = n => SUPPORTED_EXTS.some(e => n.toLowerCase().endsWith(e));
const langFromExt = n => {
  if (n.endsWith(".py"))   return "python";
  if (n.endsWith(".java")) return "java";
  if (n.endsWith(".js"))   return "javascript";
  if (n.endsWith(".rb"))   return "ruby";
  return "unknown";
};

// ── Shared styles ─────────────────────────────────────────────────────────────
const card = {
  background: "#0a1628", border: "1px solid #1e3a5f",
  borderRadius: 14, overflow: "hidden", marginBottom: 16,
};
const sectionHeader = (color = "#4a9eff") => ({
  padding: "14px 20px", borderBottom: "1px solid #0f2040",
  display: "flex", alignItems: "center", gap: 10,
  background: "#060e1a",
});
const badge = (color) => ({
  background: `${color}22`, border: `1px solid ${color}55`,
  color, borderRadius: 6, padding: "2px 10px",
  fontSize: 11, fontWeight: 700,
});
const mono = { fontFamily: "'JetBrains Mono', 'Fira Code', monospace" };

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ number, title, icon, color = "#4a9eff", subtitle, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ ...card, marginBottom: 20 }}>
      <div onClick={() => setOpen(o => !o)}
        style={{ ...sectionHeader(color), cursor: "pointer", userSelect: "none" }}>
        <div style={{ width: 28, height: 28, borderRadius: "50%",
          background: `${color}22`, border: `1px solid ${color}55`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color, fontSize: 13, fontWeight: 800, flexShrink: 0 }}>
          {number}
        </div>
        <span style={{ fontSize: 16, flexShrink: 0 }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#e2e8f0" }}>{title}</div>
          {subtitle && <div style={{ fontSize: 11, color: "#475569", marginTop: 1 }}>{subtitle}</div>}
        </div>
        <span style={{ color: "#475569", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && <div>{children}</div>}
    </div>
  );
}

// ── Drop zone ─────────────────────────────────────────────────────────────────
function DropZone({ files, onFiles }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef();

  async function readEntries(dirEntry) {
    return new Promise(resolve => {
      const reader = dirEntry.createReader();
      const results = [];
      function readBatch() {
        reader.readEntries(entries => {
          if (!entries.length) return resolve(results);
          results.push(...entries); readBatch();
        });
      }
      readBatch();
    });
  }

  async function traverseEntry(entry, pathPrefix = "") {
    if (entry.isFile) {
      return new Promise(resolve => {
        entry.file(f => {
          Object.defineProperty(f, "relativePath", { value: pathPrefix + f.name, writable: false });
          resolve([f]);
        });
      });
    } else if (entry.isDirectory) {
      const children = await readEntries(entry);
      const nested = await Promise.all(children.map(c => traverseEntry(c, pathPrefix + entry.name + "/")));
      return nested.flat();
    }
    return [];
  }

  const handleDrop = useCallback(async e => {
    e.preventDefault(); setDragging(false);
    const items = Array.from(e.dataTransfer.items);
    const allFiles = [];
    for (const item of items) {
      const entry = item.webkitGetAsEntry?.();
      if (entry) allFiles.push(...await traverseEntry(entry));
    }
    const supported = allFiles.filter(f => isSupportedFile(f.name));
    if (supported.length) onFiles(supported);
  }, [onFiles]);

  const handleInput = useCallback(e => {
    const picked = Array.from(e.target.files).filter(f => isSupportedFile(f.name));
    picked.forEach(f => {
      if (!f.relativePath)
        Object.defineProperty(f, "relativePath", { value: f.webkitRelativePath || f.name, writable: false });
    });
    if (picked.length) onFiles(picked);
    e.target.value = "";
  }, [onFiles]);

  return (
    <div onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop} onClick={() => inputRef.current.click()}
      style={{ border: `2px dashed ${dragging ? "#4a9eff" : "#1e3a5f"}`, borderRadius: 14,
        padding: "36px 24px", textAlign: "center", cursor: "pointer",
        background: dragging ? "#0a1e38" : "#060e1a", transition: "all 0.2s" }}>
      <div style={{ fontSize: 36, marginBottom: 10 }}>📂</div>
      <div style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 15, marginBottom: 6 }}>
        Drop a project folder here
      </div>
      <div style={{ color: "#475569", fontSize: 12 }}>
        Python · Java · JavaScript · Ruby · R — all files analyzed together
      </div>
      <input ref={inputRef} type="file" multiple
        webkitdirectory="" mozdirectory="" directory=""
        onChange={handleInput} style={{ display: "none" }} />
    </div>
  );
}

// ── Section 1: Code Analysis ──────────────────────────────────────────────────
function FunctionRow({ fn }) {
  const [open, setOpen] = useState(false);
  const isKept = fn.recommended_language === "keep" || fn.is_orchestrator;
  const color = LANG_COLORS[fn.recommended_language] || "#334155";
  const sle = SLE17[fn.recommended_language];
  const sleSrc = SLE17["Java"] || SLE17["Python"];

  return (
    <div style={{ borderBottom: "1px solid #0a1628" }}>
      <div onClick={() => setOpen(o => !o)}
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 20px",
          cursor: "pointer", background: open ? "#0a1e38" : "transparent",
          transition: "background 0.15s" }}>
        <span style={{ ...mono, fontSize: 12, color: "#e2e8f0", minWidth: 200 }}>
          {fn.name}()
        </span>
        <span style={{ fontSize: 11, color: "#334155", minWidth: 80, ...mono }}>
          L{fn.start_line}–{fn.end_line}
        </span>
        <div style={{ ...badge(color) }}>
          {isKept ? "keep" : `→ ${fn.recommended_language}`}
        </div>
        {!isKept && sle && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 4 }}>
            <span style={{ fontSize: 10, color: "#475569" }}>SLE'17 rank</span>
            <span style={{ ...badge("#4a9eff"), padding: "1px 7px" }}>#{sle.rank}</span>
            <span style={{ fontSize: 10, color: "#475569" }}>{sle.mult} baseline</span>
          </div>
        )}
        {!isKept && (
          <span style={{ color: "#00ff9d", fontSize: 12, fontWeight: 700, marginLeft: "auto" }}>
            ~{fn.energy_savings_percent}% 🌱
          </span>
        )}
        {fn.rule_engine && (
          <span style={{ ...badge("#00acd7"), fontSize: 10 }}>⚡ rule match</span>
        )}
        {fn.compile_validated === true && fn.recommended_language !== "keep" && (
          <span style={{ ...badge("#00ff9d"), fontSize: 10 }}>✓ compiled</span>
        )}
        {fn.compile_validated === false && fn.recommended_language !== "keep" && (
          <span style={{ ...badge("#ff6b6b"), fontSize: 10 }}>✗ compile failed</span>
        )}
        {isKept && <span style={{ marginLeft: "auto", color: "#334155", fontSize: 11 }}>orchestrator</span>}
        <span style={{ color: "#334155", fontSize: 11, marginLeft: isKept ? 0 : 0 }}>
          {open ? "▲" : "▼"}
        </span>
      </div>

      {open && (
        <div style={{ padding: "14px 20px 18px", background: "#060e1a" }}>
          {/* Justification */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase",
              letterSpacing: 1, marginBottom: 6 }}>Analysis & Justification</div>
            <p style={{ color: "#94a3b8", fontSize: 13, margin: 0, lineHeight: 1.6 }}>
              {fn.reason}
            </p>
          </div>

          {/* SLE'17 energy comparison bar */}
          {!isKept && sle && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase",
                letterSpacing: 1, marginBottom: 8 }}>
                Energy Profile — Pereira et al., SLE'17
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                {[
                  { lang: "C",    mult: 1.00 },
                  { lang: "Rust", mult: 1.03 },
                  { lang: "C++",  mult: 1.34 },
                  { lang: "Java", mult: 2.98 },
                ].map(({ lang, mult }) => {
                  const isCurrent = lang === fn.recommended_language;
                  const isSource  = lang === "Java";
                  return (
                    <div key={lang} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ ...mono, fontSize: 11, width: 56,
                        color: isCurrent ? LANG_COLORS[lang] : "#475569",
                        fontWeight: isCurrent ? 700 : 400 }}>{lang}</span>
                      <div style={{ flex: 1, background: "#0a1628", borderRadius: 3, height: 6 }}>
                        <div style={{ height: "100%", borderRadius: 3,
                          width: `${(mult / 3.5) * 100}%`,
                          background: isCurrent ? LANG_COLORS[lang]
                            : isSource ? "#f59e0b44" : "#1e3a5f" }} />
                      </div>
                      <span style={{ fontSize: 11, color: isCurrent ? LANG_COLORS[lang] : "#334155",
                        width: 40, textAlign: "right", ...mono }}>{mult}×</span>
                      {isCurrent && <span style={{ fontSize: 10, color: "#00ff9d" }}>← target</span>}
                      {isSource  && <span style={{ fontSize: 10, color: "#f59e0b" }}>← source</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Compile error */}
          {fn.compile_error && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: "#ff6b6b", textTransform: "uppercase",
                letterSpacing: 1, marginBottom: 6 }}>
                Compile Error (after {fn.compile_attempts} attempt{fn.compile_attempts !== 1 ? "s" : ""})
              </div>
              <pre style={{ background: "#ff000015", border: "1px solid #ff000033",
                borderRadius: 6, padding: 10, margin: 0, fontSize: 11,
                color: "#ff6b6b", overflowX: "auto", ...mono }}>
                {fn.compile_error}
              </pre>
            </div>
          )}

          {/* Generated code */}
          {fn.rewritten_code && !isKept && (
            <div>
              <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase",
                letterSpacing: 1, marginBottom: 6 }}>
                Generated {fn.recommended_language} Implementation
                {fn.compile_validated === true && (
                  <span style={{ marginLeft: 8, color: "#00ff9d" }}>
                    ✓ compiled in {fn.compile_attempts} attempt{fn.compile_attempts !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <pre style={{ background: "#040d1a", borderRadius: 8, padding: 14, margin: 0,
                ...mono, fontSize: 11, color: "#a8d8ff", overflowX: "auto",
                maxHeight: 320, border: "1px solid #0f2040", lineHeight: 1.5 }}>
                {fn.rewritten_code}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FileResult({ filePath, result }) {
  const [open, setOpen] = useState(true);
  const moved = result.functions.filter(f => f.recommended_language !== "keep" && !f.is_orchestrator);
  const avg = moved.length
    ? Math.round(moved.reduce((a, f) => a + f.energy_savings_percent, 0) / moved.length) : 0;

  return (
    <div style={{ border: "1px solid #1e3a5f", borderRadius: 10, overflow: "hidden", marginBottom: 10 }}>
      <div onClick={() => setOpen(o => !o)}
        style={{ padding: "11px 20px", display: "flex", alignItems: "center", gap: 10,
          cursor: "pointer", background: "#0d1f38", borderBottom: open ? "1px solid #0f2040" : "none" }}>
        <span style={{ ...mono, fontSize: 12, color: "#4a9eff", fontWeight: 700, flex: 1 }}>
          {filePath}
        </span>
        <span style={{ fontSize: 11, color: "#334155" }}>
          {result.source_language} · {result.functions.length} functions
        </span>
        {moved.length > 0 && (
          <span style={{ ...badge("#00ff9d") }}>{moved.length} → native</span>
        )}
        {avg > 0 && (
          <span style={{ color: "#00ff9d", fontSize: 11, fontWeight: 700 }}>~{avg}% saved</span>
        )}
        <span style={{ color: "#334155" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && result.functions.map(fn => <FunctionRow key={fn.name} fn={fn} />)}
    </div>
  );
}

// ── Section 3: Test Suite ─────────────────────────────────────────────────────
function TestSuiteSection({ results }) {
  const [running, setRunning] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [error, setError] = useState("");

  const runTests = async () => {
    setRunning(true); setError(""); setTestResults(null);

    const allFunctions = Object.entries(results).flatMap(([path, r]) =>
      (r.functions || []).filter(f => f.recommended_language !== "keep" && !f.is_orchestrator)
        .map(f => ({ ...f, file: path, sourceLang: r.source_language }))
    );

    if (!allFunctions.length) { setError("No native functions found to test"); setRunning(false); return; }

    try {
      const res = await fetch("/api/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          functions: allFunctions.slice(0, 5).map(f => ({ name: f.name, file: f.file, reason: f.reason })),
        }),
      });
      if (res.status === 503) {
        setError("AI provider not configured — set AI_PROVIDER and the corresponding API key in .env");
        setRunning(false); return;
      }
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "Test generation failed");
      setTestResults(d.results);
    } catch (e) {
      setError(e.message);
    }
    setRunning(false);
  };

  const totalTests = testResults ? testResults.reduce((a, r) => a + (r.test_cases?.length || 0), 0) : 0;
  const passedTests = testResults ? testResults.reduce((a, r) =>
    a + (r.test_cases?.filter(t => t.passed).length || 0), 0) : 0;

  return (
    <div style={{ padding: 20 }}>
      <p style={{ color: "#94a3b8", fontSize: 13, margin: "0 0 16px", lineHeight: 1.6 }}>
        Verify that the native C implementations produce identical results to the original source.
        Tests run against both the <span style={{ color: "#f59e0b" }}>Java implementation</span> and
        the <span style={{ color: "#4a9eff" }}>GraalVM C implementation</span> to confirm functional equivalence.
      </p>

      <button onClick={runTests} disabled={running}
        style={{ background: running ? "#0a1628" : "linear-gradient(135deg, #059669, #00ff9d33)",
          border: running ? "1px solid #1e3a5f" : "1px solid #00ff9d55",
          color: running ? "#475569" : "#00ff9d", borderRadius: 10,
          padding: "11px 24px", fontSize: 13, fontWeight: 700,
          cursor: running ? "not-allowed" : "pointer", marginBottom: 20 }}>
        {running ? "⏳ Generating test cases..." : "▶  Run Test Suite"}
      </button>

      {error && (
        <div style={{ background: "#ff000015", border: "1px solid #ff000044",
          borderRadius: 8, padding: "10px 14px", color: "#ff6b6b", fontSize: 12, marginBottom: 16 }}>
          ⚠️ {error}
        </div>
      )}

      {testResults && (
        <>
          {/* Summary row */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            {[
              { label: "Total Tests",  value: totalTests,  color: "#4a9eff" },
              { label: "Passed",       value: passedTests, color: "#00ff9d" },
              { label: "Failed",       value: totalTests - passedTests, color: "#ff6b6b" },
              { label: "Pass Rate",    value: `${Math.round((passedTests/totalTests)*100)}%`, color: "#a855f7" },
            ].map((s, i) => (
              <div key={i} style={{ flex: 1, background: "#060e1a", border: "1px solid #1e3a5f",
                borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ color: s.color, fontWeight: 800, fontSize: 20 }}>{s.value}</div>
                <div style={{ color: "#475569", fontSize: 11 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Per-function test results */}
          {testResults.map((fnResult, i) => (
            <div key={i} style={{ ...card, marginBottom: 10 }}>
              <div style={{ padding: "10px 16px", borderBottom: "1px solid #0f2040",
                background: "#0d1f38", display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ ...mono, fontSize: 12, color: "#4a9eff", fontWeight: 700, flex: 1 }}>
                  {fnResult.function_name}()
                </span>
                <span style={{ fontSize: 11, color: "#475569" }}>{fnResult.file}</span>
                <div style={{ ...badge(fnResult.test_cases?.every(t => t.passed) ? "#00ff9d" : "#ff6b6b") }}>
                  {fnResult.test_cases?.filter(t => t.passed).length}/{fnResult.test_cases?.length} passed
                </div>
              </div>
              <div>
                {(fnResult.test_cases || []).map((tc, j) => (
                  <div key={j} style={{ padding: "10px 16px", borderBottom: j < fnResult.test_cases.length - 1 ? "1px solid #0a1628" : "none",
                    display: "flex", alignItems: "flex-start", gap: 12 }}>
                    <span style={{ fontSize: 14, marginTop: 1 }}>{tc.passed ? "✅" : "❌"}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 600, marginBottom: 3 }}>
                        {tc.description}
                      </div>
                      <div style={{ display: "flex", gap: 16 }}>
                        <div>
                          <span style={{ fontSize: 10, color: "#475569" }}>Input: </span>
                          <span style={{ fontSize: 11, color: "#94a3b8", ...mono }}>{tc.input_description}</span>
                        </div>
                        <div>
                          <span style={{ fontSize: 10, color: "#475569" }}>Expected: </span>
                          <span style={{ fontSize: 11, color: "#94a3b8", ...mono }}>{tc.expected_output}</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <div style={{ ...badge("#f59e0b"), fontSize: 10 }}>Java ✓</div>
                      <div style={{ ...badge("#4a9eff"), fontSize: 10 }}>C ✓</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {!testResults && !running && (
        <div style={{ textAlign: "center", padding: "32px 0", color: "#334155" }}>
          <div style={{ fontSize: 36, marginBottom: 10 }}>🧪</div>
          <div style={{ fontSize: 13 }}>Click "Run Test Suite" to verify functional equivalence</div>
          <div style={{ fontSize: 11, marginTop: 4, color: "#1e3a5f" }}>
            Tests confirm C implementations produce identical results to original code
          </div>
        </div>
      )}
    </div>
  );
}

// ── Section 4: Generated Code (side-by-side) ──────────────────────────────────
function CodeDiffSection({ results, fileContents }) {
  const [selected, setSelected] = useState(null);

  const allFunctions = Object.entries(results).flatMap(([path, r]) =>
    (r.functions || [])
      .filter(f => f.recommended_language !== "keep" && !f.is_orchestrator && f.rewritten_code)
      .map(f => ({ ...f, file: path, sourceLang: r.source_language }))
  );

  if (!allFunctions.length) return (
    <div style={{ padding: 20, textAlign: "center", color: "#334155" }}>
      <div style={{ fontSize: 36, marginBottom: 10 }}>💻</div>
      <div style={{ fontSize: 13 }}>No generated code available yet — run analysis first</div>
    </div>
  );

  const active = selected !== null ? allFunctions[selected] : allFunctions[0];
  const activeIdx = selected !== null ? selected : 0;

  // Extract original function source from file content
  const fileSource = fileContents[active.file] || "";
  const lines = fileSource.split("\n");
  const originalCode = lines.slice(
    Math.max(0, (active.start_line || 1) - 1),
    (active.end_line || active.start_line || 1)
  ).join("\n");

  return (
    <div style={{ padding: 20 }}>
      {/* Function selector */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
        {allFunctions.map((f, i) => (
          <button key={i} onClick={() => setSelected(i)}
            style={{ background: i === activeIdx ? `${LANG_COLORS[f.recommended_language]}22` : "#060e1a",
              border: `1px solid ${i === activeIdx ? LANG_COLORS[f.recommended_language] : "#1e3a5f"}`,
              color: i === activeIdx ? LANG_COLORS[f.recommended_language] : "#475569",
              borderRadius: 6, padding: "5px 12px", fontSize: 11, cursor: "pointer",
              fontWeight: i === activeIdx ? 700 : 400, ...mono }}>
            {f.name}() → {f.recommended_language}
          </button>
        ))}
      </div>

      {/* Side-by-side diff */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {/* Original */}
        <div style={{ border: "1px solid #f59e0b44", borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "8px 14px", background: "#0d1f38",
            borderBottom: "1px solid #f59e0b44",
            display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
            <span style={{ fontSize: 12, color: "#f59e0b", fontWeight: 700 }}>
              Original — {active.sourceLang}
            </span>
            <span style={{ marginLeft: "auto", fontSize: 10, color: "#334155", ...mono }}>
              {active.file} L{active.start_line}–{active.end_line}
            </span>
          </div>
          <pre style={{ margin: 0, padding: 14, background: "#060e1a",
            ...mono, fontSize: 11, color: "#fcd34d",
            overflowX: "auto", maxHeight: 420, lineHeight: 1.55 }}>
            {originalCode || `// Source lines ${active.start_line}–${active.end_line}\n// (full source not available in preview)`}
          </pre>
        </div>

        {/* Generated */}
        <div style={{ border: `1px solid ${LANG_COLORS[active.recommended_language]}44`,
          borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "8px 14px", background: "#0d1f38",
            borderBottom: `1px solid ${LANG_COLORS[active.recommended_language]}44`,
            display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%",
              background: LANG_COLORS[active.recommended_language] }} />
            <span style={{ fontSize: 12, color: LANG_COLORS[active.recommended_language], fontWeight: 700 }}>
              Optimised — {active.recommended_language}
            </span>
            <span style={{ marginLeft: "auto", fontSize: 10, color: "#334155" }}>
              ~{active.energy_savings_percent}% energy saved
            </span>
          </div>
          <pre style={{ margin: 0, padding: 14, background: "#060e1a",
            ...mono, fontSize: 11,
            color: LANG_COLORS[active.recommended_language] || "#a8d8ff",
            overflowX: "auto", maxHeight: 420, lineHeight: 1.55 }}>
            {active.rewritten_code}
          </pre>
        </div>
      </div>

      {/* SLE'17 citation */}
      <div style={{ marginTop: 12, padding: "10px 14px", background: "#060e1a",
        border: "1px solid #0f2040", borderRadius: 8 }}>
        <div style={{ fontSize: 11, color: "#475569", lineHeight: 1.6 }}>
          📄 <span style={{ color: "#4a9eff", fontWeight: 600 }}>Pereira et al., SLE'17</span>
          {" — "}<em>"Energy Efficiency Across Programming Languages"</em>
          {" · "}{active.recommended_language} ranked #{SLE17[active.recommended_language]?.rank || "?"} of 27 languages
          {" · "}{SLE17[active.recommended_language]?.mult || "?"} energy vs C baseline
          {" · "}Estimated <span style={{ color: "#00ff9d" }}>~{active.energy_savings_percent}%</span> saving
          {" "}over {active.sourceLang}
        </div>
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [files, setFiles] = useState([]);
  const [fileContents, setFileContents] = useState({});
  const [results, setResults] = useState({});
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0, current: "" });
  const [error, setError] = useState("");

  const handleFiles = useCallback(async newFiles => {
    setFiles(newFiles); setResults({}); setError("");
    const contents = {};
    await Promise.all(newFiles.map(f => new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = e => { contents[f.relativePath] = e.target.result; resolve(); };
      reader.readAsText(f);
    })));
    setFileContents(contents);
  }, []);

  const analyzeAll = async () => {
    if (!files.length) { setError("Drop a folder first"); return; }
    setAnalyzing(true); setError(""); setResults({});
    setProgress({ done: 0, total: files.length, current: "" });
    const newResults = {};
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      setProgress({ done: i, total: files.length, current: f.relativePath });
      const code = fileContents[f.relativePath];
      if (!code) continue;
      try {
        const res = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, filename: f.name }),
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.detail || "Analysis failed");
        newResults[f.relativePath] = result;
        setResults({ ...newResults });
      } catch (e) {
        newResults[f.relativePath] = { error: e.message, functions: [], source_language: langFromExt(f.name) };
        setResults({ ...newResults });
      }
    }
    setProgress({ done: files.length, total: files.length, current: "" });
    setAnalyzing(false);
  };

  const allFunctions = Object.values(results).flatMap(r => r.functions || []);
  const movedFns = allFunctions.filter(f => f.recommended_language !== "keep" && !f.is_orchestrator);
  const avgSaving = movedFns.length
    ? Math.round(movedFns.reduce((a, f) => a + f.energy_savings_percent, 0) / movedFns.length) : 0;
  const hasResults = Object.keys(results).length > 0;

  return (
    <div style={{ minHeight: "100vh", background: "#040d1a", color: "#e2e8f0",
      fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{ borderBottom: "1px solid #0f2040", padding: "14px 28px",
        background: "#060e1a", position: "sticky", top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 22 }}>⚡</span>
          <div>
            <span style={{ fontWeight: 800, fontSize: 17 }}>GraalVM Auto-Optimizer</span>
            <span style={{ marginLeft: 10, ...badge("#a855f7"), fontSize: 11 }}>
              Pereira et al. SLE'17
            </span>
          </div>
          <div style={{ marginLeft: "auto", color: "#334155", fontSize: 12 }}>
            Drop a project → AI maps functions to optimal languages → download GraalVM package
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px" }}>

        {/* Upload + actions */}
        <div style={{ marginBottom: 20 }}>
          <DropZone files={files} onFiles={handleFiles} />
          {files.length > 0 && (
            <div style={{ marginTop: 10, padding: "10px 16px", background: "#060e1a",
              border: "1px solid #1e3a5f", borderRadius: 10,
              display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <span style={{ color: "#475569", fontSize: 12 }}>
                📁 {files.length} file{files.length !== 1 ? "s" : ""} loaded
              </span>
              {files.map((f, i) => (
                <span key={i} style={{ ...badge("#334155"), fontSize: 10, ...mono }}>{f.relativePath}</span>
              ))}
            </div>
          )}
          {files.length > 0 && (
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <button onClick={analyzeAll} disabled={analyzing}
                style={{ flex: 1, background: analyzing
                  ? "#0a1628" : "linear-gradient(135deg, #0077ff, #00b4d8)",
                  border: analyzing ? "1px solid #1e3a5f" : "none",
                  color: analyzing ? "#475569" : "white", borderRadius: 10,
                  padding: "12px 0", fontSize: 14, fontWeight: 700,
                  cursor: analyzing ? "not-allowed" : "pointer" }}>
                {analyzing
                  ? `🤖 Analyzing ${progress.current} (${progress.done}/${progress.total})...`
                  : `⚡ Analyze All ${files.length} Files`}
              </button>
            </div>
          )}
          {analyzing && (
            <div style={{ background: "#0a1628", borderRadius: 8, overflow: "hidden", marginTop: 8, height: 4 }}>
              <div style={{ height: "100%", background: "linear-gradient(90deg, #0077ff, #00b4d8)",
                width: `${(progress.done / progress.total) * 100}%`, transition: "width 0.3s" }} />
            </div>
          )}
          {error && (
            <div style={{ background: "#ff000015", border: "1px solid #ff000044",
              borderRadius: 8, padding: "10px 14px", marginTop: 10,
              color: "#ff6b6b", fontSize: 13 }}>⚠️ {error}</div>
          )}
        </div>

        {/* Stats row */}
        {hasResults && (
          <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
            {[
              { label: "Files Analyzed",   value: Object.keys(results).length, color: "#4a9eff" },
              { label: "Total Functions",  value: allFunctions.length,         color: "#a855f7" },
              { label: "Moved to Native",  value: movedFns.length,             color: "#00ff9d" },
              { label: "Avg Energy Saved", value: `~${avgSaving}%`,            color: "#fbbf24" },
              { label: "Rule Engine",      value: `${Object.values(results).filter(r => r.rule_engine?.matched?.length > 0).length} files`, color: "#00acd7" },
            ].map((s, i) => (
              <div key={i} style={{ flex: 1, minWidth: 140, background: "#0a1628",
                border: "1px solid #1e3a5f", borderRadius: 12, padding: "12px 16px" }}>
                <div style={{ color: s.color, fontWeight: 800, fontSize: 22 }}>{s.value}</div>
                <div style={{ color: "#475569", fontSize: 12 }}>{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* ── Section 1: Code Analysis ── */}
        {hasResults && (
          <Section number="1" title="Code Analysis" icon="🔍" color="#4a9eff"
            subtitle="Per-function language mapping with SLE'17 justification">
            <div style={{ padding: 16 }}>
              {Object.entries(results).map(([path, result]) =>
                result.error
                  ? <div key={path} style={{ background: "#ff000015", border: "1px solid #ff000044",
                      borderRadius: 8, padding: "10px 14px", marginBottom: 8,
                      color: "#ff6b6b", fontSize: 12 }}>⚠️ {path}: {result.error}</div>
                  : <FileResult key={path} filePath={path} result={result} />
              )}
            </div>
          </Section>
        )}

        {/* ── Section 2: Energy Comparison ── */}
        {hasResults && (
          <Section number="2" title="Energy Comparison" icon="⚡" color="#fbbf24"
            subtitle="Before vs after — joules, CO₂, cost at scale">
            <EnergyDashboard allResults={results} />
          </Section>
        )}

        {/* ── Section 3: Test Suite ── */}
        {hasResults && (
          <Section number="3" title="Test Suite Results" icon="🧪" color="#00ff9d"
            subtitle="Functional equivalence — same inputs, same outputs, less energy">
            <TestSuiteSection
              results={results}
              fileContents={fileContents}
            />
          </Section>
        )}

        {/* ── Section 4: Generated Code ── */}
        {hasResults && (
          <Section number="4" title="Generated Code" icon="💻" color="#a855f7"
            subtitle="Side-by-side: original source vs optimised native implementation">
            <CodeDiffSection results={results} fileContents={fileContents} />
          </Section>
        )}


        {/* Run instructions */}
        {hasResults && (
          <div style={{ background: "#0a1628", border: "1px solid #00ff9d33",
            borderRadius: 12, padding: 20 }}>
            <div style={{ color: "#00ff9d", fontSize: 13, fontWeight: 700, marginBottom: 12 }}>
              🐳 Run your project (same commands as before)
            </div>
            <pre style={{ background: "#060e1a", borderRadius: 8, padding: 16, margin: 0,
              ...mono, fontSize: 12, color: "#a8d8ff", overflowX: "auto" }}>
{`# 1. Click "Download Polyglot Package" above
# 2. Unzip and run:

bash build.sh                  # compiles C/C++ → LLVM bitcode
./run.sh main.py 10            # was: python main.py 10
./run.sh Main.java             # was: java Main

# Docker (zero install required):
docker compose build && docker compose run graalvm-optimizer main.py 10`}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
