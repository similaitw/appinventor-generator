# App Inventor 產生器

用中文描述想做的 App，AI 寫出 **AIA-Py**（一種長得像 Python 的 App Inventor 描述語言），網頁再把它轉成可以直接匯入 [MIT App Inventor](https://ai2.appinventor.mit.edu/) 的 `.aia` 專案檔。

## 使用方式
1. 描述 App（或匯入既有的 `.aia` 來修改）。
2. 請 AI 寫程式：
   - **複製提示詞**：貼到 Gemini／ChatGPT／Claude，再把回覆貼回來（免費、免金鑰）。
   - **Gemini 自動產生**：填自己的 Gemini API 金鑰（只存在瀏覽器），出錯會自動把錯誤丟回給 AI 修正。
3. 轉換器檢查元件、屬性、事件、方法名稱與參數，通過後下載 `.aia`。

## 架構
- 純靜態網站，轉換器 `py/aiapy.py` 用 [Pyodide](https://pyodide.org/) 在瀏覽器執行，程式碼不會上傳。
- `py/ai2_components.json`：從 App Inventor 線上版（2026-11-20 建置）抓下的 107 種元件規格，用來做嚴格檢查。
- `prompt.md`：給 AI 的系統提示詞（AIA-Py 語法＋範例＋元件參考）。
- `api/`：選用的 Vercel 函式。若在 Vercel 設定環境變數 `GEMINI_API_KEY`（可加 `GEMINI_MODEL`），使用者不填金鑰也能用「Gemini 自動產生」。

## 轉換器測試
- 128 個 `.aia`（三家國中課本、MIT 官方教學、練習題）反編譯再編譯，內容全部一致。
- `samples/`：7 個用 AIA-Py 寫的測試 App 與原始碼。

MIT App Inventor 是 MIT 的商標；本專案與 MIT 無關。
