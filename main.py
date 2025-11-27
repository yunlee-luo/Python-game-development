import pygame
import pymunk
import pymunk.pygame_util
import random
import sys
import math
import os    
import ctypes 

# --- 0. 系統與視窗設定 ---
try:
    ctypes.windll.user32.SetProcessDPIAware() 
except:
    pass 
os.environ['SDL_VIDEO_CENTERED'] = '1'

# 1. 音效低延遲優化 (必須在 pygame.init 之前)
pygame.mixer.pre_init(44100, -16, 2, 512) 

SCALE = 0.75 

pygame.init()
pygame.mixer.init() 

SCREEN_WIDTH = int(800 * SCALE)
SCREEN_HEIGHT = int(960 * SCALE) 
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("合成大'星'瓜 (終極版)")

# --- 1. 全域變數與常數 ---
clock = pygame.time.Clock()
space = pymunk.Space()
space.gravity = (0, 981 * SCALE) 

# 遊戲狀態
game_running = True
score = 0
high_score = 0 # 最高分
game_over = False
win_game = False
is_aiming = False 

# 投擲冷卻設定
last_drop_time = 0
DROP_COOLDOWN = 600 # 毫秒 (0.6秒)

# 失敗計時器
lose_timer_start = 0      
LOSE_DURATION_MS = 5000   

# 區域尺寸
TOP_AREA_HEIGHT = int(200 * SCALE) 
GAME_AREA_HEIGHT = SCREEN_HEIGHT - TOP_AREA_HEIGHT
LOSE_LINE_Y = TOP_AREA_HEIGHT + int(20 * SCALE) 

# --- 2. 資源載入與處理 ---

# 音效載入
try:
    drop_sound = pygame.mixer.Sound('DROP.wav') 
    merge_sound = pygame.mixer.Sound('COLLISION.wav')
except (pygame.error, FileNotFoundError) as e:
    print(f"警告：無法載入音效檔案。 {e}")
    class DummySound:
        def play(self): pass
    drop_sound = DummySound()
    merge_sound = DummySound()

# 讀取最高分
def load_high_score():
    try:
        with open("highscore.txt", "r") as f:
            return int(f.read())
    except:
        return 0

def save_high_score(new_score):
    try:
        with open("highscore.txt", "w") as f:
            f.write(str(new_score))
    except:
        pass

high_score = load_high_score()

# 背景自動生成
def create_starry_background(width, height):
    bg = pygame.Surface((width, height))
    bg.fill((20, 25, 40)) 
    for _ in range(200): 
        x = random.randint(0, width)
        y = random.randint(0, height)
        radius = random.randint(1, 3) if random.random() > 0.95 else 1
        brightness = random.randint(100, 255)
        color = (brightness, brightness, brightness)
        pygame.draw.circle(bg, color, (x, y), radius)
    return bg

background_image = create_starry_background(SCREEN_WIDTH, SCREEN_HEIGHT)

# 星球半徑 (1~9級)
PLANET_RADII = [0] + [int((25 + (n + 1) * 10) * SCALE) for n in range(1, 10)]

# 得分表
DROP_SCORES = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500}
MERGE_SCORES = {2: 300, 3: 600, 4: 1000, 5: 1500, 6: 2100, 7: 2800, 8: 3600, 9: 4500}

# 圓形切割函式
def crop_to_circle(image):
    rect = image.get_rect()
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255), rect.center, rect.width // 2)
    new_img = image.copy().convert_alpha()
    new_img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return new_img

# 載入星球圖片
PLANET_IMAGES = [None] 
for i in range(1, 10): 
    try:
        img_path = os.path.join('assets', f'planet_{i}.png') 
        original_image = pygame.image.load(img_path).convert_alpha() 
        target_size = (PLANET_RADII[i]*2, PLANET_RADII[i]*2)
        scaled_image = pygame.transform.scale(original_image, target_size)
        final_image = crop_to_circle(scaled_image)
        PLANET_IMAGES.append(final_image)
        print(f"成功載入星球: {img_path}")
    except Exception as e:
        print(f"警告: 載入圖片 {img_path} 失敗: {e}")
        PLANET_IMAGES.append(None)

# 備用顏色
PLANET_COLORS = [
    (0, 0, 0), (255, 255, 255), (220, 235, 255), (210, 255, 255), (210, 210, 220), 
    (220, 210, 255), (170, 200, 255), (190, 170, 255), (100, 150, 255), (150, 100, 255)
]

PLANET_COLLISION_TYPE = 1 
planets = [] 

# --- 3. 類別定義 (粒子與星球) ---

# [優化] 粒子特效類別
class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.vx = random.uniform(-5, 5) * SCALE
        self.vy = random.uniform(-5, 5) * SCALE
        self.life = 255 # 透明度壽命
        self.size = random.randint(4, 8) * SCALE
        self.decay = random.randint(5, 10) # 消失速度

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        self.size -= 0.1

    def draw(self, surface):
        if self.life > 0 and self.size > 0:
            s = pygame.Surface((int(self.size*2), int(self.size*2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, int(self.life)), (int(self.size), int(self.size)), int(self.size))
            surface.blit(s, (int(self.x - self.size), int(self.y - self.size)))

particles = [] # 儲存所有粒子

# 星球類別
class Planet:
    def __init__(self, x, y, level, is_static=False):
        self.level = level
        self.radius = PLANET_RADII[level] 
        
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
        self.shape.collision_type = PLANET_COLLISION_TYPE 
        self.shape.planet_object = self 

        space.add(self.body, self.shape)
        planets.append(self)

    def destroy(self):
        if self in planets:
            space.remove(self.body, self.shape)
            planets.remove(self)

    def draw(self):
        pos = self.body.position
        x, y = int(pos.x), int(pos.y)
        image = PLANET_IMAGES[self.level]
        if image:
            image_rect = image.get_rect(center=(x, y))
            screen.blit(image, image_rect)
        else:
            color = PLANET_COLORS[self.level]
            pygame.draw.circle(screen, color, (x, y), int(self.radius))

# --- 4. 碰撞與物理邏輯 ---

planets_to_remove = []
planets_to_add = []

def handle_collision(arbiter, space, data):
    global score, high_score, win_game
    shape_a, shape_b = arbiter.shapes
    planet_a = shape_a.planet_object
    planet_b = shape_b.planet_object
    
    if planet_a.level == planet_b.level and planet_a.level < 9:
        if planet_a not in planets_to_remove and planet_b not in planets_to_remove:
            pos_a = planet_a.body.position
            pos_b = planet_b.body.position
            new_x = (pos_a.x + pos_b.x) / 2
            new_y = (pos_a.y + pos_b.y) / 2
            new_level = planet_a.level + 1
            
            planets_to_remove.append(planet_a)
            planets_to_remove.append(planet_b)
            planets_to_add.append((new_x, new_y, new_level))
            
            merge_sound.play()

            # [優化] 產生爆炸粒子
            p_color = PLANET_COLORS[new_level] # 使用新星球的顏色
            for _ in range(15):
                particles.append(Particle(new_x, new_y, p_color))

            # 計算分數
            if new_level in MERGE_SCORES:
                score += MERGE_SCORES[new_level]
            else:
                score += new_level * 100
            
            # 更新最高分
            if score > high_score:
                high_score = score
                save_high_score(high_score)

            if new_level == 9:
                win_game = True
    return True

# 建立邊界
def create_boundaries():
    bottom = pymunk.Segment(space.static_body, (0, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    left = pymunk.Segment(space.static_body, (0, 0), (0, SCREEN_HEIGHT), 5)
    right = pymunk.Segment(space.static_body, (SCREEN_WIDTH, 0), (SCREEN_WIDTH, SCREEN_HEIGHT), 5)
    bottom.elasticity = 0.4
    left.elasticity = 0.4
    right.elasticity = 0.4
    space.add(bottom, left, right)

create_boundaries()
space.on_collision(PLANET_COLLISION_TYPE, PLANET_COLLISION_TYPE, post_solve=handle_collision)

# --- 5. UI 與 繪圖函式 ---

# 字型設定
font_name = "arial" 
if sys.platform.startswith("win"): font_name = "microsoftjhenghei" 
elif sys.platform.startswith("darwin"): font_name = "pingfangtc"
else: font_name = "wqy-microhei"

try:
    font = pygame.font.SysFont(font_name, int(60 * SCALE)) 
    font_large = pygame.font.SysFont(font_name, int(100 * SCALE))
    font_small = pygame.font.SysFont(font_name, int(40 * SCALE)) # 顯示最高分用
except:
    font = pygame.font.SysFont(None, int(60 * SCALE))
    font_large = pygame.font.SysFont(None, int(100 * SCALE))
    font_small = pygame.font.SysFont(None, int(40 * SCALE))

def draw_text(text, font_to_use, color, x, y):
    text_surface = font_to_use.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    screen.blit(text_surface, text_rect)

def draw_cosmic_button(surface, rect, text, font_obj, hover=False):
    if hover:
        bg_color, border_color = (60, 40, 90), (200, 255, 255) 
        shadow_color = (0, 255, 255)
    else:
        bg_color, border_color = (30, 20, 50), (0, 200, 255)
        shadow_color = (0, 100, 150)

    pygame.draw.rect(surface, shadow_color, rect.inflate(4, 4), 2, border_radius=18)
    pygame.draw.rect(surface, bg_color, rect, border_radius=15)
    pygame.draw.rect(surface, border_color, rect, 3, border_radius=15)
    
    text_surf = font_obj.render(text, True, (255, 255, 255))
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)

# 準備區
next_planet_level = random.randint(1, 4)
def draw_next_planet_indicator(mouse_x):
    x = max(PLANET_RADII[next_planet_level], min(mouse_x, SCREEN_WIDTH - PLANET_RADII[next_planet_level]))
    y = TOP_AREA_HEIGHT / 2 
    image = PLANET_IMAGES[next_planet_level]
    if image:
        image_rect = image.get_rect(center=(int(x), int(y)))
        screen.blit(image, image_rect)
    else:
        color = PLANET_COLORS[next_planet_level]
        pygame.draw.circle(screen, color, (int(x), int(y)), PLANET_RADII[next_planet_level])

# 重置遊戲
BTN_W, BTN_H = int(300 * SCALE), int(100 * SCALE)
BTN_X = (SCREEN_WIDTH - BTN_W) // 2
BTN_Y = (SCREEN_HEIGHT - BTN_H) // 2 + int(100 * SCALE)
RESTART_BTN_RECT = pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H)

def reset_game():
    global score, game_over, win_game, lose_timer_start, next_planet_level, planets
    for p in planets[:]: 
        p.destroy()
    planets.clear() 
    score = 0
    game_over = False
    win_game = False
    lose_timer_start = 0
    next_planet_level = random.randint(1, 4)

# --- 6. 開始畫面 ---
def game_start_screen():
    intro = True
    btn_rect = RESTART_BTN_RECT.copy() 
    # 微調開始畫面按鈕位置，與結束畫面一致或分開皆可，這裡共用 RESTART_BTN_RECT 的參數
    
    while intro:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_rect.collidepoint(event.pos):
                    intro = False 

        if background_image:
            screen.blit(background_image, (0, 0))
        else:
            screen.fill((20, 25, 40))

        title_text = font_large.render("合成大'星'瓜", True, (255, 255, 0))
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - int(100 * SCALE)))
        screen.blit(title_text, title_rect)

        mouse_pos = pygame.mouse.get_pos()
        is_hover = btn_rect.collidepoint(mouse_pos)
        draw_cosmic_button(screen, btn_rect, "開始遊戲", font, is_hover)
        pygame.display.flip()

game_start_screen()

# --- 7. 遊戲主迴圈 ---

while game_running:
    
    current_time = pygame.time.get_ticks()
    mouse_pos = pygame.mouse.get_pos()
    
    # [優化] 事件分流處理
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_running = False
        
        # 1. 遊戲進行中的事件
        if not game_over and not win_game:
            if event.type == pygame.MOUSEBUTTONDOWN:
                # 只有在冷卻時間過後才允許瞄準
                if current_time - last_drop_time > DROP_COOLDOWN:
                    is_aiming = True

            if event.type == pygame.MOUSEBUTTONUP and is_aiming:
                is_aiming = False
                # 執行發射
                drop_x = max(PLANET_RADII[next_planet_level], min(mouse_pos[0], SCREEN_WIDTH - PLANET_RADII[next_planet_level]))
                drop_y = TOP_AREA_HEIGHT 
                
                Planet(drop_x, drop_y, next_planet_level)
                drop_sound.play() 
                
                # 記錄時間與分數
                last_drop_time = current_time 
                if next_planet_level in DROP_SCORES:
                    score += DROP_SCORES[next_planet_level]
                
                # 更新最高分
                if score > high_score:
                    high_score = score
                    save_high_score(high_score)

                next_planet_level = random.randint(1, 4)

        # 2. 遊戲結束/勝利時的事件
        else:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if RESTART_BTN_RECT.collidepoint(event.pos):
                    reset_game()

    
    # [邏輯更新]
    if not game_over and not win_game:
        dt = 1.0 / 60.0
        space.step(dt)

        # 處理待刪除/新增清單
        for planet_obj in planets_to_remove:
            planet_obj.destroy()
        planets_to_remove.clear()
        
        for x, y, level in planets_to_add:
            Planet(x, y, level) 
        planets_to_add.clear()

        # [優化] 更新粒子
        for p in particles[:]:
            p.update()
            if p.life <= 0 or p.size <= 0:
                particles.remove(p)

        # 檢查失敗條件
        is_planet_dangerously_high = False
        for planet in planets:
            if planet.body.position.y < LOSE_LINE_Y:
                is_planet_dangerously_high = True
                break 

        if is_planet_dangerously_high:
            if lose_timer_start == 0:
                lose_timer_start = pygame