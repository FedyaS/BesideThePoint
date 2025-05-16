import pygame
import sys
from pygame.locals import *
import asyncio
import platform
from BesideThePoint import trial

# Initialize Pygame
pygame.init()

# Window setup
WIDTH, HEIGHT = 800, 800
OFFSET_X, OFFSET_Y = 200, 200
screen = pygame.display.set_mode((WIDTH+OFFSET_X, HEIGHT+OFFSET_Y))
pygame.display.set_caption("Geometric Simulation")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)

# Font setup
font = pygame.font.Font(None, 36)

def to_screen(x, y):
    """Convert unit square coordinates [0,1]x[0,1] to screen coordinates."""
    screen_x = x * WIDTH + (OFFSET_X // 2)
    screen_y = (1 - y) * HEIGHT + (OFFSET_Y // 2) # Flip y-axis so y=0 is at bottom
    return (screen_x, screen_y)

def draw_scene(data):
    """Draw the entire scene based on trial data."""
    screen.fill(WHITE)

    # Draw square boundaries in black
    pygame.draw.line(screen, BLACK, to_screen(0, 0), to_screen(1, 0), 2)
    pygame.draw.line(screen, BLACK, to_screen(1, 0), to_screen(1, 1), 2)
    pygame.draw.line(screen, BLACK, to_screen(1, 1), to_screen(0, 1), 2)
    pygame.draw.line(screen, BLACK, to_screen(0, 1), to_screen(0, 0), 2)

    # Draw closest side in blue
    side_start, side_end = data['closest_side']
    pygame.draw.line(screen, BLUE, to_screen(*side_start), to_screen(*side_end), 3)

    # Draw blue and red points
    blue_screen = to_screen(*data['blue_point'])
    red_screen = to_screen(*data['red_point'])
    pygame.draw.circle(screen, BLUE, blue_screen, 10)
    pygame.draw.circle(screen, RED, red_screen, 10)

    # Draw connecting line in green
    pygame.draw.line(screen, GREEN, blue_screen, red_screen, 2)

    # Draw perpendicular bisector in green
    mid_x, mid_y = data['mid_point']
    neg_recip_slope = data['neg_recip_slope']
    intersection_points = []
    # Intersection with x=0
    y_at_x0 = neg_recip_slope * (0 - mid_x) + mid_y
    if 0 <= y_at_x0 <= 1:
        intersection_points.append((0, y_at_x0))
    # Intersection with x=1
    y_at_x1 = neg_recip_slope * (1 - mid_x) + mid_y
    if 0 <= y_at_x1 <= 1:
        intersection_points.append((1, y_at_x1))
    # Intersection with y=0 and y=1 (avoid division by zero)
    if abs(neg_recip_slope) > 1e-10:  # Check to avoid division by near-zero
        x_at_y0 = (0 - mid_y) / neg_recip_slope + mid_x
        if 0 <= x_at_y0 <= 1:
            intersection_points.append((x_at_y0, 0))
        x_at_y1 = (1 - mid_y) / neg_recip_slope + mid_x
        if 0 <= x_at_y1 <= 1:
            intersection_points.append((x_at_y1, 1))
    else:  # Horizontal bisector
        if 0 <= mid_y <= 1:
            intersection_points = [(0, mid_y), (1, mid_y)]
    # Handle near-vertical bisector
    if len(intersection_points) < 2 and abs(neg_recip_slope) > 1e10:
        if 0 <= mid_x <= 1:
            intersection_points = [(mid_x, 0), (mid_x, 1)]
    # Draw bisector if we have two points
    if len(intersection_points) >= 2:
        p1 = to_screen(*intersection_points[0])
        p2 = to_screen(*intersection_points[1])
        pygame.draw.line(screen, GREEN, p1, p2, 2)

    # Draw intersection point if it exists
    if data['intersection_point']:
        inter_screen = to_screen(*data['intersection_point'])
        pygame.draw.circle(screen, GREEN, inter_screen, 5)

    # Display solution text
    text = font.render(data['solution'], True, BLACK)
    screen.blit(text, (10, 10))

async def main():
    data = trial()  # Initial trial
    FPS = 60

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_RETURN:
                    try:
                        data = trial()
                    except ZeroDivisionError:
                        data = trial()  # Retry on rare division by zero

        draw_scene(data)
        pygame.display.flip()
        await asyncio.sleep(1.0 / FPS)

if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())