#!/usr/bin/env python3
"""
PongAI (AI vs AI / Human)
Refactor of the original CSC180 tournament harness.

Mission / Match format (always):
- A match is exactly **two games**.
- `-s/--score` is the **TOTAL match target points**. We split them across the two games:
  - Game 1 plays to `floor(s/2)`.
  - Game 2 (after switching sides) plays to `ceil(s/2)`.
- The final report shows both game boxes (with correct side labels at the time of play)
  and a **controller-vs-controller** summary aggregated across both games.

Key features:
- Python 3.8+ compatible, Pygame 2.x
- Headless mode runs at max speed (no frame cap)
- Clear scoreboxes with actual controllers (e.g., `studentAI.pong_ai`)
- CLI:
    - `-l/--left`   : module name with `pong_ai()` or `human`
    - `-r/--right`  : module name with `pong_ai()` or `human`
    - `-s/--score`  : **TOTAL match points** (split across two games)
    - `--headless`  : run without display (max speed)
    - `--timeout`   : seconds per AI move (0 disables; default 0.0003)
    - `--seed`      : RNG seed for reproducibility
    - `--clock`     : FPS when displayed (default 80)

AI contract:
    def pong_ai(my_frect, other_frect, ball_frect, table_size) -> "up" | "down" | None

Defaults:
- If only `-l` or `-r` is provided, the other side becomes `human`.
- If neither is provided, tries `chaser_ai` vs `chaser_ai`; else `human` vs `human`.
"""

import argparse
import importlib
import math
import os
import random
import sys
from typing import Callable, Optional, Dict

import pygame
from pygame.locals import K_ESCAPE, K_q, KEYDOWN, QUIT, Rect

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
clock = pygame.time.Clock()

# -------------------- Floating rect -----------------------

class fRect:
    """Like Pygame's Rect, but with floating-point coordinates."""
    def __init__(self, pos, size):
        self.pos = (float(pos[0]), float(pos[1]))
        self.size = (float(size[0]), float(size[1]))

    def move_ip(self, x, y, move_factor: float = 1.0):
        self.pos = (self.pos[0] + x*move_factor, self.pos[1] + y*move_factor)

    def get_rect(self) -> Rect:
        return Rect(int(self.pos[0]), int(self.pos[1]), int(self.size[0]), int(self.size[1]))

    def copy(self):
        return fRect(self.pos, self.size)

    def intersect(self, other_frect) -> bool:
        # Two rectangles intersect iff both x and y projections intersect
        for i in range(2):
            if self.pos[i] < other_frect.pos[i]:
                if other_frect.pos[i] >= self.pos[i] + self.size[i]:
                    return False
            elif self.pos[i] > other_frect.pos[i]:
                if self.pos[i] >= other_frect.pos[i] + other_frect.size[i]:
                    return False
        return True

# -------------------- Paddle ------------------------------

class Paddle:
    def __init__(self, pos, size, speed, max_angle, facing, timeout):
        self.frect = fRect((pos[0]-size[0]/2, pos[1]-size[1]/2), size)
        self.speed = float(speed)
        self.size = size
        self.facing = facing  # 1 = left paddle (faces right), 0 = right paddle (faces left)
        self.max_angle = float(max_angle)
        self.timeout = float(timeout)
        self.move_getter: Callable = None  # set in main
        self.label: str = "UNSET"

    def move(self, enemy_frect, ball_frect, table_size):
        # Use timeout-limited call when timeout > 0, else direct call (debug)
        if self.timeout and self.timeout > 0:
            direction = timeout(self.move_getter,
                                (self.frect.copy(), enemy_frect.copy(), ball_frect.copy(), tuple(table_size)),
                                {}, self.timeout, default=None)
        else:
            direction = self.move_getter(self.frect.copy(), enemy_frect.copy(), ball_frect.copy(), tuple(table_size))

        if direction == "up":
            self.frect.move_ip(0, -self.speed)
        elif direction == "down":
            self.frect.move_ip(0, self.speed)

        # Clamp to table
        to_bottom = (self.frect.pos[1] + self.frect.size[1]) - table_size[1]
        if to_bottom > 0:
            self.frect.move_ip(0, -to_bottom)
        to_top = self.frect.pos[1]
        if to_top < 0:
            self.frect.move_ip(0, -to_top)

    def get_angle(self, y):
        center = self.frect.pos[1] + self.size[1]/2
        rel = (y - center) / self.size[1]
        rel = max(-0.5, min(0.5, rel))
        sign = 1 - 2*self.facing  # right paddle (+), left paddle (-)
        return sign * rel * self.max_angle * math.pi/180.0

# -------------------- Ball --------------------------------

class Ball:
    def __init__(self, table_size, size, paddle_bounce, wall_bounce, dust_error, init_speed_mag):
        rand_ang = (.4 + .4*random.random())*math.pi*(1 - 2*(random.random() > .5)) + .5*math.pi
        speed = (init_speed_mag*math.cos(rand_ang), init_speed_mag*math.sin(rand_ang))
        pos = (table_size[0]/2, table_size[1]/2)
        self.frect = fRect((pos[0]-size[0]/2, pos[1]-size[1]/2), size)
        self.speed = (float(speed[0]), float(speed[1]))
        self.size = size
        self.paddle_bounce = float(paddle_bounce)
        self.wall_bounce = float(wall_bounce)
        self.dust_error = float(dust_error)
        self.init_speed_mag = float(init_speed_mag)
        self.prev_bounce: Optional[Paddle] = None

    def get_center(self):
        return (self.frect.pos[0] + .5*self.frect.size[0], self.frect.pos[1] + .5*self.frect.size[1])

    def get_speed_mag(self):
        return math.hypot(self.speed[0], self.speed[1])

    def move(self, paddles, table_size, move_factor):
        moved = False
        walls_rects = [Rect(-100, -100, table_size[0]+200, 100),           # top
                       Rect(-100, table_size[1], table_size[0]+200, 100)]  # bottom

        # Wall collisions
        for wall_rect in walls_rects:
            if self.frect.get_rect().colliderect(wall_rect):
                c = 0
                while self.frect.get_rect().colliderect(wall_rect):
                    self.frect.move_ip(-.1*self.speed[0], -.1*self.speed[1], move_factor)
                    c += 1
                r1 = 0 if self.wall_bounce == 0 else (1 + 2*(random.random()-.5)*self.dust_error)
                r2 = 0 if self.wall_bounce == 0 else (1 + 2*(random.random()-.5)*self.dust_error)
                self.speed = (self.wall_bounce*self.speed[0]*r1, -self.wall_bounce*self.speed[1]*r2)
                while c > 0 or self.frect.get_rect().colliderect(wall_rect):
                    self.frect.move_ip(.1*self.speed[0], .1*self.speed[1], move_factor)
                    c -= 1
                moved = True

        # Paddle collisions
        for paddle in paddles:
            if self.frect.intersect(paddle.frect):
                midx = paddle.frect.pos[0] + paddle.frect.size[0]/2
                if (paddle.facing == 1 and self.get_center()[0] < midx) or \
                   (paddle.facing == 0 and self.get_center()[0] > midx):
                    continue

                c = 0
                top_collide = self.frect.get_rect().colliderect(walls_rects[0])
                bot_collide = self.frect.get_rect().colliderect(walls_rects[1])
                while self.frect.intersect(paddle.frect) and not top_collide and not bot_collide:
                    self.frect.move_ip(-.1*self.speed[0], -.1*self.speed[1], move_factor)
                    c += 1
                    top_collide = self.frect.get_rect().colliderect(walls_rects[0])
                    bot_collide = self.frect.get_rect().colliderect(walls_rects[1])

                theta = paddle.get_angle(self.frect.pos[1] + .5*self.frect.size[1])
                v = [self.speed[0], self.speed[1]]
                v = [math.cos(theta)*v[0] - math.sin(theta)*v[1],
                     math.sin(theta)*v[0] + math.cos(theta)*v[1]]
                v[0] = -v[0]
                v = [math.cos(-theta)*v[0] - math.sin(-theta)*v[1],
                     math.cos(-theta)*v[1] + math.sin(-theta)*v[0]]

                horiz_dir = (2*paddle.facing - 1)  # left: +1, right: -1
                if v[0]*horiz_dir < 1.0:
                    eps_sign = 1.0 if v[1] >= 0 else -1.0
                    speed_mag2 = v[0]**2 + v[1]**2
                    if speed_mag2 <= 1.0:
                        v[0] = horiz_dir * 1.0
                        v[1] = 0.0
                    else:
                        v[1] = eps_sign * math.sqrt(max(0.0, speed_mag2 - 1.0))
                        v[0] = horiz_dir * 1.0

                if paddle is not self.prev_bounce:
                    self.speed = (v[0]*self.paddle_bounce, v[1]*self.paddle_bounce)
                else:
                    self.speed = (v[0], v[1])
                self.prev_bounce = paddle

                while c > 0 or self.frect.intersect(paddle.frect):
                    self.frect.move_ip(.1*self.speed[0], .1*self.speed[1], move_factor)
                    c -= 1
                moved = True

        if not moved:
            self.frect.move_ip(self.speed[0], self.speed[1], move_factor)

# -------------------- Human controls ----------------------

def directions_from_arrows(paddle_rect, other_paddle_rect, ball_rect, table_size):
    keys = pygame.key.get_pressed()
    if keys[pygame.K_UP]:
        return "up"
    elif keys[pygame.K_DOWN]:
        return "down"
    return None


def directions_from_ws(paddle_rect, other_paddle_rect, ball_rect, table_size):
    keys = pygame.key.get_pressed()
    if keys[pygame.K_w]:
        return "up"
    elif keys[pygame.K_s]:
        return "down"
    return None

# -------------------- Timeout helper ----------------------

def timeout(func, args=(), kwargs=None, timeout_duration: float = 1.0, default=None):
    if kwargs is None:
        kwargs = {}
    import threading
    class InterruptableThread(threading.Thread):
        def __init__(self):
            super().__init__()
            self.result = None
        def run(self):
            try:
                self.result = func(*args, **kwargs)
            except Exception:
                self.result = default

    it = InterruptableThread()
    it.daemon = True
    it.start()
    it.join(timeout_duration)
    if it.is_alive():
        return default
    return it.result

# -------------------- Rendering ---------------------------

def render(screen, paddles, ball, score, table_size):
    screen.fill(BLACK)
    pygame.draw.rect(screen, WHITE, paddles[0].frect.get_rect())
    pygame.draw.rect(screen, WHITE, paddles[1].frect.get_rect())
    pygame.draw.circle(screen, WHITE,
                       (int(ball.get_center()[0]), int(ball.get_center()[1])),
                       int(ball.frect.size[0]/2), 0)
    midx = int(screen.get_width() / 2)
    pygame.draw.line(screen, WHITE, (midx, 0), (midx, screen.get_height()))

    score_font = pygame.font.Font(None, 32)
    screen.blit(score_font.render(str(score[0]), True, WHITE), [int(0.4*table_size[0])-8, 0])
    screen.blit(score_font.render(str(score[1]), True, WHITE), [int(0.6*table_size[0])-8, 0])
    pygame.display.flip()

# -------------------- Scoring / Game loop -----------------

def check_point(score, ball, table_size):
    if ball.frect.pos[0] + ball.size[0]/2 < 0:
        score[1] += 1
        ball = Ball(table_size, ball.size, ball.paddle_bounce, ball.wall_bounce, ball.dust_error, ball.init_speed_mag)
        return (ball, score)
    elif ball.frect.pos[0] + ball.size[0]/2 >= table_size[0]:
        score[0] += 1
        ball = Ball(table_size, ball.size, ball.paddle_bounce, ball.wall_bounce, ball.dust_error, ball.init_speed_mag)
        return (ball, score)
    return (ball, score)


def game_loop(screen, paddles, ball, table_size, clock_rate, turn_wait_rate, score_to_win, display, fast=False):
    """Run a single game until a side reaches score_to_win.

    If fast=True, no artificial frame delay (best speed for headless).
    """
    score = [0, 0]
    while max(score) < score_to_win:
        if display:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key in (K_ESCAPE, K_q)):
                    return score
        else:
            pygame.event.pump()

        old_score = score[:]
        ball, score = check_point(score, ball, table_size)
        paddles[0].move(paddles[1].frect, ball.frect, table_size)
        paddles[1].move(paddles[0].frect, ball.frect, table_size)

        inv_move_factor = int(ball.get_speed_mag())
        if inv_move_factor > 0:
            for _ in range(inv_move_factor):
                ball.move(paddles, table_size, 1.0/inv_move_factor)
        else:
            ball.move(paddles, table_size, 1.0)

        if display:
            if score != old_score:
                font = pygame.font.Font(None, 32)
                msg = "Left scores!" if score[0] != old_score[0] else "Right scores!"
                x = 0 if "Left" in msg else int(table_size[0]/2 + 20)
                screen.blit(font.render(msg, True, WHITE, BLACK), [x, 32])
                pygame.display.flip()
                if not fast:
                    clock.tick(turn_wait_rate)
            render(screen, paddles, ball, score, table_size)

        if not fast:
            clock.tick(clock_rate)

    return score

# -------------------- Formatting helpers ------------------

def _ascii_box(title: str, lines) -> str:
    """
    Render an ASCII box with a header line and a separator under the header.

    Example:
    +-----------------------+
    | FINAL SCORE           |
    +-----------------------+
    | Left  (A) : 5         |
    | Right (B) : 3         |
    | Winner     : Left — A |
    +-----------------------+
    """
    # Normalize & compute inner width
    if not isinstance(lines, (list, tuple)):
        lines = [str(lines)]
    else:
        lines = [str(s) for s in lines]

    width = max(len(title), *(len(s) for s in lines)) + 4  # total line width incl. borders
    top = "+" + "-" * (width - 2) + "+\n"

    title_line = f"| {title.ljust(width - 4)} |\n"
    body = "".join(f"| {s.ljust(width - 4)} |\n" for s in lines)

    return top + title_line + top + body + top


def format_final_score(scoreL, scoreR, labelL, labelR, title="FINAL SCORE") -> str:
    winner_side = "Left" if scoreL > scoreR else "Right" if scoreR > scoreL else "Tie"
    winner_label = labelL if scoreL > scoreR else labelR if scoreR > scoreL else "-"

    lines = [
        f"Left  ({labelL}) : {scoreL}",
        f"Right ({labelR}) : {scoreR}",
        f"Winner           : {winner_side}" + (f" — {winner_label}" if winner_side != "Tie" else "")
    ]
    return _ascii_box(title, lines)


def format_match_report(game1, labels1, game2, labels2, total_target) -> str:
    """
    Build a consolidated match report with 3 boxes:
    - GAME 1
    - GAME 2
    - MATCH SUMMARY (controller-vs-controller across both games)

    Winner logic:
      1) More games won wins the match.
      2) If games won are equal (e.g., both win one), higher total points wins.
      3) If still equal, it's a Tie.
    """
    (g1L, g1R, t1) = game1
    (g2L, g2R, t2) = game2
    (labL1, labR1) = labels1
    (labL2, labR2) = labels2

    # Controller identities: A = labL1 (starts Left), B = labR1 (starts Right)
    A, B = labL1, labR1

    # Aggregate by controller (sides are switched in game 2)
    A_points = g1L + g2R
    B_points = g1R + g2L
    A_wins = (1 if g1L > g1R else 0) + (1 if g2R > g2L else 0)
    B_wins = (1 if g1R > g1L else 0) + (1 if g2L > g2R else 0)

    # New winner logic: wins first, then total points as tiebreaker
    if A_wins > B_wins:
        winner = A
    elif B_wins > A_wins:
        winner = B
    else:
        if A_points > B_points:
            winner = A
        elif B_points > A_points:
            winner = B
        else:
            winner = "Tie"

    def _ascii_box(title: str, lines) -> str:
        width = max(len(title), *(len(str(s)) for s in lines)) + 4
        top = "+" + "-" * (width - 2) + "+\n"
        title_line = f"| {title.ljust(width - 4)} |\n"
        body = "".join(f"| {str(s).ljust(width - 4)} |\n" for s in lines)
        return top + title_line + top + body + top

    game1_box = _ascii_box(
        f"GAME 1",
        [
            f"Left  ({labL1}) : {g1L}",
            f"Right ({labR1}) : {g1R}",
        ],
    )

    game2_box = _ascii_box(
        f"GAME 2 (switched)",
        [
            f"Left  ({labL2}) : {g2L}",
            f"Right ({labR2}) : {g2R}",
        ],
    )

    summary_box = _ascii_box(
        "MATCH SUMMARY",
        [
            f"{A} points : {A_points}",
            f"{B} points : {B_points}",
            f"Winner : {winner}",
        ],
    )

    return f"{game1_box}\n{game2_box}\n{summary_box}"


# -------------------- Match helpers -----------------------

def new_ball(table_size, ball_size, paddle_bounce, wall_bounce, dust_error, init_speed_mag):
    return Ball(table_size, ball_size, paddle_bounce, wall_bounce, dust_error, init_speed_mag)


def reset_paddles_to_centers(paddles, table_size, paddle_size):
    paddles[0].frect = fRect((20 - paddle_size[0]/2, table_size[1]/2 - paddle_size[1]/2), paddle_size)
    paddles[1].frect = fRect((table_size[0]-20 - paddle_size[0]/2, table_size[1]/2 - paddle_size[1]/2), paddle_size)


# -------------------- Controller resolution ---------------

def resolve_controller(spec: Optional[str], side: str):
    """Return (callable, label). side is 'left' or 'right'."""
    if spec and spec.lower() == "human":
        return (directions_from_ws if side == "left" else directions_from_arrows,
                "HUMAN(WS)" if side == "left" else "HUMAN(ARROWS)")

    if spec:
        try:
            mod = importlib.import_module(spec)
        except Exception as e:
            print(f"[ERROR] Could not import module '{spec}': {e}")
            sys.exit(2)
        func = getattr(mod, "pong_ai", None)
        if not callable(func):
            print(f"[ERROR] Module '{spec}' does not have callable 'pong_ai'.")
            sys.exit(2)
        return func, f"{spec}"

    return None, "UNSET"

# -------------------- Main / CLI --------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pong AI vs AI (or Human) Tournament Harness",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python PongAI.py -l studentOneAI -r studentFourAI -s 1000
  python PongAI.py -l my_team_ai -s 21          # Right = human (arrows); total 21 → 10 + 11
  python PongAI.py -r my_team_ai -s 21          # Left  = human (W/S)
  python PongAI.py -l teamA -r teamB --headless --seed 42
"""
    )
    parser.add_argument("-l", "--left", help="Left controller: module with pong_ai or 'human'")
    parser.add_argument("-r", "--right", help="Right controller: module with pong_ai or 'human'")
    parser.add_argument("-s", "--score", type=int, default=10, help="TOTAL match points (split across two games)")
    parser.add_argument("--headless", action="store_true", help="Run with no display (max speed)")
    parser.add_argument("--timeout", type=float, default=0.0003, help="Seconds per move (0 disables limit)")
    parser.add_argument("--seed", type=int, help="Set RNG seed for reproducibility")
    parser.add_argument("--clock", type=int, default=80, help="Frames per second when displayed (default: 80)")

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    left_spec = args.left
    right_spec = args.right
    if left_spec and not right_spec:
        right_spec = "human"
    elif right_spec and not left_spec:
        left_spec = "human"
    elif not left_spec and not right_spec:
        try:
            importlib.import_module("chaser_ai")
            left_spec = right_spec = "chaser_ai"
        except Exception:
            left_spec = "human"
            right_spec = "human"

    left_func, left_label = resolve_controller(left_spec, "left")
    right_func, right_label = resolve_controller(right_spec, "right")

    # Physics / table params
    table_size = (440, 280)
    paddle_size = (10, 70)
    ball_size = (15, 15)
    paddle_speed = 1
    max_angle = 45
    paddle_bounce = 1.2
    wall_bounce = 1.00
    dust_error = 0.00
    init_speed_mag = 2
    turn_wait_rate = 3

    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode(table_size)
    pygame.display.set_caption('PongAI')

    paddles = [Paddle((20, table_size[1]/2), paddle_size, paddle_speed, max_angle, 1, args.timeout),
               Paddle((table_size[0]-20, table_size[1]/2), paddle_size, paddle_speed, max_angle, 0, args.timeout)]
    ball = Ball(table_size, ball_size, paddle_bounce, wall_bounce, dust_error, init_speed_mag)

    paddles[0].move_getter = left_func if left_func else directions_from_ws
    paddles[1].move_getter = right_func if right_func else directions_from_arrows
    paddles[0].label = left_label
    paddles[1].label = right_label

    display = not args.headless
    fast = args.headless

    # Always a two-game match. Total target points = args.score
    total_target = max(1, args.score)
    pts_g1 = total_target // 2
    pts_g2 = total_target - pts_g1

    # Remember initial controller labels
    init_left_label = paddles[0].label
    init_right_label = paddles[1].label

    # Game 1 (initial sides)
    score1 = game_loop(screen, paddles, ball, table_size, args.clock, turn_wait_rate, pts_g1, display, fast=fast)
    g1L, g1R = score1

    # Prepare Game 2: reset & switch sides
    ball = new_ball(table_size, ball_size, paddle_bounce, wall_bounce, dust_error, init_speed_mag)
    reset_paddles_to_centers(paddles, table_size, paddle_size)
    paddles[0].move_getter, paddles[1].move_getter = paddles[1].move_getter, paddles[0].move_getter
    paddles[0].label,       paddles[1].label       = paddles[1].label,       paddles[0].label

    if display and not fast:
        screen.fill(BLACK)
        msg = pygame.font.Font(None, 32).render('SWITCHING SIDES', True, WHITE)
        screen.blit(msg, [int(0.6*table_size[0])-8, 0])
        pygame.display.flip()
        clock.tick(4)

    # Game 2 (switched sides)
    score2 = game_loop(screen, paddles, ball, table_size, args.clock, turn_wait_rate, pts_g2, display, fast=fast)
    g2L, g2R = score2

    # Consolidated match report (aggregate by **controller identity**)
    report = format_match_report(
        (g1L, g1R, pts_g1), (init_left_label, init_right_label),
        (g2L, g2R, pts_g2), (paddles[0].label, paddles[1].label),
        total_target,
    )
    print(report)

    pygame.quit()

if __name__ == "__main__":
    main()
