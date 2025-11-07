import pygame
import pymunk
import pymunk.pygame_util
import random
import sys
import math
import itertools # <--- 我們需要這個來幫我們做 "配對"

# --- 1. Pygame 和 Pymunk 初始化 ---

pygame.init()
pygame.mixer.init() # 初始化音效

# 遊戲視窗設定
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 960 # 800 + 160 的頂部空間
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("水果合成遊戲 (手動碰撞檢查版)")

# 遊戲時鐘 (控制 FPS)
clock = pygame.time.Clock()

# Pymunk 物理空間
space = pymunk.Space()
space.gravity = (0, 981) # 模擬重力 (y軸向下為正)

# Pygame 繪圖設定 (用於Pymunk偵錯)
draw_options = pymunk.pygame_util.DrawOptions(screen)

# 遊戲狀態
game_running = True
score = 0
game_over = False
win_game = False

# 水果的頂部區域 (準備區 + 失敗線)
TOP_AREA_HEIGHT = 200 # 原本 y=80 + y<200 的區域
GAME_AREA_HEIGHT = SCREEN_HEIGHT - TOP_AREA_HEIGHT
LOSE_LINE_Y = TOP_AREA_HEIGHT + 20 # Y座標 220

# --- 2. 遊戲資源 (顏色、音效) ---

# 載入音效 (你需要有這些檔案)
try:
    drop_sound = pygame.mixer.Sound('按鈕類3.wav') # 假設是 .wav
    merge_sound = pygame.mixer.Sound('按鈕類7.wav')
    
# =================================================================
# ⭐⭐⭐ 程式碼修改處 ⭐⭐⭐
#
# 這裡就是我們修改的地方，同時捕捉 pygame.error 和 FileNotFoundError
# 這樣就算找不到檔案，程式也不會當機
#
except (pygame.error, FileNotFoundError) as e:
# =================================================================
    print(f"警告：無法載入音效檔案。 {e}")
    # 建立無聲的 "假" 音效，避免程式崩潰
    class DummySound:
        def play(self): pass
    drop_sound = DummySound()
    merge_sound = DummySound()

# 為了方便執行，我們用顏色代表水果等級 (frame)
# 索引 0 不用，從 1 (n=1) 開始
FRUIT_COLORS = [
    (0, 0, 0),       # 0: 佔位
    (255, 100, 100), # 1: 紅
    (255, 165, 0),   # 2: 橘
    (255, 255, 0),   # 3: 黃
    (100, 255, 100), # 4: 綠
    (100, 100, 255), # 5: 藍
    (100, 0, 100),   # 6: 紫
    (200, 200, 200), # 7: 灰
    (255, 20, 147),  # 8: 深粉紅
    (0, 255, 255),   # 9: 青
    (255, 255, 255), # 10: 白 (西瓜)
]

# 水果半徑 (依照你 create 函式中的 setCircle)
FRUIT_RADII = [0] + [25 + (n + 1) * 10 for n in range(1, 11)]

# 物理設定
FRUIT_COLLISION_TYPE = 1 # 所有水果都用同一個碰撞類型

# 儲存所有在場上的水果物件
fruits = []

# --- 3. 水果的 Class (Pymunk 核心) ---

class Fruit:
    def __init__(self, x, y, level, is_static=False):
        self.level = level
        self.radius = FRUIT_RADII[level]
        
        # 1. 建立物理 "剛體" (Body)
        if is_static:
            self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        else:
            mass = self.radius ** 2 # 質量隨半徑平方增加
            moment = pymunk.moment_for_circle(mass, 0, self.radius)
            self.body = pymunk.Body(mass, moment)

        self.body.position = x, y
        
        # 2. 建立物理 "形狀" (Shape)
        self.shape = pymunk.Circle(self.body, self.radius)
        self.shape.elasticity = 0.4 # 反彈係數
        self.shape.friction = 0.5   # 摩擦力
        
        self.shape.collision_type = FRUIT_COLLISION_TYPE 
        self.shape.fruit_object = self

        # 3. 將剛體和形狀加入到物理空間
        space.add(self.body, self.shape)
        fruits.append(self)

    def destroy(self):
        """從物理空間和列表中移除"""
        if self in fruits:
            space.remove(self.body, self.shape)
            fruits.remove(self)

    def draw(self):
        """在 Pygame 視窗上繪製自己"""
        pos = self.body.position
        x, y = int(pos.x), int(pos.y)
        angle = self.body.angle
        
        # 繪製圓形
        color = FRUIT_COLORS[self.level]
        pygame.draw.circle(screen, color, (x, y), int(self.radius))

        # 為了偵錯，畫一條線表示旋轉
        end_x = x + math.cos(angle) * self.radius
        end_y = y + math.sin(angle) * self.radius
        pygame.draw.line(screen, (0,0,0), (x,y), (end_x, end_y), 2)


# --- 4. Pymunk 碰撞處理 (手動) ---

fruits_to_remove = []
fruits_to_add = []


# --- 5. 建立遊戲邊界 (Pymunk 的靜態牆壁) ---

def create_boundaries():
    """建立遊戲區的牆壁"""
    bottom = pymunk.Segment(space.static_body, (0, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    left = pymunk.Segment(space.static_body, (0, TOP_AREA_HEIGHT), (0, SCREEN_HEIGHT), 5)
    right = pymunk.Segment(space.static_body, (SCREEN_WIDTH, TOP_AREA_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    
    bottom.elasticity = 0.4
    left.elasticity = 0.4
    right.elasticity = 0.4
    
    space.add(bottom, left, right)

create_boundaries()


# --- 6. 遊戲準備區 (和你的 pick 邏輯一樣) ---

next_fruit_level = random.randint(1, 4)

def draw_next_fruit_indicator(mouse_x):
    """在頂部繪製準備區的水果"""
    x = max(FRUIT_RADII[next_fruit_level], min(mouse_x, SCREEN_WIDTH - FRUIT_RADII[next_fruit_level]))
    y = TOP_AREA_HEIGHT / 2 # 放在準備區中間 (y=100)
    
    color = FRUIT_COLORS[next_fruit_level]
    pygame.draw.circle(screen, color, (int(x), int(y)), FRUIT_RADII[next_fruit_level])


# --- 7. 繪製文字函式 ---
font = pygame.font.SysFont("simhei", 60) # 使用系統內建的黑體 (或 "mingliu")
font_large = pygame.font.SysFont("simhei", 100)

def draw_text(text, font_to_use, color, x, y):
    text_surface = font_to_use.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    screen.blit(text_surface, text_rect)


# --- 8. 遊戲主迴圈 (Pygame 的核心) ---

while game_running:
    
    # (A) 處理輸入事件 (Event)
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_running = False
        
        # 檢查滑鼠按下
        if event.type == pygame.MOUSEBUTTONDOWN and not game_over and not win_game:
            if mouse_pos[1] < TOP_AREA_HEIGHT:
                
                # 1. 取得滑鼠 x 位置
                drop_x = max(FRUIT_RADII[next_fruit_level], min(mouse_pos[0], SCREEN_WIDTH - FRUIT_RADII[next_fruit_level]))
                drop_y = TOP_AREA_HEIGHT 
                
                # 2. 創造水果
                Fruit(drop_x, drop_y, next_fruit_level)
                drop_sound.play() # 這裡會呼叫 "假" 的 play()

                # 3. 產生下一個水果
                next_fruit_level = random.randint(1, 4)

    
    # (B) 更新遊戲邏輯 (Logic)
    
    if not game_over and not win_game:
        # Pymunk 物理更新
        dt = 1.0 / 60.0
        space.step(dt)

        # 手動碰撞檢查
        for fruit_a, fruit_b in itertools.combinations(fruits, 2):
            
            # 檢查是否符合合併條件 (等級相同)
            if fruit_a.level == fruit_b.level and fruit_a.level < 10:
                
                # 手動計算它們之間的距離
                pos_a = fruit_a.body.position
                pos_b = fruit_b.body.position
                
                dist_sq = (pos_a.x - pos_b.x)**2 + (pos_a.y - pos_b.y)**2
                
                # 計算它們 "應該" 碰撞的距離
                radius_sum = fruit_a.radius + fruit_b.radius
                
                # 如果它們 "重疊" 了 
                if dist_sq < (radius_sum * 0.9)**2:
                    
                    # 執行合併邏輯
                    if fruit_a not in fruits_to_remove and fruit_b not in fruits_to_remove:
                        
                        fruits_to_remove.append(fruit_a)
                        fruits_to_remove.append(fruit_b)
                        
                        new_x = (pos_a.x + pos_b.x) / 2
                        new_y = (pos_a.y + pos_b.y) / 2
                        new_level = fruit_a.level + 1
                        
                        fruits_to_add.append((new_x, new_y, new_level))
                        
                        merge_sound.play() # 這裡會呼叫 "假" 的 play()
                        score += new_level * 10
                        
                        if new_level == 10:
                            win_game = True
        
        # 處理 "待辦事項" (移除和新增水果)
        for fruit_obj in fruits_to_remove:
            fruit_obj.destroy()
        fruits_to_remove.clear()
        
        for x, y, level in fruits_to_add:
            Fruit(x, y, level) # 創造新水果
        fruits_to_add.clear()

        # 檢查失敗條件
        for fruit in fruits:
            if fruit.body.position.y < LOSE_LINE_Y: 
                if fruit.body.is_sleeping:
                    game_over = True
                    break

    # (C) 繪製畫面 (Render)
    
    # 1. 填滿背景色
    screen.fill((50, 50, 70)) # 深藍灰色
    
    # 2. 繪製準備區和失敗線
    pygame.draw.rect(screen, (40, 40, 50), (0, 0, SCREEN_WIDTH, TOP_AREA_HEIGHT))
    pygame.draw.line(screen, (255, 0, 0), (0, LOSE_LINE_Y), (SCREEN_WIDTH, LOSE_LINE_Y), 3)

    # 3. 繪製所有水果
    for fruit in fruits:
        fruit.draw()
        
    # 4. 繪製準備區的水果
    if not game_over and not win_game:
        draw_next_fruit_indicator(mouse_pos[0])
        
    # 5. 繪製分數
    draw_text(f"分數: {score}", font, (255, 255, 255), SCREEN_WIDTH / 2, TOP_AREA_HEIGHT + 50)
    
    # 6. 處理遊戲結束/勝利
    if game_over:
        draw_text("YOU LOSE!!", font_large, (255, 0, 0), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
    if win_game:
        draw_text("YOU WIN!!", font_large, (255, 255, 0), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        
    # 7. 更新螢幕
    pygame.display.flip()
    
    # 8. 控制 FPS
    clock.tick(60) # 保持每秒 60 幀


# --- 9. 遊戲結束 ---
pygame.quit()
sys.exit()