// 回報這個部署是否設定了共用的 Gemini 金鑰（不回傳金鑰本身）
module.exports = (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ serverKey: !!process.env.GEMINI_API_KEY, model: process.env.GEMINI_MODEL || "" });
};
