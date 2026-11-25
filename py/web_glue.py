"""網頁用的轉換介面：在 Pyodide 裡執行，呼叫 aiapy。"""
import base64, io, json, re, zipfile
import xml.etree.ElementTree as ET
import aiapy

CATEGORY = [
    ("component_event", "事件"),
    ("component_method", "元件方法"),
    ("component_set_get", "元件屬性"),
    ("component_component_block", "元件"),
    ("controls_", "控制"),
    ("logic_", "邏輯"),
    ("math_", "數學"),
    ("text", "文字"),
    ("lists_", "清單"),
    ("color_", "顏色"),
    ("global_declaration", "變數"),
    ("lexical_variable", "變數"),
    ("local_declaration", "變數"),
    ("procedures_", "程序"),
    ("helpers_", "其他"),
]


def _cat(t):
    for prefix, name in CATEGORY:
        if t.startswith(prefix):
            return name
    return "其他"


def extract_code(reply):
    """從 AI 回覆抓出 ```python 程式碼區塊，以及區塊外的說明文字。"""
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
    if m:
        code = max(m, key=len)
        note = re.sub(r"```(?:python|py)?\s*\n.*?```", "", reply, flags=re.S).strip()
        return code.strip() + "\n", note
    return reply.strip() + "\n", ""


def _tree(comp, depth=0, out=None):
    if out is None:
        out = []
    props = {k: v for k, v in comp.items() if not k.startswith("$") and k != "Uuid"}
    out.append({"depth": depth, "name": comp["$Name"], "type": comp["$Type"],
                "text": props.get("Text") or props.get("Title") or ""})
    for c in comp.get("$Components", []):
        _tree(c, depth + 1, out)
    return out


def _summary(scm, bky):
    j = json.loads(scm.split("$JSON", 1)[1].rsplit("|#", 1)[0])
    tree = _tree(j["Properties"])
    counts, events, procs, globals_ = {}, [], [], []
    root = ET.fromstring(bky) if bky.strip() else ET.Element("xml")
    total = 0
    for b in root.iter():
        if b.tag.split("}")[-1] != "block":
            continue
        total += 1
        c = _cat(b.get("type"))
        counts[c] = counts.get(c, 0) + 1
    for b in root:
        if b.tag.split("}")[-1] != "block":
            continue
        t = b.get("type")
        m = next((c for c in b if c.tag.split("}")[-1] == "mutation"), None)
        f = {c.get("name"): c.text for c in b if c.tag.split("}")[-1] == "field"}
        if t == "component_event" and m is not None:
            events.append(f"{m.get('instance_name')}.{m.get('event_name')}")
        elif t.startswith("procedures_def"):
            procs.append(f.get("NAME", ""))
        elif t == "global_declaration":
            globals_.append(f.get("NAME", ""))
    return {"tree": tree, "counts": counts, "total": total, "events": events,
            "procedures": procs, "globals": globals_}


UPLOAD = {"path": None}


def build(text, app_name, strict=True, keep_upload=True):
    """編譯 AIA-Py 文字。回傳 JSON 字串：ok、error、aia（base64）、screens（摘要）。
    keep_upload=True 且先前有上傳 .aia 時，沿用它的素材檔和擴充元件。"""
    try:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", app_name or ""):
            raise aiapy.CompileError("專案名稱只能用英文字母開頭，後面接英文、數字或底線")
        up = UPLOAD["path"] if keep_upload else None
        assets, exts = None, None
        if up:
            assets = {k: v for k, v in aiapy.list_assets(up).items() if not k.startswith("external_comps/")}
            exts = aiapy.load_extensions(up) or None
        if strict:
            aiapy.compile_project(text, app_name, strict=True, extensions=exts)   # 先做嚴格檢查
        aiapy.build_aia(text, "/tmp/out.aia", app_name, assets=assets, extensions=exts)
        data = open("/tmp/out.aia", "rb").read()
        screens = {n: _summary(scm, bky) for n, scm, bky in aiapy.screens_of("/tmp/out.aia")}
        return json.dumps({"ok": True, "aia": base64.b64encode(data).decode(),
                           "screens": screens}, ensure_ascii=False)
    except SyntaxError as e:
        return json.dumps({"ok": False, "error": f"語法錯誤（第 {e.lineno} 行）：{e.msg}"}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


def clear_upload():
    UPLOAD["path"] = None


def decompile_b64(b64):
    """上傳的 .aia（base64）→ AIA-Py 文字。"""
    try:
        data = base64.b64decode(b64)
        with open("/tmp/upload.aia", "wb") as fh:
            fh.write(data)
        UPLOAD["path"] = "/tmp/upload.aia"
        name = "MyApp"
        with zipfile.ZipFile("/tmp/upload.aia") as z:
            for n in z.namelist():
                m = re.match(r"src/appinventor/[^/]+/([^/]+)/", n)
                if m:
                    name = m.group(1)
                    break
        return json.dumps({"ok": True, "text": aiapy.decompile("/tmp/upload.aia"), "name": name},
                          ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
