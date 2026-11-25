Screen1 = Form(Title="碼錶", AlignHorizontal=3)
標籤_時間 = Label(Screen1, Text="0.0", FontSize=60, TextAlignment=1, Width=-2)
水平配置1 = HorizontalArrangement(Screen1, AlignHorizontal=3, Width=-2)
按鈕_開始 = Button(水平配置1, Text="開始", Width=-1050)
按鈕_歸零 = Button(水平配置1, Text="歸零", Width=-1050)
計時器1 = Clock(Screen1, TimerInterval=100, TimerEnabled=False)

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
