Screen1 = Form(Title="骰子", AlignHorizontal=3, AlignVertical=2)
標籤_點數 = Label(Screen1, Text="🎲", FontSize=100, TextAlignment=1, Width=-2)
按鈕_擲 = Button(Screen1, Text="擲骰子", FontSize=24, Width=-2)
計時器1 = Clock(Screen1, TimerInterval=100, TimerEnabled=False)

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
