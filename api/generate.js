// 用伺服器的 Gemini 金鑰產生 AIA-Py（系統提示詞由伺服器端讀取，不接受前端覆寫）
const fs = require("fs");
const path = require("path");
let PROMPT = null;

module.exports = async (req, res) => {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return res.status(404).json({ error: "此網站沒有設定共用金鑰，請填自己的 Gemini 金鑰" });
  if (req.method !== "POST") return res.status(405).json({ error: "只接受 POST" });
  try {
    if (!PROMPT) PROMPT = fs.readFileSync(path.join(process.cwd(), "prompt.md"), "utf8");
    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
    const contents = Array.isArray(body.contents) ? body.contents.slice(-8) : [];
    const size = JSON.stringify(contents).length;
    if (!contents.length || size > 60000) return res.status(400).json({ error: "請求內容太長或是空的" });
    const model = /^gemini-[\w.-]+$/.test(body.model || "") ? body.model : (process.env.GEMINI_MODEL || "gemini-flash-latest");
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: PROMPT }] },
        contents,
        generationConfig: { temperature: 0.3 },
      }),
    });
    const j = await r.json();
    res.status(r.status).json(j);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
};
