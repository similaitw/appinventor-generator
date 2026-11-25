"use strict";
const $ = (id) => document.getElementById(id);
const state = { py: null, glue: null, prompt: "", lastError: "", lastAia: null, history: [], serverKey: false };

const EXAMPLES = [
  ["BMI 計算機", "做一個 BMI 計算機，輸入身高（公分）和體重（公斤），按按鈕顯示 BMI（小數一位）和體位建議，過重時文字變紅色。"],
  ["猜數字", "電腦隨機想一個 1 到 100 的數字，玩家輸入猜測，提示太大或太小，猜中時跳出對話框顯示猜了幾次，按確定重新開始。"],
  ["骰子", "做一個擲骰子 App，按按鈕後點數快速跳動一秒再停下，顯示 1 到 6 的結果，擲出 6 時變紅色。"],
  ["待辦清單", "做一個待辦清單，可以輸入事項按新增，清單顯示所有事項，點一下事項就刪除，關掉 App 再打開資料還在。"],
  ["畫畫板", "做一個畫畫板，手指拖曳畫線，有紅、藍、黑三個顏色按鈕、線條粗細滑桿和清除按鈕。"],
  ["接球遊戲", "做一個接球遊戲，球在畫布上反彈，點到球加一分，球掉到底部分數歸零，畫面上方顯示分數。"],
  ["英文朗讀", "輸入一段英文，按按鈕用語音念出來，可以用滑桿調整說話速度。"],
  ["登入切換畫面", "做一個登入畫面，帳號 student、密碼 1234 才能進入第二個畫面，第二個畫面顯示歡迎訊息和登出按鈕。"],
];

// ---------- 初始化 ----------
async function initPy() {
  const pill = $("pyStatus");
  try {
    const [aiapy, comps, glue, prompt] = await Promise.all([
      fetch("py/aiapy.py").then((r) => r.text()),
      fetch("py/ai2_components.json").then((r) => r.text()),
      fetch("py/web_glue.py").then((r) => r.text()),
      fetch("prompt.md").then((r) => r.text()),
    ]);
    state.prompt = prompt;
    $("specText").textContent = prompt;
    const py = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/npm/pyodide@0.29.5/" });
    py.FS.mkdirTree("/app");
    py.FS.writeFile("/app/aiapy.py", aiapy);
    py.FS.writeFile("/app/ai2_components.json", comps);
    py.FS.writeFile("/app/web_glue.py", glue);
    py.runPython('import sys; sys.path.insert(0, "/app"); import web_glue');
    state.py = py;
    state.glue = py.globals.get("web_glue");
    pill.textContent = "轉換器就緒";
    pill.className = "pill ready";
  } catch (e) {
    console.error(e);
    pill.textContent = "轉換器載入失敗，請重新整理";
    pill.className = "pill fail";
  }
}

function buildChips() {
  const box = $("chips");
  for (const [label, text] of EXAMPLES) {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = label;
    b.onclick = () => { $("desc").value = text; };
    box.appendChild(b);
  }
}

// ---------- 提示詞 ----------
function userMessage() {
  const desc = $("desc").value.trim();
  const code = $("code").value.trim();
  let msg = `# 使用者需求\n${desc || "（請依現有程式改進）"}`;
  if (state.uploaded && code) {
    msg += `\n\n# 現有程式（請在這個基礎上修改，保留原本的元件名稱，輸出修改後的完整程式）\n\`\`\`python\n${code}\n\`\`\``;
  }
  return msg;
}
function fullPrompt() { return `${state.prompt}\n\n${userMessage()}`; }
function fixMessage(err) {
  return `轉換器檢查出錯誤：\n${err}\n\n請修正這個錯誤，輸出修正後的完整 AIA-Py 程式（只要一個 \`\`\`python 程式碼區塊）。`;
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const t = document.createElement("textarea");
    t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  const old = btn.textContent;
  btn.textContent = "已複製！";
  setTimeout(() => (btn.textContent = old), 1500);
}

// ---------- 檢查與轉換 ----------
function setNote(note) {
  const box = $("aiNote");
  if (note) { box.textContent = note; box.classList.remove("hidden"); } else box.classList.add("hidden");
}

function applyReply(reply) {
  const [code, note] = state.glue.extract_code(reply).toJs();
  $("code").value = code;
  setNote(note);
}

function check() {
  if (!state.glue) { alert("轉換器還在載入，請稍等幾秒"); return null; }
  const code = $("code").value;
  if (!code.trim()) { showError("編輯器是空的"); return null; }
  const r = JSON.parse(state.glue.build(code, $("appName").value.trim(), true, !!state.uploaded));
  if (!r.ok) { showError(r.error); $("step4").classList.add("hidden"); return r; }
  hideError();
  state.lastAia = r.aia;
  renderResult(r.screens);
  $("checkMsg").textContent = "✓ 檢查通過，可以下載了";
  return r;
}

function showError(msg) {
  state.lastError = msg;
  $("errorText").textContent = "✗ " + msg;
  $("errorBox").classList.remove("hidden");
  $("checkMsg").textContent = "";
}
function hideError() { $("errorBox").classList.add("hidden"); state.lastError = ""; }

const TYPE_ZH = {
  Form: "畫面", Button: "按鈕", Label: "標籤", TextBox: "文字輸入盒", PasswordTextBox: "密碼輸入盒", Image: "圖片",
  CheckBox: "核取方塊", Switch: "開關", Slider: "滑桿", Spinner: "下拉選單", ListPicker: "清單選擇器", ListView: "清單顯示器",
  DatePicker: "日期選擇器", TimePicker: "時間選擇器", Notifier: "對話框", HorizontalArrangement: "水平配置",
  VerticalArrangement: "垂直配置", TableArrangement: "表格配置", HorizontalScrollArrangement: "水平捲動配置",
  VerticalScrollArrangement: "垂直捲動配置", Canvas: "畫布", ImageSprite: "圖片精靈", Ball: "球", Clock: "計時器",
  Sound: "音效", Player: "音樂播放器", TextToSpeech: "文字轉語音", SpeechRecognizer: "語音辨識", TinyDB: "微型資料庫",
  Web: "網路", WebViewer: "網路瀏覽器", AccelerometerSensor: "加速度感測器", OrientationSensor: "方向感測器",
  LocationSensor: "位置感測器", Camera: "照相機", ImagePicker: "圖像選擇器", ActivityStarter: "Activity 啟動器",
  Sharing: "分享", Texting: "簡訊", PhoneCall: "電話",
};

function renderResult(screens) {
  const tree = $("tree"), stats = $("stats");
  tree.innerHTML = ""; stats.innerHTML = "";
  for (const [name, s] of Object.entries(screens)) {
    const t = document.createElement("div");
    t.innerHTML = `<div class="screen-title">${esc(name)}</div>`;
    for (const n of s.tree) {
      const d = document.createElement("div");
      d.className = "node";
      d.style.paddingLeft = n.depth * 18 + "px";
      d.innerHTML = `${esc(n.name)}<span class="type">${esc(TYPE_ZH[n.type] || n.type)}</span>` +
        (n.text ? `<span class="txt">「${esc(String(n.text).slice(0, 20))}」</span>` : "");
      t.appendChild(d);
    }
    tree.appendChild(t);

    const st = document.createElement("div");
    st.innerHTML = `<div class="screen-title">${esc(name)}：共 ${s.total} 個積木</div>`;
    const max = Math.max(1, ...Object.values(s.counts));
    for (const [k, v] of Object.entries(s.counts).sort((a, b) => b[1] - a[1])) {
      st.innerHTML += `<div class="bar"><span class="label">${esc(k)}</span><span class="fill" style="width:${(v / max) * 160}px"></span>${v}</div>`;
    }
    const tags = [];
    if (s.events.length) tags.push("事件：" + s.events.join("、"));
    if (s.procedures.length) tags.push("程序：" + s.procedures.join("、"));
    if (s.globals.length) tags.push("全域變數：" + s.globals.join("、"));
    st.innerHTML += `<div class="tags">${tags.map(esc).join("<br>")}</div>`;
    stats.appendChild(st);
  }
  $("step4").classList.remove("hidden");
}

function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function download() {
  if (!state.lastAia) return;
  const bin = Uint8Array.from(atob(state.lastAia), (c) => c.charCodeAt(0));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([bin], { type: "application/zip" }));
  a.download = `${$("appName").value.trim() || "MyApp"}.aia`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ---------- 匯入既有 .aia ----------
async function onUpload(file) {
  if (!state.glue) { alert("轉換器還在載入，請稍等幾秒"); return; }
  const buf = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  const r = JSON.parse(state.glue.decompile_b64(btoa(bin)));
  if (!r.ok) { alert("無法讀取這個 .aia：" + r.error); return; }
  state.uploaded = file.name;
  $("code").value = r.text;
  $("appName").value = r.name;
  setNote("");
  $("uploadInfo").innerHTML = `已匯入 ${esc(file.name)}（圖片素材與擴充元件會保留）。在上面描述想怎麼修改，再請 AI 產生。 <button class="ghost small" id="clearUpload">取消匯入</button>`;
  $("clearUpload").onclick = () => {
    state.uploaded = null; state.glue.clear_upload(); $("uploadInfo").textContent = "";
  };
  check();
}

// ---------- Gemini ----------
async function loadServerStatus() {
  try {
    const r = await fetch("/api/status");
    if (r.ok) {
      const j = await r.json();
      state.serverKey = !!j.serverKey;
      state.serverModel = j.model || "";
      if (state.serverKey) $("serverKeyNote").classList.remove("hidden");
    }
  } catch { /* 靜態預覽時沒有 /api */ }
}

function versionKey(name) {
  const m = name.match(/gemini-(\d+(?:\.\d+)?)/);
  return m ? parseFloat(m[1]) : 0;
}

async function loadModels() {
  const key = $("apiKey").value.trim();
  const sel = $("model");
  let names = [];
  try {
    if (key) {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key=${encodeURIComponent(key)}`);
      if (!r.ok) throw new Error(`金鑰無法使用（HTTP ${r.status}）`);
      const j = await r.json();
      names = (j.models || [])
        .filter((m) => (m.supportedGenerationMethods || []).includes("generateContent"))
        .map((m) => m.name.replace("models/", ""))
        .filter((n) => /^gemini-/.test(n) && !/(tts|image|embedding|live|audio|vision)/.test(n));
    } else if (state.serverKey) {
      const r = await fetch("/api/models");
      if (r.ok) names = (await r.json()).models || [];
    }
  } catch (e) {
    log("✗ " + e.message);
  }
  names.sort((a, b) => versionKey(b) - versionKey(a) || (a.includes("flash") ? -1 : 1));
  sel.innerHTML = "";
  if (!names.length) { sel.innerHTML = '<option value="">（請先填金鑰）</option>'; return; }
  const preferred = names.find((n) => /flash/.test(n) && !/lite|preview|exp/.test(n)) || names[0];
  for (const n of names) {
    const o = document.createElement("option");
    o.value = o.textContent = n;
    if (n === (localStorage.getItem("aig_model") || preferred)) o.selected = true;
    sel.appendChild(o);
  }
}

async function callGemini(contents) {
  const key = $("apiKey").value.trim();
  const model = $("model").value;
  const body = {
    systemInstruction: { parts: [{ text: state.prompt }] },
    contents,
    generationConfig: { temperature: 0.3 },
  };
  let r;
  if (key) {
    if (!model) throw new Error("請先選擇模型");
    r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(key)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } else if (state.serverKey) {
    r = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, contents }),
    });
  } else {
    throw new Error("請填入 Gemini API 金鑰，或改用「複製提示詞」");
  }
  const j = await r.json();
  if (!r.ok) throw new Error(j.error?.message || j.error || `HTTP ${r.status}`);
  const parts = j.candidates?.[0]?.content?.parts || [];
  const text = parts.filter((p) => !p.thought).map((p) => p.text || "").join("");
  if (!text) throw new Error("AI 沒有回應內容（可能被安全機制擋下），請換個說法再試");
  return text;
}

function log(msg) { $("genLog").textContent += msg + "\n"; }

async function generate() {
  if (!state.glue) { alert("轉換器還在載入，請稍等幾秒"); return; }
  if (!$("desc").value.trim() && !state.uploaded) { alert("請先描述你想做的 App"); return; }
  const btn = $("generate");
  btn.disabled = true;
  $("genLog").textContent = "";
  localStorage.setItem("aig_model", $("model").value);
  const maxFix = parseInt($("maxFix").value, 10);
  const contents = [{ role: "user", parts: [{ text: userMessage() }] }];
  try {
    for (let round = 0; round <= maxFix; round++) {
      log(round === 0 ? "⋯ AI 產生中（約 10～40 秒）" : `⋯ 第 ${round} 次自動修正`);
      const t0 = Date.now();
      const reply = await callGemini(contents);
      log(`  回應完成（${((Date.now() - t0) / 1000).toFixed(0)} 秒）`);
      applyReply(reply);
      const r = check();
      if (r && r.ok) { log("✓ 檢查通過"); $("step3").scrollIntoView({ behavior: "smooth" }); return; }
      log("✗ " + (r ? r.error : "檢查失敗"));
      contents.push({ role: "model", parts: [{ text: reply }] });
      contents.push({ role: "user", parts: [{ text: fixMessage(r ? r.error : "") }] });
    }
    log("自動修正次數用完了。可以手動修改程式，或按「複製修正提示詞」貼到其他 AI。");
  } catch (e) {
    log("✗ " + e.message);
  } finally {
    btn.disabled = false;
  }
}

// ---------- 事件綁定 ----------
function bind() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
      $("pane-copy").classList.toggle("hidden", t.dataset.tab !== "copy");
      $("pane-api").classList.toggle("hidden", t.dataset.tab !== "api");
    };
  });
  $("copyPrompt").onclick = (e) => {
    if (!$("desc").value.trim() && !state.uploaded) { alert("請先描述你想做的 App"); return; }
    copyText(fullPrompt(), e.target);
  };
  $("usePaste").onclick = () => {
    const t = $("pasteReply").value;
    if (!t.trim()) { alert("請先貼上 AI 的回覆"); return; }
    applyReply(t);
    check();
  };
  $("check").onclick = check;
  $("copyFix").onclick = (e) => copyText(fixMessage(state.lastError), e.target);
  $("download").onclick = download;
  $("uploadBtn").onclick = () => $("uploadInput").click();
  $("uploadInput").onchange = (e) => { if (e.target.files[0]) onUpload(e.target.files[0]); e.target.value = ""; };
  $("showSpec").onclick = () => $("specDialog").showModal();
  $("closeSpec").onclick = () => $("specDialog").close();
  $("generate").onclick = generate;
  $("loadModels").onclick = loadModels;
  const k = localStorage.getItem("aig_key");
  if (k) $("apiKey").value = k;
  $("apiKey").onchange = () => {
    localStorage.setItem("aig_key", $("apiKey").value.trim());
    loadModels();
  };
}

buildChips();
bind();
initPy();
loadServerStatus().then(() => { if ($("apiKey").value || state.serverKey) loadModels(); });
