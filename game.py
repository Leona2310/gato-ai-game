import os
import sys
import pygame
import random
import math
import cv2
import mediapipe as mp
import time

pygame.init()
W, H = 1280, 720
screen = pygame.display.set_mode((W, H))
clock = pygame.time.Clock()
pygame.display.set_caption("GATO")

# ------------------ Mediapipe Setup ------------------
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
cap = cv2.VideoCapture(1)

# ------------------ Colors ------------------
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 150, 255)
WHITE = (255, 255, 255)
BUTTON_COLOR = (200, 50, 50)
BUTTON_HOVER = (255, 0, 0)

# ------------------ Game Variables ------------------
max_hp = 100
current_hp = 100
GESTURE = "Unknown"
GESTURE_COOLDOWN = 0.3
last_gesture_time = 0
round_num = 1
total_rounds = 3
enemies_per_round = 10
spawn_interval = 1200  # milliseconds
enemies_spawned = 0
round_started = False
round_countdown = 3
countdown_start_time = 0
qualification = 5
destroyed_this_round = 0
game_started = False
show_round_intro = True
round_intro_time = 0
show_game_start = True
game_over = False
game_over_message = ""
score = 0
exit_after_time = 3
game_music_started = False

# Delay before showing GAME OVER after HP hits 0 (so sad cat is visible)
game_over_delay = 2.0
game_over_delay_start = None

# ------------------ Load Assets ------------------
cat_neutral = pygame.image.load("cat_neutral.png").convert_alpha()
cat_happy = pygame.image.load("cat_happy.png").convert_alpha()
cat_sad = pygame.image.load("cat_sad.png").convert_alpha()
cat_neutral = pygame.transform.scale(cat_neutral, (300, 300))
cat_happy = pygame.transform.scale(cat_happy, (300, 300))
cat_sad = pygame.transform.scale(cat_sad, (300, 300))
cat_x, cat_y = 100, H // 2 - 100
bg_image = pygame.image.load("magic_forest.png").convert()
bg_image = pygame.transform.scale(bg_image, (W, H))

# ------------------ Sound ------------------
try:
    pygame.mixer.init()
    destroy_sound = pygame.mixer.Sound("shatter.wav")
    damage_sound = pygame.mixer.Sound("hit.wav")
    beep_sound = pygame.mixer.Sound("beep.wav")
    pygame.mixer.music.load("background_music.mp3")
    pygame.mixer.music.set_volume(0.5)
except Exception as e:
    # If audio fails to initialize, just move on (prevents crashes on headless machines)
    print("Audio init failed:", e)
    destroy_sound = None
    damage_sound = None
    beep_sound = None

# ------------------ Animation Lists ------------------
gesture_animations = []
destroy_animations = []
enemies = []

# ------------------ Classes ------------------
class GestureAnimation:
    def __init__(self, gesture):
        self.gesture = gesture
        self.x, self.y = W // 2, H // 2
        self.alpha = 255
        self.scale = 1.0
        self.active = True

    def update(self):
        self.scale += 0.05
        self.alpha -= 10
        if self.alpha <= 0:
            self.active = False

    def draw(self, surface):
        safe_alpha = max(0, min(255, self.alpha))
        if self.gesture == "Square":
            color = (0, 150, 255)
            size = int(100 * self.scale)
            rect = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.rect(rect, (*color, safe_alpha), (0, 0, size, size), 10)
            surface.blit(rect, (self.x - size // 2, self.y - size // 2))
        elif self.gesture == "Circle":
            color = (255, 100, 100)
            size = int(100 * self.scale)
            circle = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle, (*color, safe_alpha), (size, size), size, 10)
            surface.blit(circle, (self.x - size, self.y - size))
        elif self.gesture == "Line":
            color = (100, 255, 100)
            length = int(150 * self.scale)
            line = pygame.Surface((length, 10), pygame.SRCALPHA)
            pygame.draw.rect(line, (*color, safe_alpha), (0, 0, length, 10))
            surface.blit(line, (self.x - length // 2, self.y - 5))
        elif self.gesture == "Triangle":
            color = (255, 200, 0)
            size = int(100 * self.scale)
            triangle = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            points = [(size, 0), (0, size * 2), (size * 2, size * 2)]
            pygame.draw.polygon(triangle, (*color, safe_alpha), points, 10)
            surface.blit(triangle, (self.x - size, self.y - size))

class DestroyAnimation:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 10
        self.max_radius = 80
        self.active = True
        self.alpha = 255
        self.particles = [(random.randint(-20, 20), random.randint(-20, 20)) for _ in range(10)]

    def update(self):
        if self.radius < self.max_radius:
            self.radius += 8
            self.alpha -= 15
            if self.alpha < 0:
                self.alpha = 0
        else:
            self.active = False

    def draw(self, surface):
        if self.active:
            # draw particle lines on an alpha surface so transparency is respected
            effect_surface = pygame.Surface((self.radius * 2 + 40, self.radius * 2 + 40), pygame.SRCALPHA)
            for px, py in self.particles:
                pygame.draw.line(effect_surface, (255, 255, 0, max(0, int(self.alpha))), 
                                 (self.radius + 20, self.radius + 20), (self.radius + 20 + px, self.radius + 20 + py), 3)
            pygame.draw.circle(effect_surface, (255, 255, 0, max(0, int(self.alpha))), 
                               (self.radius + 20, self.radius + 20), int(self.radius), 2)
            surface.blit(effect_surface, (self.x - self.radius - 20, self.y - self.radius - 20))

class Enemy:
    def __init__(self):
        self.x = W + random.randint(0, 200)
        self.y = random.randint(100, H - 150)
        self.speed = random.uniform(4.0, 7.0) + round_num * 0.5
        self.type = random.choice(["Circle", "Square", "Triangle"])
        self.rune = random.choice(["Circle", "Line", "Triangle", "Square"])
        self.attacking = False
        self.attack_speed = 12.0

    def update(self):
        if not self.attacking:
            self.x -= self.speed
            if abs(self.x - cat_x) < 250:
                self.attacking = True
        else:
            dx = cat_x - self.x
            dy = cat_y - self.y
            distance = math.hypot(dx, dy)
            if distance != 0:
                self.x += (dx / distance) * self.attack_speed
                self.y += (dy / distance) * self.attack_speed

    def draw(self):
        draw_enemy_with_rune(screen, self.type, int(self.x), int(self.y), self.rune)

    def has_reached_cat(self):
        distance = math.hypot(cat_x - self.x, cat_y - self.y)
        return distance < 80

# ------------------ Functions ------------------
def draw_enemy_with_rune(surface, etype, x, y, rune):
    enemy_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
    if etype == "Circle":
        pygame.draw.circle(enemy_surf, BLACK, (50, 50), 50)
    elif etype == "Square":
        pygame.draw.rect(enemy_surf, BLACK, (0, 0, 100, 100))
    elif etype == "Triangle":
        pts = [(50, 0), (0, 100), (100, 100)]
        pygame.draw.polygon(enemy_surf, BLACK, pts)
    surface.blit(enemy_surf, (x, y))
    center_x, center_y = x + 50, y + 50
    if rune == "Circle":
        pygame.draw.circle(surface, BLUE, (center_x, center_y), 30, 5)
    elif rune == "Line":
        pygame.draw.line(surface, BLUE, (center_x - 40, center_y), (center_x + 40, center_y), 5)
    elif rune == "Triangle":
        pts = [(center_x, center_y - 30), (center_x - 30, center_y + 30), (center_x + 30, center_y + 30)]
        pygame.draw.polygon(surface, BLUE, pts, 5)
    elif rune == "Square":
        pygame.draw.rect(surface, BLUE, (center_x - 30, center_y - 30, 60, 60), 5)

def draw_hp_bar(surface, x, y, hp, max_hp):
    bar_width = 100
    bar_height = 10
    fill = (hp / max_hp) * bar_width
    pygame.draw.rect(surface, RED, (x, y - 20, bar_width, bar_height), border_radius=5)
    pygame.draw.rect(surface, GREEN, (x, y - 20, fill, bar_height), border_radius=5)
    pygame.draw.rect(surface, BLACK, (x, y - 20, bar_width, bar_height), width=2, border_radius=5)

def fingers_open(hand, handedness):
    tips = [4, 8, 12, 16, 20]
    fingers = []
    # thumb check depends on left/right hand orientation
    if handedness == "Left":
        fingers.append(1 if hand.landmark[tips[0]].x > hand.landmark[3].x else 0)
    else:
        fingers.append(1 if hand.landmark[tips[0]].x < hand.landmark[3].x else 0)
    for i in range(1, 5):
        fingers.append(1 if hand.landmark[tips[i]].y < hand.landmark[tips[i] - 2].y else 0)
    return fingers

def detect_hand_gesture():
    ret, frame = cap.read()
    if not ret:
        return "Unknown"
    frame = cv2.flip(frame, 1)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)
    if not results.multi_hand_landmarks:
        return "Unknown"

    hand_gestures = []
    for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
        f = fingers_open(hand_landmarks, handedness.classification[0].label)
        total = sum(f)
        if total == 0:
            hand_gestures.append("Circle")
        elif total == 5:
            hand_gestures.append("Square")
        elif f[1] and f[2] and total == 2:
            hand_gestures.append("Triangle")
        else:
            hand_gestures.append("Line")

    if len(hand_gestures) == 2:
        return hand_gestures[0] if hand_gestures[0] == hand_gestures[1] else "Line"
    elif len(hand_gestures) == 1:
        return hand_gestures[0]
    return "Unknown"

# ------------------ Tutorial & Messages ------------------
def show_message_centered(text, subtext=""):
    font_big = pygame.font.SysFont(None, 100)
    font_small = pygame.font.SysFont(None, 50)
    screen.fill(WHITE)
    text_surf = font_big.render(text, True, RED)
    screen.blit(text_surf, (W//2 - text_surf.get_width()//2, H//2 - 100))
    if subtext:
        sub_surf = font_small.render(subtext, True, BLACK)
        screen.blit(sub_surf, (W//2 - sub_surf.get_width()//2, H//2))
    pygame.display.flip()

def draw_exit_button():
    mouse = pygame.mouse.get_pos()
    click = pygame.mouse.get_pressed()
    button_rect = pygame.Rect(W - 150, H - 70, 120, 50)
    color = BUTTON_HOVER if button_rect.collidepoint(mouse) else BUTTON_COLOR
    pygame.draw.rect(screen, color, button_rect)
    font = pygame.font.SysFont(None, 40)
    text = font.render("EXIT", True, WHITE)
    screen.blit(text, (W - 150 + 30, H - 70 + 10))
    if button_rect.collidepoint(mouse) and click[0] == 1:
        cap.release()
        pygame.quit()
        sys.exit()

def show_tutorial():
    global game_started, countdown_start_time, show_game_start
    tutorial = True
    font_big = pygame.font.SysFont(None, 50)
    font_small = pygame.font.SysFont(None, 35)
    while tutorial:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                cap.release()
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                tutorial = False
                game_started = True
                show_game_start = True
                countdown_start_time = time.time()

        screen.fill(WHITE)
        texts = [
            "TWO-HAND GESTURES:",
            "Square: Both hands open",
            "Circle: Both hands closed (fists)",
            "Triangle: Both peace signs",
            "Line: One hand open, one closed",
            "Press SPACE to Start!"
        ]
        for idx, text in enumerate(texts):
            rendered = font_big.render(text, True, BLACK) if idx == 0 else font_small.render(text, True, BLACK)
            screen.blit(rendered, (W // 2 - rendered.get_width() // 2, 100 + idx * 70))
        pygame.display.flip()
        clock.tick(60)

show_tutorial()

# ------------------ Main Game Loop ------------------
SPAWN = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWN, spawn_interval)
last_count_value = None
game_over_start_time = None

while True:
    screen.blit(bg_image, (0, 0))
    draw_exit_button()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            cap.release()
            pygame.quit()
            sys.exit()
        if event.type == SPAWN and round_started:
            enemies.append(Enemy())
            enemies_spawned += 1

    # If we've entered the timed "delay before game over" state, check it here
    if game_over_delay_start is not None and not game_over:
        # show sad cat until delay passes, then flip to game over
        if time.time() - game_over_delay_start >= game_over_delay:
            game_over = True
            game_over_delay_start = None

    # Game Over Screen
    if game_over:
        # show the GAME OVER message screen
        show_message_centered("GAME OVER", f"{game_over_message} | Score: {score}")
        if game_over_start_time is None:
            game_over_start_time = time.time()
        elif time.time() - game_over_start_time > exit_after_time:
            cap.release()
            pygame.quit()
            sys.exit()
        pygame.display.flip()
        continue

    # Start Message
    if show_game_start:
        show_message_centered("Game Starts!", "Get Ready...")
        if time.time() - countdown_start_time > 2:
            show_game_start = False
            show_round_intro = True
            round_intro_time = time.time()
        continue

    # Round Intro
    if show_round_intro:
        show_message_centered(f"Round {round_num}", "Prepare yourself...")
        if time.time() - round_intro_time > 2:
            show_round_intro = False
            countdown_start_time = time.time()
        continue

    # Round Countdown
    if game_started and not round_started:
        elapsed = time.time() - countdown_start_time
        count = max(0, round_countdown - int(elapsed))
        font = pygame.font.SysFont(None, 150)
        countdown_text = font.render(str(count), True, RED)
        screen.blit(countdown_text, (W // 2 - 50, H // 2 - 75))
        if count != last_count_value and count > 0:
            if beep_sound:
                beep_sound.play()
            last_count_value = count
        if elapsed >= round_countdown:
            round_started = True
            enemies_spawned = 0
            destroyed_this_round = 0
            last_count_value = None
            pygame.time.set_timer(SPAWN, spawn_interval)
            if not game_music_started:
                try:
                    pygame.mixer.music.play(-1)
                except:
                    pass
                game_music_started = True

    # ---------------- Game Logic ----------------
    if round_started:
        current_time = time.time()
        if current_time - last_gesture_time > GESTURE_COOLDOWN:
            gesture = detect_hand_gesture()
            if gesture != "Unknown":
                GESTURE = gesture
                last_gesture_time = current_time
                gesture_animations.append(GestureAnimation(gesture))
                matched_any = False
                for e in enemies[:]:
                    if e.rune == GESTURE:
                        destroy_animations.append(DestroyAnimation(e.x + 50, e.y + 50))
                        try:
                            enemies.remove(e)
                        except ValueError:
                            pass
                        matched_any = True
                        destroyed_this_round += 1
                        score += 10
                if matched_any and destroy_sound:
                    destroy_sound.play()

        for e in enemies[:]:
            e.update()
            e.draw()
            if e.has_reached_cat():
                try:
                    enemies.remove(e)
                except ValueError:
                    pass
                current_hp -= 10
                if current_hp < 0:
                    current_hp = 0
                if damage_sound:
                    damage_sound.play()
                # If hp has dropped to 0, start the delay timer (show sad cat for a bit)
                if current_hp == 0 and not game_over and game_over_delay_start is None:
                    game_over_delay_start = time.time()
                    game_over_message = "Your cat ran out of health! Keep training!"

        # Draw Cat (happy / neutral / sad)
        # Sad is shown when HP is <= 20% of max_hp
        if current_hp > max_hp * 0.5:
            screen.blit(cat_happy, (cat_x, cat_y))
        elif current_hp > max_hp * 0.2:
            screen.blit(cat_neutral, (cat_x, cat_y))
        else:
            # includes current_hp == 0
            screen.blit(cat_sad, (cat_x, cat_y))

        # Animations
        for anim in destroy_animations[:]:
            anim.update()
            anim.draw(screen)
            if not anim.active:
                destroy_animations.remove(anim)
        for ga in gesture_animations[:]:
            ga.update()
            ga.draw(screen)
            if not ga.active:
                gesture_animations.remove(ga)

        draw_hp_bar(screen, cat_x, cat_y, current_hp, max_hp)
        font = pygame.font.SysFont(None, 60)
        gesture_text = font.render(f"Gesture: {GESTURE}", True, BLACK)
        screen.blit(gesture_text, (W // 2 - 150, 50))
        round_font = pygame.font.SysFont(None, 50)
        round_text = round_font.render(f"Round {round_num}", True, RED)
        screen.blit(round_text, (W - 200, 20))

        # Round Completion
        if enemies_spawned >= enemies_per_round and not enemies:
            round_started = False
            game_started = True
            countdown_start_time = time.time()
            # Evaluate whether player qualified to move on
            if destroyed_this_round >= qualification:
                if round_num >= total_rounds:
                    # Player won — show victory and then game over screen
                    game_over = True
                    game_over_message = "Victory! You completed all rounds!"
                else:
                    round_num += 1
                    enemies_per_round += 5
                    spawn_interval = max(500, spawn_interval - 100)
                    pygame.time.set_timer(SPAWN, spawn_interval)
            else:
                game_over = True
                game_over_message = f"You failed to destroy enough enemies! Destroyed: {destroyed_this_round}, Required: {qualification}"

    pygame.display.flip()
    clock.tick(60)
