from random import randint 
from time import sleep

# --- 創造水果的函式 (不變) ---
def create(n,x,y):
    a=sprite('水果',x, y)
    a.setCircle(25+(n+1)*10)
    a.setBounce(0.8).setFrame(n)


# --- 遊戲準備 ---
pick=image('水果', 400, 80) # 準備區的水果

# --- 遊戲主迴圈 ---
while True:
    # 讓準備區的水果跟隨滑鼠
    pick.setXY(mouseX(),80)
    
    # 如果滑鼠按下（放下水果）
    if isDown('mouse'):
        audio('按鈕類3').play() # 音效
        pick.hide() # 暫時隱藏
        # 在滑鼠位置創造一個新水果
        create(pick.frame, pick.x, pick.y)
        sleep(0.2) # 延遲，防手滑
        # 隨機產生下一個水果
        pick.setFrame(randint(1,4))
        pick.show() # 顯示下一個水果

    # --- 檢查勝利、失敗、合併條件 ---
    for a in getSprites('水果'):
        
        # 1. 勝利條件：合成出第10級的水果
        if a.frame==10:
            text('YOU WIN!!',270, 480, 100)
            stop()

        # 2. 檢查 'a' 是否碰到了「另一個水果 b」
        #    我們假設 a.isMeet('水果') 會返回那個水果 b
        b = a.isMeet('水果') 

        # 3. 失敗條件：如果 b 存在 (有碰撞) 且 'a' 堆太高
        if b and a.y<200:
            text('YOU LOSE!!',270, 480, 100)
            stop()
            
        # 4. 合併條件：如果 b 存在 且 兩者等級相同
        if b and a.frame == b.frame:
            # 確保它們不是在頂部合併 (避免在失敗區合併)
            if a.y > 200 and b.y > 200:
                audio('按鈕類7').play() # 音效
                create(a.frame+1,a.x,a.y)
                a.destroy()
                b.destroy()
                # 因為我們修改了精靈列表，
                # 最好立刻跳出迴圈，下一輪再重新檢查
                break