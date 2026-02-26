import random

# Keep track of which edge we aimed for last time
_last_edge = "top"

def pong_ai(paddle_frect, other_paddle_frect, ball_frect, table_size):
    global _last_ball, _last_edge

    paddle_y = paddle_frect.pos[1] + paddle_frect.size[1] / 2
    ball_x = ball_frect.pos[0] + ball_frect.size[0] / 2
    ball_y = ball_frect.pos[1] + ball_frect.size[1] / 2

    is_left = paddle_frect.pos[0] < table_size[0] / 2

    if "_last_ball" not in globals():
        _last_ball = (ball_x, ball_y)

    vx = ball_x - _last_ball[0]
    vy = ball_y - _last_ball[1]
    _last_ball = (ball_x, ball_y)

    if vx == 0:
        target_y = table_size[1] / 2
    else:
        dist_x = (paddle_frect.pos[0] + (paddle_frect.size[0] if is_left else 0)) - ball_x
        t = dist_x / vx if vx != 0 else 0
        predicted_y = ball_y + vy * t

        # Reflect off walls
        height = table_size[1]
        while predicted_y < 0 or predicted_y > height:
            if predicted_y < 0:
                predicted_y = -predicted_y
            elif predicted_y > height:
                predicted_y = 2 * height - predicted_y

        target_y = predicted_y

    # Edge offset for more extreme rebounds
    edge_offset = paddle_frect.size[1] * 0.35

    # Decide which edge to aim for
    if random.random() < 0.5:
        _last_edge = "top"
    else:
        _last_edge = "bottom"

    if _last_edge == "top":
        target_y -= edge_offset
    else:
        target_y += edge_offset

    # Clamp inside table bounds
    margin = paddle_frect.size[1] * 0.1
    target_y = max(margin, min(table_size[1] - margin, target_y))

    # Movement decision
    if paddle_y < target_y - 2:
        return "down"
    elif paddle_y > target_y + 2:
        return "up"
    return None
