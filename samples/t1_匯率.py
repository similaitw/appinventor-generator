Screen1 = Form(Title="匯率換算", AlignHorizontal=3)
標籤1 = Label(Screen1, Text="新台幣金額", FontSize=18)
文字輸入盒_台幣 = TextBox(Screen1, NumbersOnly=True, Width=-2)
下拉_幣別 = Spinner(Screen1, ElementsFromString="美元,日圓,歐元", Width=-2)
按鈕_換算 = Button(Screen1, Text="換算", Width=-2)
標籤_結果 = Label(Screen1, Text="", FontSize=24, TextAlignment=1, Width=-2)

匯率表 = [32.5, 0.21, 35.2]

@when(按鈕_換算.Click)
def _():
    if is_number(文字輸入盒_台幣.Text):
        標籤_結果.Text = join(format_decimal(文字輸入盒_台幣.Text / 匯率表[下拉_幣別.SelectionIndex], 2), " ", 下拉_幣別.Selection)
    else:
        標籤_結果.Text = "請輸入數字"
