Screen1 = Form(Title="記事本")
文字輸入盒_內容 = TextBox(Screen1, Hint="輸入待辦事項", Width=-2)
水平配置1 = HorizontalArrangement(Screen1, Width=-2)
按鈕_新增 = Button(水平配置1, Text="新增", Width=-1050)
按鈕_清空 = Button(水平配置1, Text="全部清除", Width=-1050)
清單檢視1 = ListView(Screen1, Width=-2, Height=-2)
微型資料庫1 = TinyDB(Screen1)
對話框1 = Notifier(Screen1)

事項 = []

@when(Screen1.Initialize)
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
