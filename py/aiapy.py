"""AIA-Py：用 Python 語法描述 App Inventor 專案，雙向轉換 .aia。

  decompile(aia_path) -> 文字
  compile_text(text, app_name) -> (scm, bky)
  build_aia(text, out_path, app_name)

語法（皆為合法 Python，可直接用 ast 解析，中文名稱可用）：
  Screen1 = Form(AppName="P1", Title="Screen1")
  標籤1 = Label(Screen1, Text="哈囉", FontSize=20)      # 元件：類型(父容器, 屬性=值)
  答案 = 0                                               # 全域變數
  @when(按鈕_計算.Click)                                 # 事件
  def _():
      標籤1.Text = join("你好", 文字輸入盒.Text)          # 設定屬性 / 取得屬性
      for i in irange(1, 10, 1): ...                     # App Inventor 的 for 範圍（含終點）
      if a == b and c < d: ... elif ...: ... else: ...
      while 條件: ...
      add_items(清單, x)
  運算：+ - * /  比較 == != < <= > >=   and/or
  函式：add(a,b,c)  multiply(a,b,c)  join(a,b,...)  remainder(a,b)  quotient(a,b)  a % b（模數）
  清單：[] / [a, b]
"""
import ast, json, random, re, string, zipfile, io
import xml.etree.ElementTree as ET

YA_VERSION = "226"
LANG_VERSION = "36"
COMP_VERSION = {"Form": "31", "Button": "7", "Label": "5", "TextBox": "6",
                "PasswordTextBox": "5", "HorizontalArrangement": "4",
                "VerticalArrangement": "4", "Image": "4", "Clock": "4",
                "Web": "9", "TableArrangement": "1"}
# 事件參數（App Inventor 規格，依序）
EVENT_PARAMS = {
    ("Web", "GotText"): ["url", "responseCode", "responseType", "responseContent"],
    ("Canvas", "Touched"): ["x", "y", "touchedAnySprite"],
    ("Notifier", "AfterChoosing"): ["choice"],
    ("Clock", "Timer"): [],
    ("Canvas", "TouchDown"): ["x", "y"],
    ("Canvas", "TouchUp"): ["x", "y"],
    ("Canvas", "Dragged"): ["startX", "startY", "prevX", "prevY", "currentX", "currentY", "draggedAnySprite"],
    ("Canvas", "Flung"): ["x", "y", "speed", "heading", "xvel", "yvel", "flungSprite"],
    ("ImageSprite", "Touched"): ["x", "y"],
    ("ImageSprite", "CollidedWith"): ["other"],
    ("ImageSprite", "EdgeReached"): ["edge"],
    ("ImageSprite", "Dragged"): ["startX", "startY", "prevX", "prevY", "currentX", "currentY"],
    ("Ball", "Touched"): ["x", "y"],
    ("Ball", "CollidedWith"): ["other"],
    ("Ball", "EdgeReached"): ["edge"],
    ("Slider", "PositionChanged"): ["thumbPosition"],
    ("Notifier", "AfterTextInput"): ["response"],
    ("TextToSpeech", "AfterSpeaking"): ["result"],
    ("SpeechRecognizer", "AfterGettingText"): ["result", "partial"],
    ("LocationSensor", "LocationChanged"): ["latitude", "longitude", "altitude", "speed"],
    ("Camera", "AfterPicture"): ["image"],
    ("Form", "OtherScreenClosed"): ["otherScreenName", "result"],
}
CMP = {"EQ": ast.Eq, "NEQ": ast.NotEq, "LT": ast.Lt, "LTE": ast.LtE, "GT": ast.Gt, "GTE": ast.GtE}
CMP_SYM = {"EQ": "==", "NEQ": "!=", "LT": "<", "LTE": "<=", "GT": ">", "GTE": ">="}
NS = "{http://www.w3.org/1999/xhtml}"
# ---- App Inventor 元件目錄（從線上版 BlocklyPanel_getComponentsJSONString() 抓下的精簡版）
import os, difflib
_CAT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai2_components.json")
def _from_compact(c):
    """ai2_components.json 精簡格式 -> 內部目錄格式"""
    return {
        "version": str(c["v"]), "nonvisible": c["nv"], "external": c.get("ext", False),
        "fqcn": c.get("t", ""),
        "props": {p[0] for p in c["props"]},
        "bp": {p[0]: p[2] for p in c["bp"]},
        "events": {e[0]: [x.split(":")[0] for x in e[1]] for e in c["ev"]},
        "methods": {m[0]: [x.split(":")[0] for x in m[1]] for m in c["me"]},
    }

def compact_component(c):
    """App Inventor 元件描述（components.json / BlocklyPanel_getComponentsJSONString 的一筆）-> 精簡格式。
    與瀏覽器端抓 ai2_components.json 時用的轉換相同。"""
    P = lambda ps: [p["name"] + ":" + p.get("type", "") for p in (ps or [])]
    live = lambda xs: [x for x in (xs or []) if str(x.get("deprecated", "false")) != "true"]
    return {"t": c.get("type", ""), "n": c["name"], "v": c.get("version", "1"),
            "c": c.get("categoryString", ""), "nv": str(c.get("nonVisible", "false")) == "true",
            "ext": str(c.get("external", "false")) == "true",
            "props": [[p["name"], p.get("editorType", ""), p.get("defaultValue", "")] for p in (c.get("properties") or [])],
            "bp": [[p["name"], p.get("type", ""), p.get("rw", "")] for p in live(c.get("blockProperties"))],
            "ev": [[e["name"], P(e.get("params"))] for e in live(c.get("events"))],
            "me": [[m["name"], P(m.get("params")), m.get("returnType", "")] for m in live(c.get("methods"))]}

CATALOG = {}
if os.path.exists(_CAT_PATH):
    for _c in json.load(open(_CAT_PATH, encoding="utf-8")):
        CATALOG[_c["n"]] = _from_compact(_c)

# ---- 擴充元件（.aix / .aia 裡的 assets/external_comps/<套件>/）
class Extension:
    """一個擴充元件套件：files 是 {套件內相對路徑: bytes}，components 是精簡格式清單"""
    def __init__(self, package, files):
        self.package = package
        self.files = files
        descs = []
        if "components.json" in files:                      # 新格式：清單
            descs = json.loads(files["components.json"].decode("utf-8"))
        elif "component.json" in files:                     # 舊格式：單一物件
            descs = [json.loads(files["component.json"].decode("utf-8"))]
        self.components = [compact_component(d) for d in descs]

    @property
    def names(self):
        return [c["n"] for c in self.components]

    def catalog(self):
        return {c["n"]: _from_compact(c) for c in self.components}

def load_extensions(path_or_bytes):
    """從 .aix 或 .aia（路徑或 bytes）讀出擴充元件。回傳 [Extension]"""
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    z = zipfile.ZipFile(src)
    groups = {}
    for n in z.namelist():
        if n.endswith("/"):
            continue
        if n.startswith("assets/external_comps/"):          # .aia
            rest = n[len("assets/external_comps/"):]
        elif not n.startswith(("src/", "assets/", "youngandroidproject/")):  # .aix：<套件>/...
            rest = n
        else:
            continue
        if "/" not in rest:
            continue
        pkg, rel = rest.split("/", 1)
        groups.setdefault(pkg, {})[rel] = z.read(n)
    return [Extension(pkg, files) for pkg, files in groups.items()
            if "components.json" in files or "component.json" in files]

def _ext_catalog(extensions):
    cat = {}
    for e in extensions or []:
        cat.update(e.catalog())
    return cat
# scm 裡會出現、但不在設計師屬性清單的結構性屬性
_STRUCT_PROPS = {"Width", "Height", "Column", "Row", "Uuid", "AppName", "Title", "Sizing", "Theme", "VersionCode", "VersionName",
                 "ShowListsAsJson", "TutorialURL", "BlocksToolkit", "DefaultFileScope", "AccentColor",
                 "PrimaryColor", "PrimaryColorDark", "ActionBar", "Icon", "AppIcon"}

def _hint(name, pool):
    m = difflib.get_close_matches(name, list(pool), n=3)
    return f"（你是不是要寫：{'、'.join(m)}？）" if m else ""

# ---- 好讀語法對照表：函式名 -> (積木類型, 固定欄位, 參數欄位, 輸入插槽, 突變屬性, 是否為敘述)
def _S(t, fields=None, pfields=(), inputs=(), mut=None, stmt=False):
    return (t, fields or {}, tuple(pfields), tuple(inputs), mut, stmt)
SUGAR = {
    "sqrt": _S("math_single", {"OP": "ROOT"}, inputs=["NUM"]),
    "abs": _S("math_abs", {"OP": "ABS"}, inputs=["NUM"]),
    "neg": _S("math_neg", {"OP": "NEG"}, inputs=["NUM"]),
    "log": _S("math_single", {"OP": "LN"}, inputs=["NUM"]),
    "exp": _S("math_single", {"OP": "EXP"}, inputs=["NUM"]),
    "round": _S("math_round", {"OP": "ROUND"}, inputs=["NUM"]),
    "ceiling": _S("math_round", {"OP": "CEILING"}, inputs=["NUM"]),
    "floor": _S("math_round", {"OP": "FLOOR"}, inputs=["NUM"]),
    "sin": _S("math_trig", {"OP": "SIN"}, inputs=["NUM"]),
    "cos": _S("math_trig", {"OP": "COS"}, inputs=["NUM"]),
    "tan": _S("math_trig", {"OP": "TAN"}, inputs=["NUM"]),
    "power": _S("math_power", inputs=["A", "B"]),
    "format_decimal": _S("math_format_as_decimal", inputs=["NUM", "PLACES"]),
    "is_number": _S("math_is_a_number", {"OP": "NUMBER"}, inputs=["NUM"]),
    "random_fraction": _S("math_random_float"),
    "avg_of": _S("math_on_list2", {"OP": "AVG"}, inputs=["LIST"]),
    "min_of": _S("math_on_list2", {"OP": "MIN"}, inputs=["LIST"]),
    "max_of": _S("math_on_list2", {"OP": "MAX"}, inputs=["LIST"]),
    "length": _S("text_length", inputs=["VALUE"]),
    "is_empty": _S("text_isEmpty", inputs=["VALUE"]),
    "list_is_empty": _S("lists_is_empty", inputs=["LIST"]),
    "upcase": _S("text_changeCase", {"OP": "UPCASE"}, inputs=["TEXT"]),
    "downcase": _S("text_changeCase", {"OP": "DOWNCASE"}, inputs=["TEXT"]),
    "trim": _S("text_trim", inputs=["TEXT"]),
    "contains": _S("text_contains", {"OP": "CONTAINS"}, inputs=["TEXT", "PIECE"], mut={"mode": "CONTAINS"}),
    "split": _S("text_split", {"OP": "SPLIT"}, inputs=["TEXT", "AT"], mut={"mode": "SPLIT"}),
    "split_at_spaces": _S("text_split_at_spaces", inputs=["TEXT"]),
    "replace_all": _S("text_replace_all", inputs=["TEXT", "SEGMENT", "REPLACEMENT"]),
    "segment": _S("text_segment", inputs=["TEXT", "START", "LENGTH"]),
    "starts_at": _S("text_starts_at", inputs=["TEXT", "PIECE"]),
    "reverse_text": _S("text_reverse", inputs=["VALUE"]),
    "index_of": _S("lists_position_in", inputs=["ITEM", "LIST"]),
    "pick_random": _S("lists_pick_random_item", inputs=["LIST"]),
    "copy_list": _S("lists_copy", inputs=["LIST"]),
    "reverse_list": _S("lists_reverse", inputs=["LIST"]),
    "get_start_value": _S("controls_getStartValue"),
    "equal": _S("logic_compare", {"OP": "EQ"}, inputs=["A", "B"]),
    "not_equal": _S("logic_compare", {"OP": "NEQ"}, inputs=["A", "B"]),
    "screen_name": _S("helpers_screen_names", pfields=["SCREEN"]),
    "asset": _S("helpers_assets", pfields=["ASSET"]),
    "make_color": _S("color_make_color", inputs=["COLORLIST"]),
    "open_screen": _S("controls_openAnotherScreen", inputs=["SCREEN"], stmt=True),
    "open_screen_with_value": _S("controls_openAnotherScreenWithStartValue", inputs=["SCREENNAME", "STARTVALUE"], stmt=True),
    "close_screen": _S("controls_closeScreen", stmt=True),
    "close_screen_with_value": _S("controls_closeScreenWithValue", inputs=["SCREEN"], stmt=True),
    "remove_item": _S("lists_remove_item", inputs=["LIST", "INDEX"], stmt=True),
    "replace_item": _S("lists_replace_item", inputs=["LIST", "NUM", "ITEM"], stmt=True),
    "insert_item": _S("lists_insert_item", inputs=["LIST", "INDEX", "ITEM"], stmt=True),
    "append_list": _S("lists_append_list", inputs=["LIST0", "LIST1"], stmt=True),
    "evaluate_ignore": _S("controls_eval_but_ignore", inputs=["VALUE"], stmt=True),
}
COLORS = {"BLACK": "#000000", "WHITE": "#ffffff", "RED": "#ff0000", "PINK": "#ffafaf", "ORANGE": "#ffc800",
          "YELLOW": "#ffff00", "GREEN": "#00ff00", "CYAN": "#00ffff", "BLUE": "#0000ff", "MAGENTA": "#ff00ff",
          "LIGHT_GRAY": "#cccccc", "GRAY": "#888888", "DARK_GRAY": "#444444"}

def _sugar_match(b):
    """積木 -> 好讀語法名稱（完全吻合才回傳）"""
    t = b.get("type")
    if set(b.attrib) - {"type", "id", "x", "y", "inline"}:
        return None
    m = _one(b, "mutation", None)
    fields = {c.get("name"): (c.text or "") for c in b if _tag(c) == "field"}
    vals = {c.get("name") for c in b if _tag(c) == "value"}
    others = [c for c in b if _tag(c) not in ("mutation", "field", "value", "next", "comment")]
    if others:
        return None
    for name, (bt, cf, pf, ins, mut, stmt) in SUGAR.items():
        if bt != t:
            continue
        if any(fields.get(k) != v for k, v in cf.items()):
            continue
        if set(fields) != set(cf) | set(pf):
            continue
        if not vals <= set(ins):
            continue
        if mut is None and m is not None:
            continue
        if mut is not None and (m is None or dict(m.attrib) != mut or len(m)):
            continue
        return name
    return None

TEXT_CMP = {"EQUAL": "text_equal", "NEQ": "text_not_equal", "LT": "text_less", "GT": "text_greater"}


# ---------------------------------------------------------------- 共用
def _lit(s):
    """scm 屬性字串 -> Python 字面值字串"""
    if re.fullmatch(r"-?\d+", s):
        return s
    if s in ("True", "False"):
        return s
    return json.dumps(s, ensure_ascii=False)

def _tag(e):
    return e.tag.split("}")[-1]

def _kids(e, tag, name=None):
    return [c for c in e if _tag(c) == tag and (name is None or c.get("name") == name)]

def _one(e, tag, name):
    r = _kids(e, tag, name)
    return r[0] if r else None

# ---------------------------------------------------------------- 反編譯
class Decompiler:
    def __init__(self, catalog=None):
        self.cat = catalog if catalog is not None else CATALOG
        self.lines = []
        self.evparams = set()
        self.globals = set()
        self.pending = []
        self.counter = 0

    # ---- 通用寫法：B.積木類型(f_欄位="…", 輸入=運算式, _m={突變屬性}, _mc=[子節點], _a={積木屬性})
    def generic_args(self, b):
        parts, stmts = [], []
        attrs = {k: v for k, v in b.attrib.items() if k not in ("type", "id", "x", "y", "inline")}
        for c in b:
            tg = _tag(c)
            if tg == "mutation":
                if c.attrib:
                    parts.append("_m=" + repr(dict(c.attrib)))
                kids = [(_tag(k), dict(k.attrib)) for k in c]
                if kids:
                    parts.append("_mc=" + repr(kids))
            elif tg == "field":
                parts.append(f"f_{c.get('name')}={json.dumps(c.text or '', ensure_ascii=False)}")
            elif tg == "value":
                parts.append(f"{c.get('name')}={self.expr(_one(c, 'block', None))}")
            elif tg == "statement":
                stmts.append(c.get("name"))
        if attrs:
            parts.append("_a=" + repr(attrs))
        return parts, stmts

    def generic_expr(self, b):
        parts, stmts = self.generic_args(b)
        if stmts:   # 運算式裡含敘述（如 do-then-return）：敘述放進前面的 def __sN():
            refs = []
            for sn in stmts:
                self.counter += 1
                nm = f"__s{self.counter}"
                self.pending.append((nm, b, sn))
                refs.append(f"{sn}={nm}")
            parts.append(f"_st=dict({', '.join(refs)})")
        return f"B.{b.get('type')}({', '.join(parts)})"

    def flush(self, mark, ind):
        if not self.pending:
            return
        tail = self.lines[mark:]
        del self.lines[mark:]
        while self.pending:
            todo, self.pending = self.pending, []
            for nm, b, sn in todo:
                self.lines.append("    " * ind + f"def {nm}():")
                self.body(b, sn, ind + 1)
        self.lines.extend(tail)

    def generic_stmt(self, b, ind):
        p = "    " * ind
        parts, stmts = self.generic_args(b)
        head = f"B.{b.get('type')}({', '.join(parts)})"
        if not stmts:
            self.lines.append(p + head); return
        if len(stmts) == 1:
            self.lines.append(f"{p}with {head[:-1]}{', ' if parts else ''}_s={stmts[0]!r}):")
            self.body(b, stmts[0], ind + 1); return
        self.lines.append(f"{p}with {head}:")
        for sn in stmts:
            self.lines.append(f"{p}    with S.{sn}:")
            self.body(b, sn, ind + 2)

    def expr(self, b):
        if b is None:
            return "___"
        if b.get("disabled") or b.get("collapsed"):
            return self.generic_expr(b)
        try:
            return self._expr(b)
        except (NotImplementedError, KeyError, AttributeError, TypeError):
            return self.generic_expr(b)

    def _sugar_call(self, b, name):
        bt, cf, pf, ins, mut, stmt = SUGAR[name]
        args = [json.dumps(_one(b, "field", k).text or "", ensure_ascii=False) for k in pf]
        for k in ins:
            val = _one(b, "value", k)
            args.append(self.expr(_one(val, "block", None) if val is not None else None))
        while args and args[-1] == "___":   # 尾端空插槽省略不了（位置參數），保留
            break
        return f"{name}({', '.join(args)})"

    def _expr(self, b):
        t = b.get("type")
        sg = _sugar_match(b)
        if sg and not SUGAR[sg][5]:
            return self._sugar_call(b, sg)
        if t.startswith("color_") and t[6:].upper() in COLORS and _one(b, "mutation", None) is None:
            fl = _one(b, "field", "COLOR")
            if fl is not None and (fl.text or "").lower() == COLORS[t[6:].upper()] and len(b) == 1 \
                    and not (set(b.attrib) - {"type", "id", "x", "y", "inline"}):
                return f"Color.{t[6:].upper()}"
        if t == "logic_false" and len(b) == 1 and _one(b, "field", "BOOL") is not None \
                and _one(b, "field", "BOOL").text == "FALSE":
            return "False"
        f = lambda n: _one(b, "field", n).text or ""
        v = lambda n: self.expr(_one(_one(b, "value", n), "block", None) if _one(b, "value", n) is not None else None)
        m = _one(b, "mutation", None)
        items = int(m.get("items")) if m is not None and m.get("items") else 0
        if t == "text":
            return json.dumps(f("TEXT"), ensure_ascii=False)
        if t == "math_number":
            num = f("NUM")
            try:
                ok = str(ast.literal_eval(num)) == num
            except Exception:
                ok = False
            if not ok:
                raise NotImplementedError("number literal")
            return num
        if t == "lexical_variable_get":
            if m is not None and len(m) and f("VAR") not in self.evparams:
                raise NotImplementedError("eventparam outside event")
            if m is not None and not len(m):
                raise NotImplementedError("odd mutation")
            raw = f("VAR")
            if raw.startswith("global ") and raw[7:] in self.evparams:
                raise NotImplementedError("global shadowed by event param")
            if not raw.startswith("global ") and raw in self.globals:
                raise NotImplementedError("local shadows global")
            return raw.replace("global ", "")
        if t == "procedures_callreturn":
            n = len(m) if m is not None else 0
            return f"{f('PROCNAME')}({', '.join(v(f'ARG{i}') for i in range(n))})"
        if t == "component_set_get":
            if m.get("is_generic") == "true":
                return f"Any.{m.get('component_type')}({v('COMPONENT')}).{m.get('property_name')}"
            return f"{m.get('instance_name')}.{m.get('property_name')}"
        if t == "component_component_block":
            return m.get("instance_name")
        if t == "component_method":
            if m.get("is_generic") == "true":
                raise NotImplementedError("generic method")
            idx = [int(c.get("name")[3:]) for c in b if _tag(c) == "value" and re.fullmatch(r"ARG\d+", c.get("name", ""))]
            n = max(idx) + 1 if idx else 0
            return f"{m.get('instance_name')}.{m.get('method_name')}({', '.join(v(f'ARG{i}') for i in range(n))})"
        if t == "lists_select_item":
            return f"{v('LIST')}[{v('NUM')}]"
        if t == "text_compare":
            return f"{TEXT_CMP[f('OP')]}({v('TEXT1')}, {v('TEXT2')})"
        if t == "math_random_int":
            return f"random_int({v('FROM')}, {v('TO')})"
        if t == "lists_length":
            return f"len({v('LIST')})"
        if t == "logic_negate":
            return f"(not {v('BOOL')})"
        if t == "lists_is_in":
            return f"({v('ITEM')} in {v('LIST')})"
        if t == "logic_boolean":
            if f("BOOL") != "TRUE":
                raise NotImplementedError("logic_boolean FALSE")
            return "True"
        if t == "lists_from_csv_table":
            return f"csv_table({v('TEXT')})"
        if t in ("math_add", "math_multiply"):
            parts = [v(f"NUM{i}") for i in range(items)]
            if items == 2:
                return f"({parts[0]} {'+' if t == 'math_add' else '*'} {parts[1]})"
            return f"{'add' if t == 'math_add' else 'multiply'}({', '.join(parts)})"
        if t == "math_subtract":
            return f"({v('A')} - {v('B')})"
        if t == "math_division":
            return f"({v('A')} / {v('B')})"
        if t == "math_divide":
            op = f("OP")
            a, c = v("DIVIDEND"), v("DIVISOR")
            return f"({a} % {c})" if op == "MODULO" else f"{op.lower()}({a}, {c})"
        if t == "math_compare":
            return f"({v('A')} {CMP_SYM[f('OP')]} {v('B')})"
        if t == "logic_operation":
            if m is None or m.get("items") != "2":
                raise NotImplementedError("logic_operation items")
            return f"({v('A')} {f('OP').lower()} {v('B')})"
        if t == "text_join":
            return f"join({', '.join(v(f'ADD{i}') for i in range(items))})"
        if t == "lists_create_with":
            return f"[{', '.join(v(f'ADD{i}') for i in range(items))}]"
        raise NotImplementedError(t)

    def stmts(self, b, ind):
        while b is not None:
            self.stmt(b, ind)
            nx = _one(b, "next", None)
            b = _one(nx, "block", None) if nx is not None else None

    def body(self, b, name, ind):
        s = _one(b, "statement", name)
        if s is None or _one(s, "block", None) is None:
            self.lines.append("    " * ind + "pass")
        else:
            self.stmts(_one(s, "block", None), ind)

    def stmt(self, b, ind):
        if b.get("disabled") or b.get("collapsed"):
            return self.generic_stmt(b, ind)
        mark = len(self.lines)
        saved = list(self.pending)
        try:
            self._stmt(b, ind)
        except (NotImplementedError, KeyError, AttributeError, TypeError):
            del self.lines[mark:]
            self.pending = saved
            self.generic_stmt(b, ind)
        self.flush(mark, ind)

    def _stmt(self, b, ind):
        t = b.get("type"); p = "    " * ind
        sg = _sugar_match(b)
        if sg and SUGAR[sg][5]:
            self.lines.append(p + self._sugar_call(b, sg)); return
        f = lambda n: _one(b, "field", n).text or ""
        v = lambda n: self.expr(_one(_one(b, "value", n), "block", None) if _one(b, "value", n) is not None else None)
        m = _one(b, "mutation", None)
        if t == "component_set_get":
            if m.get("is_generic") == "true":
                self.lines.append(f"{p}Any.{m.get('component_type')}({v('COMPONENT')}).{m.get('property_name')} = {v('VALUE')}")
            else:
                self.lines.append(f"{p}{m.get('instance_name')}.{m.get('property_name')} = {v('VALUE')}")
        elif t == "lexical_variable_set":
            self.lines.append(f"{p}{f('VAR').replace('global ', '')} = {v('VALUE')}")
        elif t == "controls_if":
            if m is not None and set(m.attrib) - {"elseif", "else"}:
                raise NotImplementedError("if mutation")
            n_elif = int(m.get("elseif", 0)) if m is not None else 0
            has_else = m is not None and m.get("else") == "1"
            for i in range(n_elif + 1):
                self.lines.append(f"{p}{'if' if i == 0 else 'elif'} {v(f'IF{i}')}:")
                self.body(b, f"DO{i}", ind + 1)
            if has_else:
                self.lines.append(f"{p}else:")
                self.body(b, "ELSE", ind + 1)
        elif t == "controls_forRange":
            self.lines.append(f"{p}for {f('VAR')} in irange({v('START')}, {v('END')}, {v('STEP')}):")
            self.body(b, "DO", ind + 1)
        elif t == "controls_forEach":
            self.lines.append(f"{p}for {f('VAR')} in {v('LIST')}:")
            self.body(b, "DO", ind + 1)
        elif t == "procedures_callnoreturn":
            n = len(m) if m is not None else 0
            self.lines.append(f"{p}{f('PROCNAME')}({', '.join(v(f'ARG{i}') for i in range(n))})")
        elif t == "controls_while":
            self.lines.append(f"{p}while {v('TEST')}:")
            self.body(b, "DO", ind + 1)
        elif t == "lists_add_items":
            n = int(m.get("items"))
            self.lines.append(f"{p}add_items({', '.join([v('LIST')] + [v(f'ITEM{i}') for i in range(n)])})")
        else:
            self.lines.append(p + self.expr(b))   # 方法呼叫或單獨的運算式

    def run(self, scm, bky):
        j = json.loads(scm.split("$JSON", 1)[1].rsplit("|#", 1)[0])
        L = self.lines
        L.append("# ---- 畫面元件 ----")
        def walk(c, parent):
            props = [f"{k}={_lit(c[k])}" for k in c if not k.startswith("$") and k != "Uuid"]
            args = ([parent] if parent else []) + props
            L.append(f"{c['$Name']} = {c['$Type']}({', '.join(args)})")
            for k in c.get("$Components", []):
                walk(k, c["$Name"])
        walk(j["Properties"], None)
        root = ET.fromstring(bky) if bky.strip() else ET.Element("xml")
        tops = _kids(root, "block")
        self.globals = {_one(b, "field", "NAME").text for b in tops if b.get("type") == "global_declaration"}
        L.append("")
        L.append("# ---- 全域變數 ----")
        for b in tops:
            if b.get("type") == "global_declaration":
                val = _one(b, "value", "VALUE")
                mark = len(L)
                L.append(f"{_one(b, 'field', 'NAME').text} = {self.expr(_one(val, 'block', None) if val is not None else None)}")
                self.flush(mark, 0)
        for b in tops:
            t = b.get("type")
            if t == "global_declaration":
                continue
            if t in ("procedures_defnoreturn", "procedures_defreturn"):
                m = _one(b, "mutation", None)
                args = [a.get("name") for a in m] if m is not None else []
                L.append("")
                extra = {k: v for k, v in b.attrib.items() if k not in ("type", "id", "x", "y", "inline")}
                if extra:
                    L.append("@attrs(" + ", ".join(f"{k}={v!r}" for k, v in extra.items()) + ")")
                L.append(f"def {_one(b, 'field', 'NAME').text}({', '.join(args)}):")
                if t == "procedures_defnoreturn":
                    self.body(b, "STACK", 1)
                else:
                    mark = len(L)
                    L.append(f"    return {self.expr(_one(_one(b, 'value', 'RETURN'), 'block', None) if _one(b, 'value', 'RETURN') is not None else None)}")
                    self.flush(mark, 1)
                continue
            if t != "component_event" or _one(b, "mutation", None).get("is_generic") == "true":
                L.append("")
                L.append("@floating   # 散落在工作區、沒接到事件的積木")
                L.append("def _():")
                self.stmts(b, 1)
                continue
            m = _one(b, "mutation", None)
            L.append("")
            extra = {k: v for k, v in b.attrib.items() if k not in ("type", "id", "x", "y", "inline")}
            dis = "".join(f", {k}={v!r}" for k, v in extra.items())
            L.append(f"@when({m.get('instance_name')}.{m.get('event_name')}{dis})")
            ct, en = m.get("component_type"), m.get("event_name")
            params = self.cat.get(ct, {}).get("events", {}).get(en) or EVENT_PARAMS.get((ct, en))
            if params is None:
                params = []
                for ep in (x for x in b.iter() if _tag(x) == "eventparam"):
                    if ep.get("name") not in params: params.append(ep.get("name"))
            L.append(f"def _({', '.join(params)}):")
            self.evparams = set(params)
            self.body(b, "DO", 1)
            self.evparams = set()
        return "\n".join(L) + "\n"

def list_assets(aia_path):
    z = zipfile.ZipFile(aia_path)
    return {n[len("assets/"):]: z.read(n) for n in z.namelist() if n.startswith("assets/") and not n.endswith("/")}

SCREEN_MARK = "#### SCREEN "

def screens_of(aia_path):
    """回傳 [(畫面名, scm, bky)]，Screen1 排第一"""
    z = zipfile.ZipFile(aia_path)
    out = []
    for n in z.namelist():
        if n.startswith("src/") and n.endswith(".scm"):
            name = n.rsplit("/", 1)[1][:-4]
            bn = n[:-4] + ".bky"
            bky = z.read(bn).decode() if bn in z.namelist() else ""
            out.append((name, z.read(n).decode(), bky))
    out.sort(key=lambda t: (t[0] != "Screen1", t[0]))
    return out

def decompile(aia_path):
    exts = load_extensions(aia_path)
    cat = {**CATALOG, **_ext_catalog(exts)}
    head = ""
    if exts:   # 註解，僅供閱讀；編譯時不讀
        head = "".join(f"# 擴充元件：{e.package}（{'、'.join(e.names)}）\n" for e in exts)
    scr = screens_of(aia_path)
    if len(scr) == 1:
        return head + Decompiler(cat).run(scr[0][1], scr[0][2])
    return head + "\n".join(f"{SCREEN_MARK}{n}\n" + Decompiler(cat).run(scm, bky) for n, scm, bky in scr)

def split_screens(text):
    """多畫面文字 -> [(畫面名, 文字)]"""
    if SCREEN_MARK not in text:
        return [("Screen1", text)]
    parts = re.split(r"^" + re.escape(SCREEN_MARK) + r"(\w+)\s*$", text, flags=re.M)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]

def compile_project(text, app_name="GeneratedApp", strict=True, extensions=None):
    """回傳 {畫面名: (scm, bky)}。extensions：[Extension]（load_extensions 的結果），嚴格模式會一併驗證"""
    return {n: Compiler(app_name, strict, extensions).run(t, n) for n, t in split_screens(text)}

# ---------------------------------------------------------------- 編譯
_ID_CHARS = string.ascii_letters + string.digits + "!#$%()*+,-./:;=?@[]^_`{|}~"
def _bid():
    return "".join(random.choice(_ID_CHARS) for _ in range(20))

class CompileError(Exception):
    pass

class Compiler:
    def __init__(self, app_name, strict=True, extensions=None):
        self.cat = {**CATALOG, **_ext_catalog(extensions)}
        self.app = app_name
        self.strict = strict
        self.procs = {}          # 程序名 -> (參數, 有回傳值)
        self.stmt_bodies = {}    # __sN -> 敘述
        self.comps = {}          # name -> type
        self.globals = set()
        self.local = []          # 迴圈變數堆疊
        self.eventparams = set()

    # ---- XML 小工具
    def B(self, typ, parent=None, name=None, kind="value"):
        b = ET.Element("block", {"type": typ, "id": _bid()})
        if parent is not None:
            holder = ET.SubElement(parent, kind, {"name": name})
            holder.append(b)
        return b

    def F(self, b, name, text):
        ET.SubElement(b, "field", {"name": name}).text = str(text)

    def M(self, b, **kw):
        ET.SubElement(b, "mutation", {k: str(v) for k, v in kw.items()})

    def V(self, b, name, node):
        if isinstance(node, ast.Name) and node.id == "___":
            return   # 空插槽
        h = ET.SubElement(b, "value", {"name": name})
        h.append(self.expr(node))

    def var(self, name):
        if name in self.local:
            return name
        if name in self.globals:
            return "global " + name
        if not self.strict:
            return name
        raise CompileError(f"未宣告的變數：{name}")

    # ---- 用元件目錄檢查（僅嚴格模式）
    def check_prop(self, ctype, prop, set_or_get):
        if not self.strict or ctype not in self.cat:
            return
        bp = self.cat[ctype]["bp"]
        if prop not in bp:
            raise CompileError(f"{ctype} 沒有屬性 {prop}{_hint(prop, bp)}")
        rw = bp[prop]
        if set_or_get == "set" and rw == "read-only":
            raise CompileError(f"{ctype}.{prop} 是唯讀屬性，不能設定")
        if set_or_get == "get" and rw == "write-only":
            raise CompileError(f"{ctype}.{prop} 只能設定，不能讀取")

    def check_member(self, ctype, kind, name, nargs=None):
        if not self.strict or ctype not in self.cat:
            return
        pool = self.cat[ctype][kind]
        label = "事件" if kind == "events" else "方法"
        if name not in pool:
            raise CompileError(f"{ctype} 沒有{label} {name}{_hint(name, pool)}")
        if nargs is not None and nargs != len(pool[name]):
            raise CompileError(f"{ctype}.{name} 需要 {len(pool[name])} 個參數（{', '.join(pool[name])}），你給了 {nargs} 個")

    def comp_prop(self, node, set_or_get):
        if not (isinstance(node.value, ast.Name) and node.value.id in self.comps):
            raise CompileError(f"找不到元件：{ast.unparse(node.value)}")
        inst = node.value.id
        self.check_prop(self.comps[inst], node.attr, set_or_get)
        b = self.B("component_set_get")
        self.M(b, component_type=self.comps[inst], set_or_get=set_or_get,
               property_name=node.attr, is_generic="false", instance_name=inst)
        self.F(b, "COMPONENT_SELECTOR", inst)
        self.F(b, "PROP", node.attr)
        return b

    # ---- 通用積木 B.xxx(...)
    def _is_B(self, n):
        return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "B"

    def generic(self, call):
        b = self.B(call.func.attr)
        kw = {k.arg: k.value for k in call.keywords}
        if "_a" in kw:
            for k, v in ast.literal_eval(kw["_a"]).items(): b.set(k, v)
        if "_m" in kw or "_mc" in kw:
            m = ET.SubElement(b, "mutation", ast.literal_eval(kw["_m"]) if "_m" in kw else {})
            for tg, at in (ast.literal_eval(kw["_mc"]) if "_mc" in kw else []):
                ET.SubElement(m, tg, at)
        declared = []
        for k, v in kw.items():
            if k.startswith("f_"):
                val = ast.literal_eval(v)
                self.F(b, k[2:], val)
                if re.fullmatch(r"VAR\d*", k[2:]) and call.func.attr.startswith(("local_declaration", "controls_for")):
                    declared.append(val)
        self.local.extend(declared)
        for k, v in kw.items():
            if k.startswith("_") or k.startswith("f_"):
                continue
            self.V(b, k, v)
        if "_st" in kw:
            for k in kw["_st"].keywords:
                self.S(b, k.arg, self.stmt_bodies[k.value.id])
        return b, declared

    def _reg(self, body):
        for x in body:
            if isinstance(x, ast.FunctionDef) and x.name.startswith("__s"):
                self.stmt_bodies[x.name] = x.body

    def sugar(self, n, as_stmt):
        name = n.func.id
        bt, cf, pf, ins, mut, stmt = SUGAR[name]
        if stmt != as_stmt:
            raise CompileError(f"{name}() 是{'敘述，要單獨一行' if stmt else '運算式，不能單獨一行'}")
        if len(n.args) != len(pf) + len(ins):
            raise CompileError(f"{name}() 需要 {len(pf) + len(ins)} 個參數，你給了 {len(n.args)} 個")
        b = self.B(bt)
        if mut is not None:
            ET.SubElement(b, "mutation", dict(mut))
        for k, v in cf.items():
            self.F(b, k, v)
        args = list(n.args)
        for k in pf:
            self.F(b, k, ast.literal_eval(args.pop(0)))
        for k in ins:
            self.V(b, k, args.pop(0))
        return b

    def proc_call(self, n, as_stmt):
        name = n.func.id
        params, _ = self.procs[name]
        b = self.B("procedures_callnoreturn" if as_stmt else "procedures_callreturn")
        m = ET.SubElement(b, "mutation", {"name": name})
        for a in params: ET.SubElement(m, "arg", {"name": a})
        self.F(b, "PROCNAME", name)
        for i, e in enumerate(n.args): self.V(b, f"ARG{i}", e)
        return b

    # ---- 運算式
    def expr(self, n):
        if self._is_B(n):
            b, declared = self.generic(n)
            for _ in declared: self.local.pop()
            return b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in self.procs:
            return self.proc_call(n, False)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, str):
                b = self.B("text"); self.F(b, "TEXT", n.value); return b
            if isinstance(n.value, bool):
                if n.value:
                    b = self.B("logic_boolean"); self.F(b, "BOOL", "TRUE")
                else:
                    b = self.B("logic_false"); self.F(b, "BOOL", "FALSE")
                return b
            b = self.B("math_number"); self.F(b, "NUM", n.value); return b
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant):
            b = self.B("math_number"); self.F(b, "NUM", -n.operand.value); return b
        if isinstance(n, ast.Name):
            if n.id in self.eventparams and n.id not in self.local:
                b = self.B("lexical_variable_get")
                ET.SubElement(ET.SubElement(b, "mutation"), "eventparam", {"name": n.id})
                self.F(b, "VAR", n.id); return b
            if n.id in self.comps and n.id not in self.globals and n.id not in self.local:
                b = self.B("component_component_block")
                self.M(b, component_type=self.comps[n.id], instance_name=n.id)
                self.F(b, "COMPONENT_SELECTOR", n.id); return b
            b = self.B("lexical_variable_get"); self.F(b, "VAR", self.var(n.id)); return b
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "Color" \
                and "Color" not in self.comps:
            if n.attr not in COLORS:
                raise CompileError(f"沒有顏色 Color.{n.attr}{_hint(n.attr, COLORS)}")
            b = self.B("color_" + n.attr.lower()); self.F(b, "COLOR", COLORS[n.attr]); return b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in SUGAR \
                and n.func.id not in self.procs:
            return self.sugar(n, as_stmt=False)
        if isinstance(n, ast.Attribute):
            if self._is_any(n.value):
                return self.generic_prop(n, "get")
            return self.comp_prop(n, "get")
        if isinstance(n, ast.Subscript):
            b = self.B("lists_select_item"); self.V(b, "LIST", n.value); self.V(b, "NUM", n.slice); return b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and isinstance(n.func.value, ast.Name) and n.func.value.id in self.comps:
            inst = n.func.value.id
            self.check_member(self.comps[inst], "methods", n.func.attr, len(n.args))
            b = self.B("component_method")
            self.M(b, component_type=self.comps[inst], method_name=n.func.attr,
                   is_generic="false", instance_name=inst)
            self.F(b, "COMPONENT_SELECTOR", inst)
            for i, e in enumerate(n.args): self.V(b, f"ARG{i}", e)
            return b
        if isinstance(n, ast.BinOp):
            op = type(n.op)
            if op in (ast.Add, ast.Mult):
                b = self.B("math_add" if op is ast.Add else "math_multiply")
                self.M(b, items=2); self.V(b, "NUM0", n.left); self.V(b, "NUM1", n.right); return b
            if op in (ast.Sub, ast.Div):
                b = self.B("math_subtract" if op is ast.Sub else "math_division")
                self.V(b, "A", n.left); self.V(b, "B", n.right); return b
            if op is ast.Mod:
                return self._divide("MODULO", n.left, n.right)
            if op is ast.Pow:
                b = self.B("math_power"); self.V(b, "A", n.left); self.V(b, "B", n.right); return b
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            b = self.B("logic_negate"); self.V(b, "BOOL", n.operand); return b
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.In):
            b = self.B("lists_is_in"); self.V(b, "ITEM", n.left); self.V(b, "LIST", n.comparators[0]); return b
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                raise CompileError("請不要連續比較（a < b < c），改用 and")
            op = next(k for k, c in CMP.items() if isinstance(n.ops[0], c))
            b = self.B("math_compare"); self.F(b, "OP", op)
            self.V(b, "A", n.left); self.V(b, "B", n.comparators[0]); return b
        if isinstance(n, ast.BoolOp):
            op = "AND" if isinstance(n.op, ast.And) else "OR"
            # 2 項以上就巢狀
            node = n.values[0]
            for nxt in n.values[1:]:
                b = self.B("logic_operation"); self.M(b, items=2); self.F(b, "OP", op)
                self._vb(b, "A", node); self.V(b, "B", nxt); node = b
            return node
        if isinstance(n, ast.List):
            b = self.B("lists_create_with"); self.M(b, items=len(n.elts))
            for i, e in enumerate(n.elts): self.V(b, f"ADD{i}", e)
            return b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            fn, a = n.func.id, n.args
            if fn in ("add", "multiply"):
                b = self.B("math_add" if fn == "add" else "math_multiply"); self.M(b, items=len(a))
                for i, e in enumerate(a): self.V(b, f"NUM{i}", e)
                return b
            if fn == "join":
                b = self.B("text_join"); self.M(b, items=len(a))
                for i, e in enumerate(a): self.V(b, f"ADD{i}", e)
                return b
            inv = {v: k for k, v in TEXT_CMP.items()}
            if fn in inv:
                b = self.B("text_compare"); self.F(b, "OP", inv[fn])
                self.V(b, "TEXT1", a[0]); self.V(b, "TEXT2", a[1]); return b
            if fn == "random_int":
                b = self.B("math_random_int"); self.V(b, "FROM", a[0]); self.V(b, "TO", a[1]); return b
            if fn == "len":
                b = self.B("lists_length"); self.V(b, "LIST", a[0]); return b
            if fn == "csv_table":
                b = self.B("lists_from_csv_table"); self.V(b, "TEXT", a[0]); return b
            if fn in ("remainder", "quotient"):
                return self._divide(fn.upper(), a[0], a[1])
        raise CompileError(f"不支援的運算式：{ast.unparse(n)}")

    @staticmethod
    def _is_any(v):
        return isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) \
            and isinstance(v.func.value, ast.Name) and v.func.value.id == "Any"

    def generic_prop(self, node, set_or_get, value=None):
        call = node.value
        self.check_prop(call.func.attr, node.attr, set_or_get)
        b = self.B("component_set_get")
        self.M(b, component_type=call.func.attr, set_or_get=set_or_get,
               property_name=node.attr, is_generic="true")
        self.F(b, "PROP", node.attr)
        self.V(b, "COMPONENT", call.args[0])
        if value is not None: self.V(b, "VALUE", value)
        return b

    def _vb(self, b, name, node):
        h = ET.SubElement(b, "value", {"name": name})
        h.append(node if isinstance(node, ET.Element) else self.expr(node))

    def _divide(self, op, a, c):
        b = self.B("math_divide"); self.F(b, "OP", op)
        self.V(b, "DIVIDEND", a); self.V(b, "DIVISOR", c); return b

    # ---- 敘述
    def stmt(self, n):
        if isinstance(n, ast.Assign):
            tgt = n.targets[0]
            if isinstance(tgt, ast.Attribute) and self._is_any(tgt.value):
                return self.generic_prop(tgt, "set", n.value)
            if isinstance(tgt, ast.Attribute):
                b = self.comp_prop(tgt, "set"); self.V(b, "VALUE", n.value); return b
            if isinstance(tgt, ast.Name):
                b = self.B("lexical_variable_set"); self.F(b, "VAR", self.var(tgt.id))
                self.V(b, "VALUE", n.value); return b
        if isinstance(n, ast.If):
            branches, node = [], n
            while True:
                branches.append((node.test, node.body))
                if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                    node = node.orelse[0]; continue
                break
            els = node.orelse
            b = self.B("controls_if")
            attrs = {}
            if len(branches) > 1: attrs["elseif"] = len(branches) - 1
            if els: attrs["else"] = 1
            if attrs: self.M(b, **attrs)
            for i, (t, body) in enumerate(branches):
                self.V(b, f"IF{i}", t)
            for i, (t, body) in enumerate(branches):
                self.S(b, f"DO{i}", body)
            if els: self.S(b, "ELSE", els)
            return b
        if isinstance(n, ast.With):
            call = n.items[0].context_expr
            kw = {k.arg: k.value for k in call.keywords}
            sname = ast.literal_eval(kw.pop("_s")) if "_s" in kw else None
            call.keywords = [k for k in call.keywords if k.arg != "_s"]
            b, declared = self.generic(call)
            if sname:
                self.S(b, sname, n.body)
            else:
                for sub in n.body:
                    self.S(b, sub.items[0].context_expr.attr, sub.body)
            for _ in declared: self.local.pop()
            return b
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) \
                and n.value.func.id in self.procs:
            return self.proc_call(n.value, True)
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) \
                and n.value.func.id in SUGAR:
            return self.sugar(n.value, as_stmt=True)
        if isinstance(n, ast.For) and not (isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name)
                                           and n.iter.func.id == "irange"):
            b = self.B("controls_forEach"); self.F(b, "VAR", n.target.id)
            self.V(b, "LIST", n.iter)
            self.local.append(n.target.id); self.S(b, "DO", n.body); self.local.pop()
            return b
        if isinstance(n, ast.For):
            c = n.iter
            if not (isinstance(c, ast.Call) and c.func.id == "irange" and len(c.args) == 3):
                raise CompileError("for 迴圈請用 irange(起, 終, 間隔)")
            b = self.B("controls_forRange"); self.F(b, "VAR", n.target.id)
            for nm, e in zip(("START", "END", "STEP"), c.args): self.V(b, nm, e)
            self.local.append(n.target.id); self.S(b, "DO", n.body); self.local.pop()
            return b
        if isinstance(n, ast.While):
            b = self.B("controls_while"); self.V(b, "TEST", n.test); self.S(b, "DO", n.body); return b
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) \
                and isinstance(n.value.func, ast.Name) and n.value.func.id == "add_items":
            a = n.value.args
            b = self.B("lists_add_items"); self.M(b, items=len(a) - 1); self.V(b, "LIST", a[0])
            for i, e in enumerate(a[1:]): self.V(b, f"ITEM{i}", e)
            return b
        if isinstance(n, ast.Pass):
            return None
        if isinstance(n, ast.Expr):
            if self._is_B(n.value):
                b, declared = self.generic(n.value)
                for _ in declared: self.local.pop()
                return b
            return self.expr(n.value)   # 方法呼叫或散落的運算式
        raise CompileError(f"不支援的敘述：{ast.unparse(n)}")

    def S(self, parent, name, body):
        self._reg(body)
        body = [x for x in body if not (isinstance(x, ast.FunctionDef) and x.name.startswith("__s"))]
        blocks = [x for x in (self.stmt(s) for s in body) if x is not None]
        if not blocks:
            return
        h = ET.SubElement(parent, "statement", {"name": name})
        h.append(blocks[0])
        for prev, cur in zip(blocks, blocks[1:]):
            ET.SubElement(prev, "next").append(cur)

    # ---- 主流程
    def run(self, text, screen="Screen1"):
        tree = ast.parse(text)
        form, comp_list, glob_nodes, events, procs_nodes = None, [], [], [], []
        for n in tree.body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) \
                    and isinstance(n.value.func, ast.Name) and n.value.func.id[:1].isupper():
                name, typ = n.targets[0].id, n.value.func.id
                props = {k.arg: ast.literal_eval(k.value) for k in n.value.keywords}
                if self.strict and self.cat:
                    if typ not in self.cat:
                        raise CompileError(f"沒有元件類型 {typ}{_hint(typ, self.cat)}"
                                           "（如果是擴充元件，請先加入對應的 .aix）")
                    for k in props:
                        if k not in self.cat[typ]["props"] and k not in _STRUCT_PROPS:
                            raise CompileError(f"{typ}（{name}）沒有設計屬性 {k}{_hint(k, self.cat[typ]['props'])}")
                parent = n.value.args[0].id if n.value.args else None
                self.comps[name] = typ
                comp_list.append((name, typ, parent, props))
            elif isinstance(n, ast.Assign):
                self.globals.add(n.targets[0].id); glob_nodes.append(n)
            elif isinstance(n, ast.FunctionDef) and n.name.startswith("__s"):
                self.stmt_bodies[n.name] = n.body
            elif isinstance(n, ast.FunctionDef) and (not n.decorator_list or (
                    isinstance(n.decorator_list[0], ast.Call) and n.decorator_list[0].func.id == "attrs")):
                procs_nodes.append(n)
                rest = [x for x in n.body if not (isinstance(x, ast.FunctionDef) and x.name.startswith("__s"))]
                ret = len(rest) == 1 and isinstance(rest[0], ast.Return)
                self.procs[n.name] = ([a.arg for a in n.args.args], ret)
            elif isinstance(n, ast.FunctionDef):
                events.append(n)
            else:
                raise CompileError(f"最外層不支援：{ast.unparse(n)}")
        # scm：沒宣告 Form 時自動補上（AI 常省略 Screen1 = Form()）
        if not any(t == "Form" for _, t, _, _ in comp_list):
            comp_list.insert(0, (screen, "Form", None, {"Title": screen}))
            self.comps.setdefault(screen, "Form")
        nodes = {}
        for name, typ, parent, props in comp_list:
            d = {"$Name": name, "$Type": typ,
                 "$Version": COMP_VERSION.get(typ) or self.cat.get(typ, {}).get("version", "1")}
            for k, val in props.items():
                d[k] = str(val)
            d["Uuid"] = "0" if typ == "Form" else str(random.randint(-2**31, 2**31 - 1))
            nodes[name] = d
            if parent:
                if parent not in nodes:
                    raise CompileError(f"{name} 的父元件 {parent} 還沒宣告（父元件要寫在前面）")
                nodes[parent].setdefault("$Components", []).append(d)
            else:
                form = d
        form.setdefault("AppName", self.app)
        scm = "#|\n$JSON\n" + json.dumps({"authURL": ["ai2.appinventor.mit.edu"], "YaVersion": YA_VERSION,
                                          "Source": "Form", "Properties": form},
                                         ensure_ascii=True, separators=(",", ":")) + "\n|#"
        # bky
        root = ET.Element("xml", {"xmlns": "https://developers.google.com/blockly/xml"})
        y = 0
        for g in glob_nodes:
            b = self.B("global_declaration"); b.set("x", "0"); b.set("y", str(y)); y += 40
            self.F(b, "NAME", g.targets[0].id); self.V(b, "VALUE", g.value); root.append(b)
        for pn in procs_nodes:
            params, ret = self.procs[pn.name]
            b = self.B("procedures_defreturn" if ret else "procedures_defnoreturn")
            b.set("x", "0"); b.set("y", str(y)); y += 160
            for d in pn.decorator_list:
                for k in d.keywords: b.set(k.arg, str(ast.literal_eval(k.value)))
            if params:
                m = ET.SubElement(b, "mutation")
                for a in params: ET.SubElement(m, "arg", {"name": a})
            self.F(b, "NAME", pn.name)
            for i, a in enumerate(params): self.F(b, f"VAR{i}", a)
            self.local.extend(params)
            if ret:
                self._reg(pn.body)
                self.V(b, "RETURN", pn.body[-1].value)
            else:
                self.S(b, "STACK", pn.body)
            del self.local[len(self.local) - len(params):]
            root.append(b)
        for ev in events:
            dec = ev.decorator_list[0]
            dis = isinstance(dec, ast.Call) and any(k.arg == "disabled" and k.value.value for k in dec.keywords)
            if (isinstance(dec, ast.Name) and dec.id == "floating") or \
                    (isinstance(dec, ast.Call) and dec.func.id == "floating"):
                tmp = ET.Element("tmp"); self.S(tmp, "DO", ev.body)
                st = _one(tmp, "statement", "DO")
                if st is not None:
                    b = st[0]; b.set("x", "600"); b.set("y", str(y)); y += 120
                    if dis: b.set("disabled", "true")
                    root.append(b)
                continue
            if not (isinstance(dec, ast.Call) and dec.func.id == "when"):
                raise CompileError("事件請寫成 @when(元件.事件)")
            target = dec.args[0]
            inst, evname = target.value.id, target.attr
            if inst not in self.comps:
                raise CompileError(f"事件用到不存在的元件：{inst}{_hint(inst, self.comps)}")
            self.check_member(self.comps[inst], "events", evname,
                              len(ev.args.args) if ev.args.args else None)
            b = self.B("component_event"); b.set("x", "0"); b.set("y", str(y)); y += 200
            for k in (dec.keywords if isinstance(dec, ast.Call) else []):
                if k.arg != "disabled": b.set(k.arg, str(ast.literal_eval(k.value)))
            if dis: b.set("disabled", "true")
            self.M(b, component_type=self.comps[inst], is_generic="false",
                   instance_name=inst, event_name=evname)
            self.F(b, "COMPONENT_SELECTOR", inst)
            self.eventparams = {a.arg for a in ev.args.args}
            self.S(b, "DO", ev.body); root.append(b)
            self.eventparams = set()
        # 重新排版：由上往下依積木數量估算高度，避免疊在一起
        cur = 20
        for b in [c for c in root if c.tag == "block"]:
            b.set("x", "20"); b.set("y", str(cur))
            n = sum(1 for _ in b.iter("block"))
            cur += 60 + 24 * n
        ET.SubElement(root, "yacodeblocks", {"ya-version": YA_VERSION, "language-version": LANG_VERSION})
        bky = ET.tostring(root, encoding="unicode")
        return scm, bky

def compile_text(text, app_name="GeneratedApp", strict=True, extensions=None):
    """單一畫面"""
    return Compiler(app_name, strict, extensions).run(text)

PROPS_TMPL = """main=appinventor.ai_user.{n}.Screen1
name={n}
assets=../assets
source=../src
build=../build
versioncode=1
versionname=1.0
useslocation=False
aname={n}
sizing=Responsive
showlistsasjson=True
theme=Classic
color.primary=&HFF3F51B5
color.primary.dark=&HFF303F9F
color.accent=&HFFFF4081
defaultfilescope=App
actionbar=False
"""

def used_component_types(text):
    """文字裡宣告的元件類型集合"""
    out = set()
    for _, t in split_screens(text):
        for n in ast.parse(t).body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) \
                    and n.value.func.id[:1].isupper():
                out.add(n.value.func.id)
    return out

def build_aia(text, out_path, app_name="GeneratedApp", assets=None, extensions=None, prune_extensions=True):
    """assets: {檔名: bytes}，例如 {"cola.png": open(...).read()}
    extensions: .aix / .aia 的路徑或 bytes，或 Extension 物件的清單。
    prune_extensions=True 時只打包文字裡真的用到的擴充元件套件。"""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", app_name):
        raise CompileError("專案名稱只能用英文字母開頭、英數字與底線")
    exts = []
    for e in extensions or []:
        exts.extend([e] if isinstance(e, Extension) else load_extensions(e))
    if prune_extensions:
        used = used_component_types(text)
        exts = [e for e in exts if used & set(e.names)]
    proj = compile_project(text, app_name, extensions=exts)
    if "Screen1" not in proj:
        raise CompileError("必須有 Screen1")
    base = f"src/appinventor/ai_user/{app_name}/"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, (scm, bky) in proj.items():
            z.writestr(base + n + ".scm", scm)
            z.writestr(base + n + ".bky", bky)
        z.writestr("youngandroidproject/project.properties", PROPS_TMPL.format(n=app_name))
        for fn, data in (assets or {}).items():
            if fn.startswith("external_comps/"):
                continue   # 擴充元件由 extensions 參數負責
            z.writestr("assets/" + fn, data)
        for e in exts:
            for rel, data in e.files.items():
                z.writestr(f"assets/external_comps/{e.package}/{rel}", data)
    return out_path
