# == Imports (Provided) ==
import time
import numpy as np
from IPython.display import display, HTML, clear_output
from ipywidgets import HTML, Layout

def make_board(size: int = 32) -> np.ndarray:
    """Return a (size x size) zero-initialized integer grid."""
    return np.zeros((size, size), dtype=int)
    
def patterns() -> dict:
    """
    Return a mapping of pattern name -> array (for fixed patterns) or callable(shape)->array (for generated patterns).
    Provided fixed patterns: 'loaf' and 'pulsar'.
    Required generated pattern: 'random'.
    """
    # --- Provided: fixed patterns  ---
    loaf = np.array([
        [0,1,1,0],
        [1,0,0,1],
        [0,1,0,1],
        [0,0,1,0]
    ], dtype=int)

    blinker = np.array([[1,1,1]], dtype=int)

    toad = np.array([[0,1,1,1],
                     [1,1,1,0]], dtype=int)

    block = np.array([[1,1],[1,1]], dtype=int)

    boat = np.array([[1,1,0],
                     [1,0,1],
                     [0,1,0]], dtype=int)

    tub = np.array([[0,1,0],
                    [1,0,1],
                    [0,1,0]], dtype=int)

    pulsar = np.array([
        [0,0,1,1,0,0,0,0,0,1,1,0,0],
        [0,0,0,1,1,0,0,0,1,1,0,0,0],
        [1,0,0,1,0,1,0,1,0,1,0,0,1],
        [1,1,1,0,1,1,0,1,1,0,1,1,1],
        [0,1,0,1,0,1,0,1,0,1,0,1,0],
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,1,1,1,0,0,0,1,1,1,0,0],
        [0,1,0,1,0,1,0,1,0,1,0,1,0],
        [1,1,1,0,1,1,0,1,1,0,1,1,1],
        [1,0,0,1,0,1,0,1,0,1,0,0,1],
        [0,0,0,1,1,0,0,0,1,1,0,0,0],
        [0,0,1,1,0,0,0,0,0,1,1,0,0]
    ], dtype=int)

    # --- Students: implement these fixed patterns ---
    beehive = np.array([
        [0,1,1,0],
        [1,0,0,1],
        [0,1,1,0]
    ], dtype=int)

    beacon = np.array([
        [1,1,0,0],
        [1,1,0,0],
        [0,0,1,1],
        [0,0,1,1]
    ], dtype=int)

    # --- Required: generated pattern (implement this) ---
    def random_pattern(shape):
        """
        Return a random 0/1 ndarray of the given shape.
        - shape: tuple like (rows, cols)
        """
        grid = np.random.randint(2, size=shape, dtype=int)
        # Set borders to 0
        grid[0, :] = 0
        grid[-1, :] = 0
        grid[:, 0] = 0
        grid[:, -1] = 0
        return grid

    # Build and return the mapping
    pats = {
        "blinker": blinker,
        "toad": toad,
        "beacon": beacon,
        "pulsar": pulsar,
        "block": block,
        "beehive": beehive,
        "loaf": loaf,
        "boat": boat,
        "tub": tub,
        "random": random_pattern,   # <- callable function
    }

    return pats

def seed_board(name: str, size: int = 32) -> np.ndarray:
    """Return a new (size x size) board seeded with the named pattern.

    - Fixed pattern (ndarray): center it on a blank board.
    - Generated pattern (callable): call with shape=(size, size) and return the result.
    """
    pats = patterns()
    pattern = pats[name]

    if callable(pattern):
        # Generated pattern (e.g., "random")
        return pattern((size, size))
    else:
        # Fixed pattern — center it on a new board
        board = np.zeros((size, size), dtype=int)
        p_rows, p_cols = pattern.shape

        # Compute top-left corner for centering
        start_row = (size - p_rows) // 2
        start_col = (size - p_cols) // 2

        board[start_row:start_row + p_rows, start_col:start_col + p_cols] = pattern
        return board
    
def center_place(board: np.ndarray, pattern: np.ndarray) -> np.ndarray:
    """Place pattern into the center of board and return the board."""
    R, C = board.shape
    r, c = pattern.shape

    start_row = (R - r) // 2
    start_col = (C - c) // 2
    
    board[start_row:start_row + r, start_col:start_col + c] = pattern

    return board

def iterate(population: np.ndarray) -> np.ndarray:
    """Compute one in-place Life step on population with a fixed zero border, then return it."""

    # 1
    N = (
        population[:-2, :-2] + population[:-2, 1:-1] + population[:-2, 2:] +
        population[1:-1, :-2]                      + population[1:-1, 2:] +
        population[2:, :-2] + population[2:, 1:-1] + population[2:, 2:]
    )

    # 2
    inner = population[1:-1, 1:-1]

    # 3
    birth = (inner == 0) & (N == 3)                # Dead cell with exactly 3 neighbors → live
    survive = (inner == 1) & ((N == 2) | (N == 3)) # Live cell with 2 or 3 neighbors → stays live

    # 4
    inner[...] = 0
    inner[birth | survive] = 1

    #5
    return population