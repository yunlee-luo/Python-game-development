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
pygame.display.set_caption("合成大'星'瓜 (自動圓形去背版)")

# (修改) <--- 自動生成星空背景的函式 --->
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


# 遊戲時鐘
clock = pygame.time.Clock()

# Pymunk 物理空間
space = pymunk.Space()
space.gravity = (0, 981 * SCALE) 

# 遊戲狀態
game_running = True
score = 0
game_over = False
win_game = False
is_aiming = False 

# "YOU LOSE" 計時器
lose_timer_start = 0      
LOSE_DURATION_MS = 5000   

TOP_AREA_HEIGHT = int(200 * SCALE) 
GAME_AREA_HEIGHT = SCREEN_HEIGHT - TOP_AREA_HEIGHT
LOSE_LINE_Y = TOP_AREA_HEIGHT + int(20 * SCALE) 

# --- 2. 遊戲資源 (載入星球圖片與音效) ---

try:
    drop_sound = pygame.mixer.Sound('DROP.wav') 
    merge_sound = pygame.mixer.Sound('COLLISION.wav')
except (pygame.error, FileNotFoundError) as e:
    print(f"警告：無法載入音效檔案。 {e}")
    class DummySound:
        def play(self): pass
    drop_sound = DummySound()
    merge_sound = DummySound()

# 半徑設定：只生成 1~9 級的半徑
PLANET_RADII = [0] + [int((25 + (n + 1) * 10) * SCALE) for n in range(1, 10)]

# (新增) <--- 自動將圖片切割成圓形的函式 --->
def crop_to_circle(image):
    """將傳入的 Surface 切割成圓形並去背"""
    # 1. 取得圖片尺寸
    rect = image.get_rect()
    # 2. 建立一個新的透明畫布 (遮罩)
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    # 3. 在遮罩上畫一個實心白圓
    pygame.draw.circle(mask, (255, 255, 255), rect.center, rect.width // 2)
    # 4. 複製原圖並確保有 Alpha 通道
    new_img = image.copy().convert_alpha()
    # 5. 將原圖與遮罩進行 "最小透明度混合" (BLEND_RGBA_MIN)
    # 原理：遮罩外圍透明度是 0，原圖外圍就會變 0 (透明)；遮罩中間是 255，原圖中間保留
    new_img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return new_img
# (新增) <--- 函式結束 --->


# 圖片載入
PLANET_IMAGES = [None] 
for i in range(1, 10): 
    try:
        img_path = os.path.join('assets', f'planet_{i}.png') 
        
        # 1. 載入原始圖片
        original_image = pygame.image.load(img_path).convert_alpha() 
        
        # 2. 先縮放到目標大小 (直徑)
        target_size = (PLANET_RADII[i]*2, PLANET_RADII[i]*2)
        scaled_image = pygame.transform.scale(original_image, target_size)
        
        # 3. (修改) 呼叫上面的函式進行圓形切割!
        final_image = crop_to_circle(scaled_image)
        
        PLANET_IMAGES.append(final_image)
        print(f"成功載入並切割星球: {img_path}")
        
    except FileNotFoundError:
        print(f"警告: 找不到圖片檔 {img_path}，將使用純色圓形替代。")
        PLANET_IMAGES.append(None)
    except Exception as e:
        print(f"警告: 載入圖片 {img_path} 發生錯誤: {e}，將使用純色圓形替代。")
        PLANET_IMAGES.append(None)

# 備用顏色
PLANET_COLORS = [
    (0, 0, 0), (255, 255, 255), (220, 235, 255), (210, 255, 255), (210, 210, 220), 
    (220, 210, 255), (170, 200, 255), (190, 170, 255), (100, 150, 255), (150, 100, 255)
]

PLANET_COLLISION_TYPE = 1 
planets = [] 

# --- 3. Planet Class (星球類別) ---
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


# --- 4. Pymunk 碰撞處理 ---
planets_to_remove = []
planets_to_add = []

def handle_collision(arbiter, space, data):
    global score, win_game
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
            score += new_level * 10
            
            if new_level == 9:
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
space.on_collision(PLANET_COLLISION_TYPE, PLANET_COLLISION_TYPE, post_solve=handle_collision)


# --- 6. 遊戲準備區 ---
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


# --- 7. 繪製文字函式 ---
font = pygame.font.SysFont("simhei", int(60 * SCALE)) 
font_large = pygame.font.SysFont("simhei", int(100 * SCALE))

def draw_text(text, font_to_use, color, x, y):
    text_surface = font_to_use.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    screen.blit(text_surface, text_rect)


# --- 8. 遊戲主迴圈 ---

while game_running:
    
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_running = False
        
        if event.type == pygame.MOUSEBUTTONDOWN and not game_over and not win_game:
            is_aiming = True

        if event.type == pygame.MOUSEBUTTONUP and is_aiming:
            is_aiming = False
            
            drop_x = max(PLANET_RADII[next_planet_level], min(mouse_pos[0], SCREEN_WIDTH - PLANET_RADII[next_planet_level]))
            drop_y = TOP_AREA_HEIGHT 
            
            Planet(drop_x, drop_y, next_planet_level)
            drop_sound.play() 

            next_planet_level = random.randint(1, 4)

    
    if not game_over and not win_game:
        dt = 1.0 / 60.0
        space.step(dt)

        for planet_obj in planets_to_remove:
            planet_obj.destroy()
        planets_to_remove.clear()
        
        for x, y, level in planets_to_add:
            Planet(x, y, level) 
        planets_to_add.clear()

        is_planet_dangerously_high = False
        for planet in planets:
            if planet.body.position.y < LOSE_LINE_Y:
                is_planet_dangerously_high = True
                break 

        if is_planet_dangerously_high:
            if lose_timer_start == 0:
                lose_timer_start = pygame.time.get_ticks()
            else:
                elapsed_time = pygame.time.get_ticks() - lose_timer_start
                if elapsed_time > LOSE_DURATION_MS:
                    game_over = True
        else:
            lose_timer_start = 0

    # 繪製背景
    if background_image:
        screen.blit(background_image, (0, 0))
    else:
        screen.fill((20, 25, 40)) 
    
    pygame.draw.rect(screen, (30, 35, 60), (0, 0, SCREEN_WIDTH, TOP_AREA_HEIGHT)) 

    DASH_LENGTH = int(20 * SCALE)  
    GAP_LENGTH = int(10 * SCALE)   
    LINE_THICKNESS = int(5 * SCALE) 

    current_x = 0
    while current_x < SCREEN_WIDTH:
        start_point = (current_x, LOSE_LINE_Y)
        end_point = (min(current_x + DASH_LENGTH, SCREEN_WIDTH), LOSE_LINE_Y)
        pygame.draw.line(screen, (0, 255, 255), start_point, end_point, LINE_THICKNESS)
        current_x += (DASH_LENGTH + GAP_LENGTH)
    
    if is_aiming:
        aim_x = max(PLANET_RADII[next_planet_level], min(mouse_pos[0], SCREEN_WIDTH - PLANET_RADII[next_planet_level]))
        
        AIM_DASH_LENGTH = int(15 * SCALE)
        AIM_GAP_LENGTH = int(10 * SCALE)
        AIM_LINE_THICKNESS = int(2 * SCALE)
        AIM_LINE_COLOR = (100, 100, 150) 
        
        current_y = LOSE_LINE_Y
        while current_y < SCREEN_HEIGHT:
            start_point = (aim_x, current_y)
            end_point = (aim_x, min(current_y + AIM_DASH_LENGTH, SCREEN_HEIGHT))
            pygame.draw.line(screen, AIM_LINE_COLOR, start_point, end_point, AIM_LINE_THICKNESS)
            current_y += (AIM_DASH_LENGTH + AIM_GAP_LENGTH)

    for planet in planets:
        planet.draw()
        
    if not game_over and not win_game:
        draw_next_planet_indicator(mouse_pos[0]) 
        
    draw_text(f"Score: {score}", font, (255, 255, 255), SCREEN_WIDTH / 2, TOP_AREA_HEIGHT + int(50 * SCALE))
    
    if game_over:
        draw_text("YOU LOSE!!", font_large, (255, 50, 50), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
    if win_game:
        draw_text("YOU WIN!!", font_large, (255, 255, 0), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        
    pygame.display.flip()
    
    clock.tick(60) 


pygame.quit()
sys.exit()