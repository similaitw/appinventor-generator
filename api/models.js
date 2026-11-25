// 用伺服器金鑰列出可用的 Gemini 模型
module.exports = async (req, res) => {
  const key = process.env.GEMINI_API_KEY;
  if (!key) return res.status(404).json({ error: "此網站沒有設定共用金鑰" });
  try {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key=${key}`);
    const j = await r.json();
    const models = (j.models || [])
      .filter((m) => (m.supportedGenerationMethods || []).includes("generateContent"))
      .map((m) => m.name.replace("models/", ""))
      .filter((n) => /^gemini-/.test(n) && !/(tts|image|embedding|live|audio|vision)/.test(n));
    res.setHeader("Cache-Control", "s-maxage=3600");
    res.status(200).json({ models });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
};
