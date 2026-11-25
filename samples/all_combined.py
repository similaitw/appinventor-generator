#### SCREEN Screen1
Screen1 = Form(Title="登入", AlignHorizontal=3)
文字輸入盒_帳號 = TextBox(Screen1, Hint="帳號", Width=-2)
密碼輸入盒1 = PasswordTextBox(Screen1, Hint="密碼", Width=-2)
按鈕_登入 = Button(Screen1, Text="登入", Width=-2)
對話框1 = Notifier(Screen1)

@when(按鈕_登入.Click)
def _():
    if 文字輸入盒_帳號.Text == "student" and 密碼輸入盒1.Text == "1234":
        open_screen_with_value("Welcome", 文字輸入盒_帳號.Text)
    else:
        對話框1.ShowAlert("帳號或密碼錯誤")

#### SCREEN Welcome
Welcome = Form(Title="歡迎", AlignHorizontal=3)
標籤_歡迎 = Label(Welcome, Text="", FontSize=24)
按鈕_登出 = Button(Welcome, Text="登出")

@when(Welcome.Initialize)
def _():
    標籤_歡迎.Text = join("歡迎，", get_start_value())

@when(按鈕_登出.Click)
def _():
    close_screen()

#### SCREEN Rate
Rate = Form(Title="匯率換算", AlignHorizontal=3)
標籤1 = Label(Rate, Text="新台幣金額", FontSize=18)
文字輸入盒_台幣 = TextBox(Rate, NumbersOnly=True, Width=-2)
下拉_幣別 = Spinner(Rate, ElementsFromString="美元,日圓,歐元", Width=-2)
按鈕_換算 = Button(Rate, Text="換算", Width=-2)
標籤_結果 = Label(Rate, Text="", FontSize=24, TextAlignment=1, Width=-2)

匯率表 = [32.5, 0.21, 35.2]

@when(按鈕_換算.Click)
def _():
    if is_number(文字輸入盒_台幣.Text):
        標籤_結果.Text = join(format_decimal(文字輸入盒_台幣.Text / 匯率表[下拉_幣別.SelectionIndex], 2), " ", 下拉_幣別.Selection)
    else:
        標籤_結果.Text = "請輸入數字"

#### SCREEN Dice
Dice = Form(Title="骰子", AlignHorizontal=3, AlignVertical=2)
標籤_點數 = Label(Dice, Text="🎲", FontSize=100, TextAlignment=1, Width=-2)
按鈕_擲 = Button(Dice, Text="擲骰子", FontSize=24, Width=-2)
計時器1 = Clock(Dice, TimerInterval=100, TimerEnabled=False)

轉動次數 = 0

@when(按鈕_擲.Click)
def _():
    轉動次數 = 0
    計時器1.TimerEnabled = True

@when(計時器1.Timer)
def _():
    標籤_點數.Text = random_int(1, 6)
    轉動次數 = 轉動次數 + 1
    if 轉動次數 >= 10:
        計時器1.TimerEnabled = False
        if 標籤_點數.Text == 6:
            標籤_點數.TextColor = Color.RED
        else:
            標籤_點數.TextColor = Color.BLACK

#### SCREEN Todo
Todo = Form(Title="記事本")
文字輸入盒_內容 = TextBox(Todo, Hint="輸入待辦事項", Width=-2)
水平配置1 = HorizontalArrangement(Todo, Width=-2)
按鈕_新增 = Button(水平配置1, Text="新增", Width=-1050)
按鈕_清空 = Button(水平配置1, Text="全部清除", Width=-1050)
清單檢視1 = ListView(Todo, Width=-2, Height=-2)
微型資料庫1 = TinyDB(Todo)
對話框1 = Notifier(Todo)

事項 = []

@when(Todo.Initialize)
def _():
    事項 = 微型資料庫1.GetValue("事項", [])
    清單檢視1.Elements = 事項

@when(按鈕_新增.Click)
def _():
    if not is_empty(trim(文字輸入盒_內容.Text)):
        add_items(事項, 文字輸入盒_內容.Text)
        微型資料庫1.StoreValue("事項", 事項)
        清單檢視1.Elements = 事項
        文字輸入盒_內容.Text = ""

@when(清單檢視1.AfterPicking)
def _():
    remove_item(事項, 清單檢視1.SelectionIndex)
    微型資料庫1.StoreValue("事項", 事項)
    清單檢視1.Elements = 事項
    對話框1.ShowAlert("已刪除")

@when(按鈕_清空.Click)
def _():
    事項 = []
    微型資料庫1.ClearAll()
    清單檢視1.Elements = 事項

#### SCREEN AB
AB = Form(Title="1A2B", AlignHorizontal=3)
文字輸入盒_猜 = TextBox(AB, Hint="輸入 4 個不重複數字", NumbersOnly=True, Width=-2)
按鈕_猜 = Button(AB, Text="猜", Width=-2)
標籤_紀錄 = Label(AB, Text="", FontSize=18, Width=-2)

答案 = ""
A = 0
B = 0
候選 = []

@when(AB.Initialize)
def _():
    候選 = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    答案 = ""
    for i in irange(1, 4, 1):
        位置 = random_int(1, len(候選))
        答案 = join(答案, 候選[位置])
        remove_item(候選, 位置)

位置 = 0

@when(按鈕_猜.Click)
def _():
    A = 0
    B = 0
    for i in irange(1, 4, 1):
        if text_equal(segment(文字輸入盒_猜.Text, i, 1), segment(答案, i, 1)):
            A = A + 1
        elif contains(答案, segment(文字輸入盒_猜.Text, i, 1)):
            B = B + 1
    標籤_紀錄.Text = join(標籤_紀錄.Text, 文字輸入盒_猜.Text, "  ", A, "A", B, "B\n")

#### SCREEN Watch
Watch = Form(Title="碼錶", AlignHorizontal=3)
標籤_時間 = Label(Watch, Text="0.0", FontSize=60, TextAlignment=1, Width=-2)
水平配置1 = HorizontalArrangement(Watch, AlignHorizontal=3, Width=-2)
按鈕_開始 = Button(水平配置1, Text="開始", Width=-1050)
按鈕_歸零 = Button(水平配置1, Text="歸零", Width=-1050)
計時器1 = Clock(Watch, TimerInterval=100, TimerEnabled=False)

秒數 = 0

@when(按鈕_開始.Click)
def _():
    計時器1.TimerEnabled = not 計時器1.TimerEnabled
    if 計時器1.TimerEnabled:
        按鈕_開始.Text = "暫停"
    else:
        按鈕_開始.Text = "開始"

@when(計時器1.Timer)
def _():
    秒數 = 秒數 + 0.1
    標籤_時間.Text = format_decimal(秒數, 1)

@when(按鈕_歸零.Click)
def _():
    秒數 = 0
    標籤_時間.Text = "0.0"
