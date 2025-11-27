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

# 1. 音效低延遲優化
pygame.mixer.pre_init(44100, -16, 2, 512) 

SCALE = 0.75 

pygame.init()
pygame.mixer.init() 

SCREEN_WIDTH = int(800 * SCALE)
SCREEN_HEIGHT = int(960 * SCALE) 
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("合成大'星'瓜")

# --- 1. 全域變數與常數 ---
clock = pygame.time.Clock()
space = pymunk.Space()
space.gravity = (0, 981 * SCALE) 

# 遊戲狀態
game_running = True
score = 0
game_over = False
is_aiming = False 

# 音效開關狀態
sound_enabled = True 

# 勝利相關變數
has_won_once = False       
celebration_start_time = 0 
CELEBRATION_DURATION = 10000 

# 投擲冷卻
last_drop_time = 0
DROP_COOLDOWN = 600 

# 失敗計時器
lose_timer_start = 0      
LOSE_DURATION_MS = 5000   

# 區域尺寸
TOP_AREA_HEIGHT = int(200 * SCALE) 
GAME_AREA_HEIGHT = SCREEN_HEIGHT - TOP_AREA_HEIGHT
LOSE_LINE_Y = TOP_AREA_HEIGHT + int(20 * SCALE) 

# 音效按鈕區域
MUTE_BTN_SIZE = int(50 * SCALE)
MUTE_BTN_RECT = pygame.Rect(SCREEN_WIDTH - MUTE_BTN_SIZE - 20, 20, MUTE_BTN_SIZE, MUTE_BTN_SIZE)

# --- 2. 資源載入與處理 ---

try:
    drop_sound = pygame.mixer.Sound('DROP.wav') 
    merge_sound = pygame.mixer.Sound('COLLISION.wav')
except (pygame.error, FileNotFoundError) as e:
    print(f"警告：無法載入音效檔案。 {e}")
    class DummySound:
        def play(self): pass
    drop_sound = DummySound()
    merge_sound = DummySound()

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

# 星球半徑 (1~10級)
PLANET_RADII = [0] + [int((25 + (n + 1) * 10) * SCALE) for n in range(1, 11)]

# 得分表
DROP_SCORES = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500}
MERGE_SCORES = {
    2: 300, 3: 600, 4: 1000, 5: 1500, 
    6: 2100, 7: 2800, 8: 3600, 9: 4500, 
    10: 6000 
}

def crop_to_circle(image):
    rect = image.get_rect()
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255), rect.center, rect.width // 2)
    new_img = image.copy().convert_alpha()
    new_img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return new_img

PLANET_IMAGES = [None] 
for i in range(1, 11): 
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

PLANET_COLORS = [
    (0, 0, 0), (255, 255, 255), (220, 235, 255), (210, 255, 255), (210, 210, 220), 
    (220, 210, 255), (170, 200, 255), (190, 170, 255), (100, 150, 255), (150, 100, 255),
    (255, 215, 0) 
]

PLANET_COLLISION_TYPE = 1 
planets = [] 

# --- 3. 類別定義 ---

class Confetti:
    def __init__(self):
        self.x = random.randint(0, SCREEN_WIDTH)
        self.y = random.randint(-SCREEN_HEIGHT, 0)
        self.color = random.choice([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)])
        self.size = random.randint(5, 10) * SCALE
        self.speed_y = random.uniform(2, 6) * SCALE 
        self.speed_x = random.uniform(-1, 1) * SCALE 
        self.angle = random.randint(0, 360)
        self.spin_speed = random.uniform(-5, 5)

    def update(self):
        self.y += self.speed_y
        self.x += self.speed_x + math.sin(pygame.time.get_ticks() * 0.01) * 0.5
        self.angle += self.spin_speed
        
        if self.y > SCREEN_HEIGHT:
            self.y = random.randint(-100, -10)
            self.x = random.randint(0, SCREEN_WIDTH)

    def draw(self, surface):
        s = pygame.Surface((int(self.size), int(self.size)), pygame.SRCALPHA)
        s.fill(self.color)
        rotated_s = pygame.transform.rotate(s, self.angle)
        rect = rotated_s.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rotated_s, rect)

confetti_list = []

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
        
        # [修改] 圖片繪製邏輯：加入旋轉
        original_image = PLANET_IMAGES[self.level]
        
        if original_image:
            # 1. 取得 Pymunk 計算的旋轉角度 (弧度 -> 角度)
            # 負號是因為 Pygame 的旋轉方向與 Pymunk 相反
            angle_degrees = -math.degrees(self.body.angle)
            
            # 2. 旋轉圖片
            rotated_image = pygame.transform.rotate(original_image, angle_degrees)
            
            # 3. 重新計算中心點 (因為旋轉後圖片外框會變大，必須重新對齊中心)
            image_rect = rotated_image.get_rect(center=(x, y))
            
            # 4. 繪製
            screen.blit(rotated_image, image_rect)
        else:
            # 備用純色圓形
            color = PLANET_COLORS[self.level]
            pygame.draw.circle(screen, color, (x, y), int(self.radius))

# --- 4. 碰撞與物理邏輯 ---

planets_to_remove = []
planets_to_add = []

def handle_collision(arbiter, space, data):
    global score, has_won_once, celebration_start_time
    
    shape_a, shape_b = arbiter.shapes
    planet_a = shape_a.planet_object
    planet_b = shape_b.planet_object
    
    if planet_a.level == planet_b.level and planet_a.level < 10:
        if planet_a not in planets_to_remove and planet_b not in planets_to_remove:
            pos_a = planet_a.body.position
            pos_b = planet_b.body.position
            new_x = (pos_a.x + pos_b.x) / 2
            new_y = (pos_a.y + pos_b.y) / 2
            new_level = planet_a.level + 1
            
            planets_to_remove.append(planet_a)
            planets_to_remove.append(planet_b)
            planets_to_add.append((new_x, new_y, new_level))
            
            if sound_enabled:
                merge_sound.play()

            if new_level in MERGE_SCORES:
                score += MERGE_SCORES[new_level]
            else:
                score += new_level * 100
            
            if new_level == 10 and not has_won_once:
                has_won_once = True
                celebration_start_time = pygame.time.get_ticks() 
                for _ in range(150): 
                    confetti_list.append(Confetti())

    return True

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

font_name = "arial" 
if sys.platform.startswith("win"): font_name = "microsoftjhenghei" 
elif sys.platform.startswith("darwin"): font_name = "pingfangtc"
else: font_name = "wqy-microhei"

try:
    font = pygame.font.SysFont(font_name, int(60 * SCALE)) 
    font_large = pygame.font.SysFont(font_name, int(100 * SCALE))
    font_small = pygame.font.SysFont(font_name, int(40 * SCALE)) 
except:
    font = pygame.font.SysFont(None, int(60 * SCALE))
    font_large = pygame.font.SysFont(None, int(100 * SCALE))
    font_small = pygame.font.SysFont(None, int(40 * SCALE))

def draw_text(text, font_to_use, color, x, y):
    text_surface = font_to_use.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    screen.blit(text_surface, text_rect)

def draw_sound_button(surface, rect, is_on):
    bg_color = (60, 60, 80) if is_on else (80, 40, 40)
    pygame.draw.rect(surface, bg_color, rect, border_radius=10)
    pygame.draw.rect(surface, (200, 200, 255), rect, 2, border_radius=10)

    cx, cy = rect.centerx, rect.centery
    speaker_color = (255, 255, 255)
    points = [
        (cx - 5, cy - 5),
        (cx - 5, cy + 5),
        (cx + 5, cy + 10),
        (cx + 5, cy - 10)
    ]
    pygame.draw.polygon(surface, speaker_color, points)
    
    if is_on:
        pygame.draw.line(surface, speaker_color, (cx + 8, cy - 3), (cx + 8, cy + 3), 2)
        pygame.draw.line(surface, speaker_color, (cx + 12, cy - 6), (cx + 12, cy + 6), 2)
    else:
        pygame.draw.line(surface, (255, 100, 100), (cx + 8, cy - 5), (cx + 14, cy + 5), 3)
        pygame.draw.line(surface, (255, 100, 100), (cx + 14, cy - 5), (cx + 8, cy + 5), 3)


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

BTN_W, BTN_H = int(300 * SCALE), int(100 * SCALE)
BTN_X = (SCREEN_WIDTH - BTN_W) // 2
BTN_Y = (SCREEN_HEIGHT - BTN_H) // 2 + int(100 * SCALE)
RESTART_BTN_RECT = pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H)

def reset_game():
    global score, game_over, lose_timer_start, next_planet_level, planets, confetti_list, has_won_once
    for p in planets[:]: 
        p.destroy()
    planets.clear() 
    confetti_list.clear() 
    score = 0
    game_over = False
    has_won_once = False 
    lose_timer_start = 0
    next_planet_level = random.randint(1, 4)

# --- 6. 開始畫面 ---
def game_start_screen():
    global sound_enabled 
    intro = True
    btn_rect = RESTART_BTN_RECT.copy() 
    
    while intro:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_rect.collidepoint(event.pos):
                    intro = False 
                if MUTE_BTN_RECT.collidepoint(event.pos):
                    sound_enabled = not sound_enabled

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
        
        draw_sound_button(screen, MUTE_BTN_RECT, sound_enabled)

        pygame.display.flip()

game_start_screen()

# --- 7. 遊戲主迴圈 ---

while game_running:
    
    current_time = pygame.time.get_ticks()
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game_running = False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if MUTE_BTN_RECT.collidepoint(event.pos):
                sound_enabled = not sound_enabled

        if not game_over:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if not MUTE_BTN_RECT.collidepoint(event.pos):
                    if current_time - last_drop_time > DROP_COOLDOWN:
                        is_aiming = True

            if event.type == pygame.MOUSEBUTTONUP and is_aiming:
                is_aiming = False
                drop_x = max(PLANET_RADII[next_planet_level], min(mouse_pos[0], SCREEN_WIDTH - PLANET_RADII[next_planet_level]))
                drop_y = TOP_AREA_HEIGHT 
                
                Planet(drop_x, drop_y, next_planet_level)
                
                if sound_enabled:
                    drop_sound.play() 
                
                last_drop_time = current_time 
                if next_planet_level in DROP_SCORES:
                    score += DROP_SCORES[next_planet_level]
                
                next_planet_level = random.randint(1, 4)

        else:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if RESTART_BTN_RECT.collidepoint(event.pos):
                    reset_game()

    if not game_over:
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

    if has_won_once:
        time_since_win = current_time - celebration_start_time
        if time_since_win < CELEBRATION_DURATION:
            is_celebrating = True
            if len(confetti_list) < 150: 
                 confetti_list.append(Confetti())
            for c in confetti_list:
                c.update()
        else:
            confetti_list.clear()
            is_celebrating = False
    else:
        is_celebrating = False

    if background_image:
        screen.blit(background_image, (0, 0))
    else:
        screen.fill((20, 25, 40)) 
    
    pygame.draw.rect(screen, (30, 35, 60), (0, 0, SCREEN_WIDTH, TOP_AREA_HEIGHT)) 

    line_color = (0, 255, 255) 
    if lose_timer_start > 0 and (current_time - lose_timer_start > 1000):
        if (current_time // 250) % 2 == 0:
            line_color = (255, 50, 50) 
        else:
            line_color = (150, 0, 0)   

    DASH_LENGTH = int(20 * SCALE)  
    GAP_LENGTH = int(10 * SCALE)   
    LINE_THICKNESS = int(5 * SCALE) 

    current_x = 0
    while current_x < SCREEN_WIDTH:
        start_point = (current_x, LOSE_LINE_Y)
        end_point = (min(current_x + DASH_LENGTH, SCREEN_WIDTH), LOSE_LINE_Y)
        pygame.draw.line(screen, line_color, start_point, end_point, LINE_THICKNESS)
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
        
    if not game_over:
        if current_time - last_drop_time < DROP_COOLDOWN:
            pass 
        draw_next_planet_indicator(mouse_pos[0]) 

    draw_text(f"Score: {score}", font, (255, 255, 255), SCREEN_WIDTH / 2, int(60 * SCALE))
    
    draw_sound_button(screen, MUTE_BTN_RECT, sound_enabled)

    if is_celebrating:
        for c in confetti_list:
            c.draw(screen)
        draw_text("YOU WIN!!", font_large, (255, 215, 0), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - int(80 * SCALE))
        draw_text("繼續挑戰高分!", font_small, (200, 255, 255), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)

    if game_over:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        title = "GAME OVER"
        title_color = (255, 50, 50)
        
        draw_text(title, font_large, title_color, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - int(80 * SCALE))
        draw_text(f"最終得分: {score}", font, (255, 255, 255), SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)

        is_hover = RESTART_BTN_RECT.collidepoint(mouse_pos)
        draw_cosmic_button(screen, RESTART_BTN_RECT, "Try Again", font, is_hover)
        
    pygame.display.flip()
    
    clock.tick(60) 

pygame.quit()
sys.exit()