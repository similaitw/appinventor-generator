Screen1 = Form(Title="1A2B", AlignHorizontal=3)
文字輸入盒_猜 = TextBox(Screen1, Hint="輸入 4 個不重複數字", NumbersOnly=True, Width=-2)
按鈕_猜 = Button(Screen1, Text="猜", Width=-2)
標籤_紀錄 = Label(Screen1, Text="", FontSize=18, Width=-2)

答案 = ""
A = 0
B = 0
候選 = []

@when(Screen1.Initialize)
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
