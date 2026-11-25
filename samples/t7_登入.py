#### SCREEN Screen1
Screen1 = Form(Title="登入", AlignHorizontal=3)
文字輸入盒_帳號 = TextBox(Screen1, Hint="帳號", Width=-2)
密碼輸入盒1 = PasswordTextBox(Screen1, Hint="密碼", Width=-2)
按鈕_登入 = Button(Screen1, Text="登入", Width=-2)
對話框1 = Notifier(Screen1)

@when(按鈕_登入.Click)
def _():
    if 文字輸入盒_帳號.Text == "student" and 密碼輸入盒1.Text == "1234":
        open_screen_with_value("Screen2", 文字輸入盒_帳號.Text)
    else:
        對話框1.ShowAlert("帳號或密碼錯誤")

#### SCREEN Screen2
Screen2 = Form(Title="歡迎", AlignHorizontal=3)
標籤_歡迎 = Label(Screen2, Text="", FontSize=24)
按鈕_登出 = Button(Screen2, Text="登出")

@when(Screen2.Initialize)
def _():
    標籤_歡迎.Text = join("歡迎，", get_start_value())

@when(按鈕_登出.Click)
def _():
    close_screen()
