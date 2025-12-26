/**
 * MyJudge Premium WebApp (no-build, Tailwind CDN, Monaco CDN)
 * FIXES:
 * 1) CP templates per language
 * 2) Problems sorted by ID ascending
 * 3) Sample Input/Output visible (supports many JSON keys)
 * 4) Monaco loader single-source (no double init)
 * 5) Editor always works, no blank/reset
 */

const state = {
  userId: null,
  theme: localStorage.getItem("mj_theme") || "dark",
  page: "editor",
  mobileTab: "editor",
  problems: [],
  selected: null,
  editor: null,
  language: "cpp",
  code: "",
  customInput: "",
  output: "",
  verdict: "",
  drawerOpen: true,
  loading: false,
  job: null,
};

const langMap = {
  cpp: { monaco: "cpp", label: "C++" },
  c: { monaco: "c", label: "C" },
  py: { monaco: "python", label: "Python" },
  js: { monaco: "javascript", label: "JavaScript" },
};

// ✅ CP style templates
const TEMPLATES = {
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main(){
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    // TODO

    return 0;
}
`,
  c: `#include <stdio.h>

int main(){
    // TODO
    return 0;
}
`,
  py: `def solve():
    import sys
    data = sys.stdin.read().strip().split()
    # TODO

if __name__ == "__main__":
    solve()
`,
  js: `const fs = require("fs");
const input = fs.readFileSync(0, "utf8").trim().split(/\\s+/);
// TODO
`,
};

function defaultTemplate(lang) {
  return TEMPLATES[lang] || "// Write your code here...\n";
}

function qs(key) {
  const url = new URL(window.location.href);
  return url.searchParams.get(key);
}

function setTheme(mode) {
  state.theme = mode;
  localStorage.setItem("mj_theme", mode);
  document.documentElement.classList.toggle("dark", mode === "dark");
  if (state.editor) {
    monaco.editor.setTheme(state.theme === "dark" ? "vs-dark" : "vs");
  }
  render();
}

function api(path, opts = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  }).then((r) => r.json());
}

function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.innerText = msg;
  el.className =
    "fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl text-sm shadow-soft " +
    (type === "error"
      ? "bg-rose-600 text-white"
      : type === "success"
      ? "bg-emerald-600 text-white"
      : "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900");
  el.style.opacity = "1";
  setTimeout(() => (el.style.opacity = "0"), 2200);
}

// ✅ Normalize & find Sample IO from many possible keys
function getSampleIO(p) {
  if (!p) return { sampleIn: "", sampleOut: "" };

  const sampleIn =
    p.sample_input ||
    p.sampleInput ||
    p.input_sample ||
    p.sample_in ||
    p.example_input ||
    p.input_example ||
    (Array.isArray(p.examples) && p.examples[0]?.input) ||
    (Array.isArray(p.samples) && p.samples[0]?.input) ||
    "";

  const sampleOut =
    p.sample_output ||
    p.sampleOutput ||
    p.output_sample ||
    p.sample_out ||
    p.example_output ||
    p.output_example ||
    (Array.isArray(p.examples) && p.examples[0]?.output) ||
    (Array.isArray(p.samples) && p.samples[0]?.output) ||
    "";

  return { sampleIn, sampleOut };
}

// ✅ PROBLEM SORT FIX (frontend)
function sortProblemsById(arr) {
  return arr.sort((a, b) => {
    const ida = Number(a.id || a.problem_id || a.pid || 0);
    const idb = Number(b.id || b.problem_id || b.pid || 0);
    return ida - idb;
  });
}

/* ===== Monaco Loader + Mount (Single Fix) ===== */
function loadMonaco(cb) {
  if (window.monaco && window.monaco.editor) return cb();

  function loadRequire(next) {
    if (window.require) return next();
    const s = document.createElement("script");
    s.src =
      "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js";
    s.onload = next;
    s.onerror = () => console.error("Failed to load require.js");
    document.head.appendChild(s);
  }

  loadRequire(() => {
    window.require.config({
      paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs" },
    });
    window.require(["vs/editor/editor.main"], () => cb());
  });
}

function mountMonaco() {
  if (state.editor) return;

  loadMonaco(() => {
    const editorEl = document.getElementById("editor");
    if (!editorEl) return;

    editorEl.style.height = window.innerWidth < 768 ? "62vh" : "70vh";
    editorEl.innerHTML = "";

    state.editor = monaco.editor.create(editorEl, {
      value: state.code || defaultTemplate(state.language),
      language: langMap[state.language]?.monaco || "cpp",
      theme: state.theme === "dark" ? "vs-dark" : "vs",
      fontSize: 14,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      padding: { top: 14, bottom: 14 },
    });

    state.editor.onDidChangeModelContent(() => {
      state.code = state.editor.getValue();
    });

    window.addEventListener("resize", () => {
      editorEl.style.height = window.innerWidth < 768 ? "62vh" : "70vh";
      state.editor && state.editor.layout();
    });

    setTimeout(() => state.editor.layout(), 200);
  });
}

function setLanguage(lang) {
  state.language = lang;

  // ✅ If editor exists, switch language and inject template if empty
  if (state.editor) {
    monaco.editor.setModelLanguage(
      state.editor.getModel(),
      langMap[lang]?.monaco || "cpp"
    );

    // If user hasn't written anything meaningful, reset to template
    const current = state.editor.getValue().trim();
    if (!current || current === "// Write your code here..." || current.length < 10) {
      state.editor.setValue(defaultTemplate(lang));
    }

    monaco.editor.setTheme(state.theme === "dark" ? "vs-dark" : "vs");
  } else {
    state.code = defaultTemplate(lang);
  }
  render();
}

/* ===== Data Loads ===== */
async function loadProblems() {
  const data = await api("/api/problems");
  let probs = data.problems || data || [];

  // ✅ Ensure sorted by ID
  probs = sortProblemsById(probs);

  state.problems = probs;

  if (!state.selected && probs.length) {
    state.selected = probs[0];
  }
  render();
}

function selectProblem(p) {
  state.selected = p;
  state.mobileTab = "problem";
  render();
}

/* ===== Run & Submit ===== */
async function runCode() {
  if (!state.code.trim()) return toast("Code is empty", "error");
  state.loading = true;
  render();

  const payload = {
    user_id: state.userId,
    language: state.language,
    code: state.code,
    stdin: state.customInput || "",
  };

  try {
    const res = await api("/api/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.output = res.output || res.stderr || "";
    state.verdict = res.verdict || "";
    state.mobileTab = "output";
    toast("Run completed", "success");
  } catch (e) {
    toast("Run failed", "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function submitCode() {
  if (!state.selected) return toast("Select a problem first", "error");
  if (!state.code.trim()) return toast("Code is empty", "error");

  state.loading = true;
  state.job = null;
  state.output = "";
  state.verdict = "";
  render();

  const payload = {
    user_id: state.userId,
    problem_id: state.selected.id || state.selected.problem_id || state.selected.pid,
    language: state.language,
    code: state.code,
  };

  try {
    const res = await api("/api/submit", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!res.job_id) throw new Error("no job_id");
    state.job = { id: res.job_id, status: "queued" };
    state.mobileTab = "output";
    toast("Submitted • Checking…", "success");
    pollJob(res.job_id);
  } catch (e) {
    toast("Submit failed", "error");
    state.loading = false;
    render();
  }
}

async function pollJob(jobId) {
  const tick = async () => {
    try {
      const res = await api(`/api/job/${jobId}`);
      state.job = {
        id: jobId,
        status: res.status,
        result: res.result || null,
        error: res.error || null,
      };

      if (res.status === "done" || res.status === "error") {
        state.loading = false;
        state.output = res.result?.output || res.error || "";
        state.verdict = res.result?.verdict || (res.status === "error" ? "ERROR" : "");
        toast(res.status === "done" ? "Result ready" : "Error", res.status === "done" ? "success" : "error");
        render();
        return;
      }
      render();
      setTimeout(tick, 900);
    } catch (e) {
      state.loading = false;
      toast("Polling failed", "error");
      render();
    }
  };
  tick();
}

function badge(text) {
  const base = "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ";
  if (text === "AC" || text === "Accepted")
    return base + "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200";
  if (text === "WA" || text === "Wrong Answer")
    return base + "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-200";
  if (text)
    return base + "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-200";
  return base + "bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-200";
}

/* ===== UI RENDER ===== */
function layout() {
  return `
  <div id="toast" style="opacity:0; transition: opacity .2s ease;"></div>

  <div class="sticky top-0 z-40 border-b border-slate-200/60 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-2xl bg-slate-900 text-white dark:bg-white dark:text-slate-900 grid place-items-center font-black shadow-soft">MJ</div>
        <div class="leading-tight">
          <div class="font-extrabold tracking-tight">MyJudge</div>
          <div class="text-xs text-slate-500 dark:text-slate-400">Telegram WebApp • User: <span class="font-semibold">${state.userId}</span></div>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button onclick="setTheme('${state.theme === "dark" ? "light" : "dark"}')" class="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 hover:shadow-soft text-sm">
          ${state.theme === "dark" ? "☀️ Light" : "🌙 Dark"}
        </button>
        <a class="hidden sm:inline-flex px-3 py-2 rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-sm font-semibold hover:opacity-90 shadow-soft" href="#" onclick="state.page='editor';render();return false;">
          Open IDE
        </a>
      </div>
    </div>
  </div>

  <div class="max-w-7xl mx-auto px-4 py-6">
    <div class="grid grid-cols-12 gap-6">

      <aside class="hidden lg:block col-span-3">
        <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-3">
          ${navItem("dashboard","🏠","Dashboard")}
          ${navItem("problems","🧩","Problems")}
          ${navItem("editor","🧠","IDE")}
          ${navItem("rankings","🏆","Rankings")}
          ${navItem("profile","👤","Profile")}
          <div class="mt-3 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/30 text-xs text-slate-600 dark:text-slate-300">
            Tip: Desktop split-view • Mobile tabs • Output drawer.
          </div>
        </div>
      </aside>

      <main class="col-span-12 lg:col-span-9">
        ${renderPage()}
      </main>

    </div>
  </div>

  <nav class="lg:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200/60 dark:border-slate-800/70 bg-white/75 dark:bg-slate-950/40 backdrop-blur">
    <div class="max-w-7xl mx-auto px-4 py-2 grid grid-cols-5 gap-1 text-xs">
      ${mobileNav("dashboard","🏠","Home")}
      ${mobileNav("problems","🧩","Problems")}
      ${mobileNav("editor","🧠","IDE")}
      ${mobileNav("rankings","🏆","Rank")}
      ${mobileNav("profile","👤","Me")}
    </div>
  </nav>
  `;
}

function navItem(key, icon, label) {
  const active = state.page === key;
  return `
  <button onclick="state.page='${key}';render();" class="w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold
    ${active ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-soft" : "hover:bg-slate-100 dark:hover:bg-slate-900/40"}">
    <span class="text-lg">${icon}</span><span>${label}</span>
  </button>`;
}

function mobileNav(key, icon, label) {
  const active = state.page === key;
  return `
    <button onclick="state.page='${key}';render();" class="flex flex-col items-center justify-center py-2 rounded-2xl
      ${active ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-soft" : "text-slate-600 dark:text-slate-300"}">
      <div class="text-base">${icon}</div>
      <div class="leading-none">${label}</div>
    </button>
  `;
}

function renderPage() {
  if (state.page === "dashboard") return pageDashboard();
  if (state.page === "problems") return pageProblems();
  if (state.page === "rankings") return pageRankings();
  if (state.page === "profile") return pageProfile();
  return pageEditor();
}

function pageDashboard() {
  return `
    <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-6">
      <div class="text-2xl font-extrabold tracking-tight">Welcome back 👋</div>
      <div class="mt-1 text-slate-600 dark:text-slate-300">Open a problem, write code in the IDE, and submit — results will appear instantly via async queue.</div>
      <div class="grid sm:grid-cols-2 gap-4 mt-6">
        ${card("🧩", "Problems", `${state.problems.length} available`, "state.page='problems';render();")}
        ${card("🧠", "IDE", "Full-height Monaco editor", "state.page='editor';render();")}
        ${card("🏆", "Rankings", "Live leaderboard", "state.page='rankings';render();")}
        ${card("👤", "Profile", "Your stats & history", "state.page='profile';render();")}
      </div>
    </div>
  `;
}

function card(icon, title, desc, onclick) {
  return `
    <button onclick="${onclick}" class="text-left p-5 rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-slate-50/70 dark:bg-slate-900/30 hover:shadow-soft transition">
      <div class="text-2xl">${icon}</div>
      <div class="mt-2 font-extrabold">${title}</div>
      <div class="text-sm text-slate-600 dark:text-slate-300">${desc}</div>
    </button>
  `;
}

function pageProblems() {
  const list = state.problems.map((p) => {
    const id = p.id || p.problem_id || p.pid;
    const title = p.title || p.name || `Problem ${id}`;
    const diff = p.difficulty || p.level || "";
    const active = state.selected && (id === (state.selected.id || state.selected.problem_id || state.selected.pid));

    return `
    <button onclick='selectProblem(${JSON.stringify(p)})' class="w-full text-left px-4 py-3 rounded-2xl border
      ${active ? "border-indigo-500/50 bg-indigo-50 dark:bg-indigo-500/10" : "border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 hover:bg-slate-50 dark:hover:bg-slate-900/30"}
      transition">
      <div class="flex items-center justify-between gap-2">
        <div class="font-bold">${escapeHtml(title)}</div>
        <div class="${badge(diff)}">${diff || "—"}</div>
      </div>
      <div class="text-xs text-slate-500 dark:text-slate-400 mt-1">ID: ${id}</div>
    </button>`;
  }).join("");

  return `
  <div class="grid lg:grid-cols-2 gap-6">
    <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-4">
      <div class="flex items-center justify-between">
        <div class="font-extrabold text-lg">Problems</div>
        <button onclick="state.page='editor';render();" class="px-3 py-2 rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-sm font-semibold shadow-soft">Open IDE</button>
      </div>
      <div class="mt-4 space-y-3 max-h-[70vh] overflow-auto pr-1">${list || "No problems found"}</div>
    </div>

    <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-5">
      ${problemCard()}
    </div>
  </div>
  `;
}

function problemCard() {
  if (!state.selected) {
    return `<div class="text-slate-600 dark:text-slate-300">Select a problem to see details.</div>`;
  }

  const p = state.selected;
  const title = p.title || p.name || "Problem";
  const stmt = p.statement || p.description || p.problem || "";
  const { sampleIn, sampleOut } = getSampleIO(p);

  // fallback formats
  const inputFmt = p.input_format || p.input || "";
  const outputFmt = p.output_format || p.output || "";

  return `
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="text-xl font-extrabold tracking-tight">${escapeHtml(title)}</div>
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">ID: ${p.id || p.problem_id || p.pid}</div>
      </div>
      <button onclick="state.page='editor';state.mobileTab='editor';render();" class="px-3 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold shadow-soft hover:opacity-90">Solve</button>
    </div>

    <div class="mt-4 space-y-4 text-sm leading-relaxed max-h-[65vh] overflow-auto pr-1">
      <section>
        <div class="font-extrabold mb-1">Statement</div>
        <div class="text-slate-700 dark:text-slate-200 whitespace-pre-wrap">${escapeHtml(stmt) || "(No statement provided)"}</div>
      </section>

      <section>
        <div class="font-extrabold mb-1">Input Format</div>
        <div class="text-slate-700 dark:text-slate-200 whitespace-pre-wrap">${escapeHtml(inputFmt) || "(No input format provided)"}</div>
      </section>

      <section>
        <div class="font-extrabold mb-1">Output Format</div>
        <div class="text-slate-700 dark:text-slate-200 whitespace-pre-wrap">${escapeHtml(outputFmt) || "(No output format provided)"}</div>
      </section>

      <section>
        <div class="font-extrabold mb-1">Sample Input</div>
        <pre class="rounded-2xl p-4 bg-slate-950 text-slate-100 border border-slate-800 overflow-auto">${escapeHtml(sampleIn || "(No sample input provided)")}</pre>
      </section>

      <section>
        <div class="font-extrabold mb-1">Sample Output</div>
        <pre class="rounded-2xl p-4 bg-slate-950 text-slate-100 border border-slate-800 overflow-auto">${escapeHtml(sampleOut || "(No sample output provided)")}</pre>
      </section>
    </div>
  `;
}

function pageEditor() {
  const pTitle = state.selected
    ? (state.selected.title || state.selected.name || "Selected Problem")
    : "No problem selected";

  return `
  <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft overflow-hidden">

    <div class="p-4 border-b border-slate-200/60 dark:border-slate-800/70 flex flex-wrap items-center justify-between gap-3">
      <div>
        <div class="font-extrabold text-lg tracking-tight">IDE</div>
        <div class="text-xs text-slate-500 dark:text-slate-400">${escapeHtml(pTitle)}</div>
      </div>

      <div class="flex items-center gap-2">
        <select onchange="setLanguage(this.value)" class="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/40 text-sm">
          ${Object.keys(langMap).map(k => `<option value="${k}" ${k===state.language?"selected":""}>${langMap[k].label}</option>`).join("")}
        </select>

        <button onclick="runCode()" class="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/40 text-sm font-semibold hover:shadow-soft">
          ${state.loading ? "Running…" : "Run"}
        </button>
        <button onclick="submitCode()" class="px-4 py-2 rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-sm font-semibold shadow-soft hover:opacity-90">
          ${state.loading ? "Working…" : "Submit"}
        </button>
      </div>
    </div>

    <div class="lg:hidden flex gap-2 p-3 border-b border-slate-200/60 dark:border-slate-800/70">
      ${tabBtn("problem","📄","Problem")}
      ${tabBtn("editor","🧠","Editor")}
      ${tabBtn("output","🧾","Output")}
    </div>

    <div class="grid lg:grid-cols-2 gap-0">
      <div class="${state.mobileTab==='problem' ? '' : 'hidden'} lg:block border-r border-slate-200/60 dark:border-slate-800/70">
        <div class="p-5 max-h-[75vh] overflow-auto">
          ${problemCard()}
        </div>
      </div>

      <div class="${state.mobileTab==='editor' ? '' : 'hidden'} lg:block">
        <div class="p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="font-extrabold">Code</div>
            <button onclick="toggleDrawer()" class="text-xs px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/40 hover:shadow-soft">
              ${state.drawerOpen ? "Hide Output" : "Show Output"}
            </button>
          </div>

          <div id="editor" class="rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-900/5 dark:bg-slate-900/40"></div>

          <div class="mt-4 grid lg:grid-cols-2 gap-4">
            <div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/30 p-4">
              <div class="font-extrabold text-sm mb-2">Custom Input</div>
              <textarea oninput="state.customInput=this.value" class="w-full min-h-[110px] p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-950/40 text-sm outline-none" placeholder="stdin here...">${state.customInput||""}</textarea>
            </div>

            <div class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/30 p-4">
              <div class="flex items-center justify-between">
                <div class="font-extrabold text-sm">Status</div>
                <div class="${badge(state.verdict || (state.job?.status||""))}">${state.verdict || (state.job?.status || "idle")}</div>
              </div>
              <div class="mt-2 text-xs text-slate-500 dark:text-slate-400">
                ${state.job ? `Job: <span class="font-semibold">${state.job.id}</span>` : "Ready"}
              </div>
              <div class="mt-3 text-sm text-slate-700 dark:text-slate-200">
                ${state.loading ? "Working in background… (non-blocking)" : "Tip: Use Run for custom input • Submit for hidden tests"}
              </div>
            </div>
          </div>
        </div>

        <div class="${state.drawerOpen ? '' : 'hidden'} border-t border-slate-200/60 dark:border-slate-800/70">
          <div class="p-4">
            <div class="flex items-center justify-between mb-2">
              <div class="font-extrabold">Output</div>
              <button onclick="toggleDrawer()" class="text-xs px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/40 hover:shadow-soft">Close</button>
            </div>
            <pre class="min-h-[140px] max-h-[280px] overflow-auto rounded-2xl p-4 bg-slate-950 text-slate-100 text-sm border border-slate-800">${escapeHtml(state.output || "(No output yet)")}</pre>
          </div>
        </div>

      </div>
    </div>
  </div>
  `;
}

function tabBtn(key, icon, label) {
  const active = state.mobileTab === key;
  return `
    <button onclick="state.mobileTab='${key}';render();" class="flex-1 px-3 py-2 rounded-2xl text-sm font-semibold transition
      ${active ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-soft" : "bg-white/60 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-800"}">
      <span class="mr-1">${icon}</span>${label}
    </button>
  `;
}

function toggleDrawer() {
  state.drawerOpen = !state.drawerOpen;
  render();
}

function pageRankings() {
  return `
    <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-6">
      <div class="text-xl font-extrabold">Rankings</div>
      <div class="text-sm text-slate-600 dark:text-slate-300 mt-1">Connect this page to your existing /api/rankings endpoint.</div>
    </div>
  `;
}

function pageProfile() {
  return `
    <div class="rounded-3xl border border-slate-200/70 dark:border-slate-800/70 bg-white/70 dark:bg-slate-950/40 backdrop-blur shadow-soft p-6">
      <div class="text-xl font-extrabold">Profile</div>
      <div class="mt-2 text-slate-600 dark:text-slate-300">User: <span class="font-semibold">${state.userId}</span></div>
    </div>
  `;
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function render() {
  document.documentElement.classList.toggle("dark", state.theme === "dark");
  const root = document.getElementById("app");
  if (!root) return;
  root.innerHTML = layout();

  // mount monaco only when editor page visible
  if (state.page === "editor") {
    mountMonaco();
    if (state.editor) {
      monaco.editor.setTheme(state.theme === "dark" ? "vs-dark" : "vs");
    }
  }
}

function boot() {
  state.userId = qs("user_id") || "unknown";
  setTheme(state.theme);
  loadProblems();
  render();

  // ✅ default code template loaded at start
  if (!state.code) {
    state.code = defaultTemplate(state.language);
  }
}

window.setTheme = setTheme;
window.setLanguage = setLanguage;
window.runCode = runCode;
window.submitCode = submitCode;
window.toggleDrawer = toggleDrawer;
window.selectProblem = selectProblem;
window.state = state;

boot();
