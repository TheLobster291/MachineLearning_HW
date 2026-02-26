# student_ai.py
def pong_ai(paddle_frect, other_paddle_frect, ball_frect, table_size):
    """
    Smarter Pong AI: predicts where the ball will intersect our paddle column
    and moves to intercept, instead of blindly chasing.
    """
    # Paddle and ball centers
    paddle_y = paddle_frect.pos[1] + paddle_frect.size[1] / 2
    ball_x = ball_frect.pos[0] + ball_frect.size[0] / 2
    ball_y = ball_frect.pos[1] + ball_frect.size[1] / 2

    # Is this the left or right paddle?
    is_left = paddle_frect.pos[0] < table_size[0] / 2

    # Get ball velocity direction from current + previous positions
    # Since we don't get velocity directly, infer from "other paddle"
    global _last_ball
    if "_last_ball" not in globals():
        _last_ball = (ball_x, ball_y)

    vx = ball_x - _last_ball[0]
    vy = ball_y - _last_ball[1]
    _last_ball = (ball_x, ball_y)

    if vx == 0:
        target_y = table_size[1] / 2  # safe default
    else:
        # Predict y where ball will reach our paddle's x
        if is_left:
            dist_x = (paddle_frect.pos[0] + paddle_frect.size[0]) - ball_x
        else:
            dist_x = (paddle_frect.pos[0]) - ball_x
        t = dist_x / vx if vx != 0 else 0
        predicted_y = ball_y + vy * t

        # Reflect off top/bottom walls (simulate bounces)
        height = table_size[1]
        while predicted_y < 0 or predicted_y > height:
            if predicted_y < 0:
                predicted_y = -predicted_y
            elif predicted_y > height:
                predicted_y = 2 * height - predicted_y

        target_y = predicted_y

    # Add slight offset 
    margin = paddle_frect.size[1] * 0.1
    if target_y < margin:
        target_y = margin
    elif target_y > table_size[1] - margin:
        target_y = table_size[1] - margin

    # Decide move
    if paddle_y < target_y - 2:  
        return "down"
    elif paddle_y > target_y + 2:
        return "up"
    return None
