import pygame
import pymunk
import pymunk.pygame_util
import random
import sys
import math
import os    
import ctypes 

try:
    ctypes.windll.user32.SetProcessDPIAware() 
except:
    pass 
os.environ['SDL_VIDEO_CENTERED'] = '1'


# --- 1. Pygame 和 Pymunk 初始化 ---

SCALE = 0.75 

pygame.init()
pygame.mixer.init() 

SCREEN_WIDTH = int(800 * SCALE)
SCREEN_HEIGHT = int(960 * SCALE) 
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("水果合成遊戲")

# (修改) <--- 為了展示新的冬季配色，暫時不使用背景圖片 --->
# (您可以將 'my_background.jpg' 替換回來以使用您自己的圖片)
try:
    # background_image = pygame.image.load('my_background.jpg') 
    background_image = None # <--- 設為 None 來使用純色背景
    if background_image: # 只在圖片存在時才縮放
        background_image = pygame.transform.scale(background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
except Exception as e:
    background_image = None 

# 遊戲時鐘 (控制 FPS)
clock = pygame.time.Clock()

# Pymunk 物理空間
space = pymunk.Space()
space.gravity = (0, 981 * SCALE) 

# Pygame 繪圖設定 (用於Pymunk偵錯)
draw_options = pymunk.pygame_util.DrawOptions(screen)

# 遊戲狀態
game_running = True
score = 0
game_over = False
win_game = False
is_aiming = False 

# "YOU LOSE" 計時器 (5秒)
lose_timer_start = 0      
LOSE_DURATION_MS = 5000   

TOP_AREA_HEIGHT = int(200 * SCALE) 
GAME_AREA_HEIGHT = SCREEN_HEIGHT - TOP_AREA_HEIGHT
LOSE_LINE_Y = TOP_AREA_HEIGHT + int(20 * SCALE) # Y座標

# --- 2. 遊戲資源 (顏色、音效) ---

try:
    drop_sound = pygame.mixer.Sound('DROP.wav') 
    merge_sound = pygame.mixer.Sound('COLLISION.wav')
except (pygame.error, FileNotFoundError) as e:
    print(f"警告：無法載入音效檔案。 {e}")
    class DummySound:
        def play(self): pass
    drop_sound = DummySound()
    merge_sound = DummySound()

# (修改) <--- 1. 水果顏色替換為 "冬季淺冷色系" --->
FRUIT_COLORS = [
    (0, 0, 0),       # 0: 佔位
    (255, 255, 255), # 1: 雪白 (Snow White)
    (220, 235, 255), # 2: 冰藍 (Alice Blue)
    (210, 255, 255), # 3: 淡青 (Light Cyan)
    (210, 210, 220), # 4: 霜灰 (Light Gray/Silver)
    (220, 210, 255), # 5: 淺紫 (Light Lavender)
    (170, 200, 255), # 6: 天藍 (Powder Blue)
    (190, 170, 255), # 7: 薰衣草 (Medium Lavender)
    (100, 150, 255), # 8: 寶藍 (Royal Blue)
    (150, 100, 255), # 9: 靛紫 (Medium Purple)
    (180, 255, 255), # 10: 亮青 (Bright Icy Cyan) - 西瓜
]
# (修改) <--- 顏色替換結束 --->


FRUIT_RADII = [0] + [int((25 + (n + 1) * 10) * SCALE) for n in range(1, 11)]
FRUIT_COLLISION_TYPE = 1 
fruits = []

# --- 3. 水果的 Class (Pymunk 核心) ---
class Fruit:
    def __init__(self, x, y, level, is_static=False):
        self.level = level
        self.radius = FRUIT_RADII[level] 
        
        if is_static:
            self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        else:
            mass = self.radius ** 2 
            moment = pymunk.moment_for_circle(mass, 0, self.radius)
            self.body = pymunk.Body(mass, moment)

        self.body.position = x, y
        
        self.shape = pymunk.Circle(self.body, self.radius)
        self.shape.elasticity = 0.4 
        self.shape.friction = 0.5   
        self.shape.collision_type = FRUIT_COLLISION_TYPE 
        self.shape.fruit_object = self 

        space.add(self.body, self.shape)
        fruits.append(self)

    def destroy(self):
        if self in fruits:
            space.remove(self.body, self.shape)
            fruits.remove(self)

    def draw(self):
        pos = self.body.position
        x, y = int(pos.x), int(pos.y)
        angle = self.body.angle
        
        color = FRUIT_COLORS[self.level]
        pygame.draw.circle(screen, color, (x, y), int(self.radius))

        # end_x = x + math.cos(angle) * self.radius
        # end_y = y + math.sin(angle) * self.radius
        # pygame.draw.line(screen, (0,0,0), (x,y), (end_x, end_y), 2) # 圓心黑線


# --- 4. Pymunk 碰撞處理 ---
fruits_to_remove = []
fruits_to_add = []

def handle_collision(arbiter, space, data):
    global score, win_game
    shape_a, shape_b = arbiter.shapes
    fruit_a = shape_a.fruit_object
    fruit_b = shape_b.fruit_object
    
    if fruit_a.level == fruit_b.level and fruit_a.level < 10:
        if fruit_a not in fruits_to_remove and fruit_b not in fruits_to_remove:
            pos_a = fruit_a.body.position
            pos_b = fruit_b.body.position
            new_x = (pos_a.x + pos_b.x) / 2
            new_y = (pos_a.y + pos_b.y) / 2
            new_level = fruit_a.level + 1
            
            fruits_to_remove.append(fruit_a)
            fruits_to_remove.append(fruit_b)
            fruits_to_add.append((new_x, new_y, new_level))
            
            merge_sound.play()
            score += new_level * 10
            
            if new_level == 10:
                win_game = True
    return True


# --- 5. 建立遊戲邊界 ---
def create_boundaries():
    bottom = pymunk.Segment(space.static_body, (0, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    left = pymunk.Segment(space.static_body, (0, 0), (0, SCREEN_HEIGHT), 5)
    right = pymunk.Segment(space.static_body, (SCREEN_WIDTH, 0), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    
    bottom.elasticity = 0.4
    left.elasticity = 0.4
    right.elasticity = 0.4
    
    space.add(bottom, left, right)

create_boundaries()

# --- 5.5. 註冊碰撞處理器 ---
space.on_collision(FRUIT_COLLISION_TYPE, FRUIT_COLLISION_TYPE, post_solve=handle_collision)


# --- 6. 遊戲準備區 ---
next_fruit_level = random.randint(1, 4)

def draw_next_fruit_indicator(mouse_x):
    x = max(FRUIT_RADII[next_fruit_level], min(mouse_x, SCREEN_WIDTH - FRUIT_RADII[next_fruit_level]))
    y = TOP_AREA_HEIGHT / 2 
    color = FRUIT_COLORS[next_fruit_level]
    pygame.draw.circle(screen, color, (int(x), int(y)), FRUIT_RADII[next_fruit_level])


# --- 7. 繪製文字函式 ---
font = pygame.font.SysFont("simhei", int(60 * SCALE)) 
font_large = pygame.font.SysFont("simhei", int(100 * SCALE))

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
        
        if event.type == pygame.MOUSEBUTTONDOWN and not game_over and not win_game:
            is_aiming = True

        if event.type == pygame.MOUSEBUTTONUP and is_aiming:
            is_aiming = False
            
            drop_x = max(FRUIT_RADII[next_fruit_level], min(mouse_pos[0], SCREEN_WIDTH - FRUIT_RADII[next_fruit_level]))
            drop_y = TOP_AREA_HEIGHT 
            
            Fruit(drop_x, drop_y, next_fruit_level)
            drop_sound.play() 

            next_fruit_level = random.randint(1, 4)

    
    # (B) 更新遊戲邏輯 (Logic)
    
    if not game_over and not win_game:
        dt = 1.0 / 60.0
        space.step(dt)

        for fruit_obj in fruits_to_remove:
            fruit_obj.destroy()
        fruits_to_remove.clear()
        
        for x, y, level in fruits_to_add:
            Fruit(x, y, level) 
        fruits_to_add.clear()

        is_fruit_dangerously_high = False
        for fruit in fruits:
            if fruit.body.position.y < LOSE_LINE_Y:
                is_fruit_dangerously_high = True
                break 

        if is_fruit_dangerously_high:
            if lose_timer_start == 0:
                lose_timer_start = pygame.time.get_ticks()
            else:
                elapsed_time = pygame.time.get_ticks() - lose_timer_start
                if elapsed_time > LOSE_DURATION_MS:
                    game_over = True
        else:
            lose_timer_start = 0

    # (C) 繪製畫面 (Render)
    
    if background_image:
        screen.blit(background_image, (0, 0))
    else:
        # (修改) <--- 2. 背景色 --->
        screen.fill((135, 155, 180)) 
    
    # (修改) <--- 3. 頂部準備區顏色: 淺鋼藍色 --->
    pygame.draw.rect(screen, (190, 200, 220), (0, 0, SCREEN_WIDTH, TOP_AREA_HEIGHT)) 

    # 繪製失敗線 (紅色虛線)
    DASH_LENGTH = int(20 * SCALE)  
    GAP_LENGTH = int(10 * SCALE)   
    LINE_THICKNESS = int(5 * SCALE) 

    current_x = 0
    while current_x < SCREEN_WIDTH:
        start_point = (current_x, LOSE_LINE_Y)
        end_point = (min(current_x + DASH_LENGTH, SCREEN_WIDTH), LOSE_LINE_Y)
        # (修改) <--- 4. 失敗線顏色: 醒目的冰藍色 --->
        pygame.draw.line(screen, (0, 150, 255), start_point, end_point, LINE_THICKNESS)
        current_x += (DASH_LENGTH + GAP_LENGTH)
    
    # 繪製瞄準輔助線
    if is_aiming:
        aim_x = max(FRUIT_RADII[next_fruit_level], min(mouse_pos[0], SCREEN_WIDTH - FRUIT_RADII[next_fruit_level]))
        
        AIM_DASH_LENGTH = int(15 * SCALE)
        AIM_GAP_LENGTH = int(10 * SCALE)
        AIM_LINE_THICKNESS = int(2 * SCALE)
        # (修改) <--- 5. 瞄準線顏色 --->
        AIM_LINE_COLOR = (190, 200, 220) 
        
        current_y = LOSE_LINE_Y
        while current_y < SCREEN_HEIGHT:
            start_point = (aim_x, current_y)
            end_point = (aim_x, min(current_y + AIM_DASH_LENGTH, SCREEN_HEIGHT))
            pygame.draw.line(screen, AIM_LINE_COLOR, start_point, end_point, AIM_LINE_THICKNESS)
            current_y += (AIM_DASH_LENGTH + AIM_GAP_LENGTH)

    # 繪製所有水果
    for fruit in fruits:
        fruit.draw()
        
    # 繪製準備區的水果
    if not game_over and not win_game:
        draw_next_fruit_indicator(mouse_pos[0]) 
        
    # (修改) <--- 6. 分數顏色: 深海軍藍 (才能在淺色背景上顯示) --->
    draw_text(f"Score: {score}", font, (30, 40, 80), SCREEN_WIDTH / 2, TOP_AREA_HEIGHT + int(50 * SCALE))
    
    # 處理遊戲結束/勝利
    if game_over:
        # (修改) <--- 7. YOU LOSE 顏色: 深藍色 --->
        draw_text("YOU LOSE!!", font_large, (50, 50, 150), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
    if win_game:
        # (修改) <--- 8. YOU WIN 顏色: 亮青色 --->
        draw_text("YOU WIN!!", font_large, (0, 255, 255), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        
    pygame.display.flip()
    
    clock.tick(60) 


# --- 9. 遊戲結束 ---
pygame.quit()
sys.exit()