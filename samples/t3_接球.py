Screen1 = Form(Title="接球遊戲")
標籤_分數 = Label(Screen1, Text="分數：0", FontSize=20)
Canvas1 = Canvas(Screen1, Width=-2, Height=-2, BackgroundColor="&HFFE0F7FA")
球1 = Ball(Canvas1, Radius=15, PaintColor="&HFFFF5722", Speed=8, Heading=60, Interval=30, X=50, Y=20)

分數 = 0

@when(球1.EdgeReached)
def _(edge):
    if edge == -1:
        球1.MoveTo(random_int(20, 200), 10)
        分數 = 0
    else:
        球1.Bounce(edge)
    標籤_分數.Text = join("分數：", 分數)

@when(Canvas1.Touched)
def _(x, y, touchedAnySprite):
    if touchedAnySprite:
        分數 = 分數 + 1
        球1.Heading = random_int(30, 150)
        標籤_分數.Text = join("分數：", 分數)
