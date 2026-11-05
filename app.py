
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Tetris Studio",
    page_icon="🧱",
    layout="wide"
)

# -------------------------------
# SESSION SETTINGS
# -------------------------------

if "start_speed" not in st.session_state:
    st.session_state.start_speed = 750

if "speed_increase" not in st.session_state:
    st.session_state.speed_increase = 60

if "lines_per_level" not in st.session_state:
    st.session_state.lines_per_level = 10

if "grid_width" not in st.session_state:
    st.session_state.grid_width = 10

if "grid_height" not in st.session_state:
    st.session_state.grid_height = 20

if "best_score" not in st.session_state:
    st.session_state.best_score = 0

# -------------------------------
# JAVASCRIPT GAME ENGINE
# -------------------------------

ENGINE_JS = r"""
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const nextCanvas = document.getElementById("next");
const nextCtx = nextCanvas.getContext("2d");

const COLS = __WIDTH__;
const ROWS = __HEIGHT__;
const BLOCK = 25;

canvas.width = COLS * BLOCK;
canvas.height = ROWS * BLOCK;

const COLORS = [
    null,
    "#00d9ff",
    "#367bff",
    "#ff9f43",
    "#ffe45c",
    "#45e08b",
    "#b56cff",
    "#ff5c83"
];

const SHAPES = [
    null,
    [[1,1,1,1]],
    [[2,0,0],[2,2,2]],
    [[0,0,3],[3,3,3]],
    [[4,4],[4,4]],
    [[0,5,5],[5,5,0]],
    [[0,6,0],[6,6,6]],
    [[7,7,0],[0,7,7]]
];

let grid;
let player;
let nextPiece;
let score = 0;
let lines = 0;
let level = 1;
let combo = 0;

let running = false;
let paused = false;
let gameOver = false;

let dropCounter = 0;
let lastTime = 0;

let lockFlash = null;
let clearAnimation = null;

const heldKeys = new Set();

let repeatTimer = 0;
let downTimer = 0;

const START_SPEED = __START_SPEED__;
const SPEED_INCREASE = __SPEED_INCREASE__;
const LINES_PER_LEVEL = __LINES_PER_LEVEL__;

function createGrid() {
    return Array.from(
        {length: ROWS},
        () => Array(COLS).fill(0)
    );
}

function randomPiece() {
    const id = Math.floor(Math.random() * 7) + 1;

    return {
        matrix: SHAPES[id].map(row => [...row]),
        color: id,
        pos: {x: 0, y: 0}
    };
}

function resetGame() {
    grid = createGrid();

    score = 0;
    lines = 0;
    level = 1;
    combo = 0;

    gameOver = false;
    paused = false;
    running = true;

    lockFlash = null;
    clearAnimation = null;

    nextPiece = randomPiece();
    player = randomPiece();

    playerReset();
    updateStats();
    drawNext();
    showMessage("Game started!");

    document.getElementById("gameover").style.display = "none";
    document.getElementById("pauseText").textContent = "Pause";

    lastTime = performance.now();
    requestAnimationFrame(loop);
}

function playerReset() {
    player.pos.y = 0;
    player.pos.x =
        Math.floor(COLS / 2) -
        Math.floor(player.matrix[0].length / 2);

    if (collide(grid, player)) {
        endGame();
    }
}

function collide(board, piece) {
    const matrix = piece.matrix;
    const pos = piece.pos;

    for (let y = 0; y < matrix.length; y++) {
        for (let x = 0; x < matrix[y].length; x++) {
            if (!matrix[y][x]) continue;

            const newX = x + pos.x;
            const newY = y + pos.y;

            if (
                newX < 0 ||
                newX >= COLS ||
                newY >= ROWS
            ) {
                return true;
            }

            if (newY >= 0 && board[newY][newX]) {
                return true;
            }
        }
    }

    return false;
}

function merge(board, piece) {
    piece.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                const targetY = y + piece.pos.y;
                const targetX = x + piece.pos.x;

                if (targetY >= 0) {
                    board[targetY][targetX] = piece.color;
                }
            }
        });
    });
}

function rotateMatrix(matrix, direction) {
    const rotated = matrix[0].map((_, index) =>
        matrix.map(row => row[index])
    );

    if (direction > 0) {
        return rotated.map(row => row.reverse());
    }

    return rotated.reverse();
}

function rotate(direction = 1) {
    if (!running || paused || gameOver) return;

    const originalX = player.pos.x;
    const oldMatrix = player.matrix;

    player.matrix = rotateMatrix(player.matrix, direction);

    let offset = 1;

    while (collide(grid, player)) {
        player.pos.x += offset;

        offset = -(offset + (offset > 0 ? 1 : -1));

        if (Math.abs(offset) > player.matrix[0].length + 1) {
            player.matrix = oldMatrix;
            player.pos.x = originalX;
            return;
        }
    }

    draw();
}

function move(direction, distance = 1) {
    if (!running || paused || gameOver) return;

    player.pos.x += direction * distance;

    if (collide(grid, player)) {
        player.pos.x -= direction * distance;
    }

    draw();
}

function softDrop() {
    if (!running || paused || gameOver) return;

    player.pos.y++;

    if (collide(grid, player)) {
        player.pos.y--;
        lockPiece();
        return;
    }

    score += 1;
    updateStats();
    draw();
}

function hardDrop() {
    if (!running || paused || gameOver) return;

    let distance = 0;

    while (!collide(grid, player)) {
        player.pos.y++;
        distance++;
    }

    player.pos.y--;
    score += Math.max(0, distance - 1) * 2;

    lockPiece();
}

function lockPiece() {
    merge(grid, player);

    // NEW: brief visual flash when a piece locks into place.
    lockFlash = {
        matrix: player.matrix.map(row => [...row]),
        x: player.pos.x,
        y: player.pos.y,
        color: player.color,
        start: performance.now()
    };

    clearLines();

    player = nextPiece;
    nextPiece = randomPiece();

    playerReset();
    drawNext();
    updateStats();
    draw();
}

function clearLines() {
    let cleared = 0;
    const completedRows = [];

    outer:
    for (let y = ROWS - 1; y >= 0; y--) {
        for (let x = 0; x < COLS; x++) {
            if (!grid[y][x]) {
                continue outer;
            }
        }

        completedRows.push(y);
        cleared++;
    }

    if (cleared > 0) {
        clearAnimation = {
            rows: completedRows,
            start: performance.now()
        };

        for (const row of completedRows) {
            grid.splice(row, 1);
            grid.unshift(Array(COLS).fill(0));
        }

        lines += cleared;
        combo++;

        const rewards = [0, 100, 300, 500, 800];

        score += (rewards[Math.min(cleared, 4)] || 800) * level;

        if (cleared > 1) {
            score += combo * 50 * level;
            showMessage("COMBO! " + cleared + " lines cleared!");
        } else {
            showMessage("Line cleared!");
        }

        level = Math.floor(lines / LINES_PER_LEVEL) + 1;
    } else {
        combo = 0;
    }

    updateStats();
}

function showMessage(message) {
    document.getElementById("message").textContent = message;
}

function drawBlock(context, x, y, color, size, alpha = 1) {
    context.globalAlpha = alpha;

    context.fillStyle = color;
    context.fillRect(
        x * size + 1,
        y * size + 1,
        size - 2,
        size - 2
    );

    context.fillStyle = "#ffffff44";
    context.fillRect(
        x * size + 3,
        y * size + 3,
        size - 6,
        3
    );

    context.strokeStyle = "#ffffff30";
    context.lineWidth = 1;
    context.strokeRect(
        x * size + 1,
        y * size + 1,
        size - 2,
        size - 2
    );

    context.globalAlpha = 1;
}

function drawMatrix(context, matrix, offset, color, alpha = 1, size = BLOCK) {
    matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                drawBlock(
                    context,
                    x + offset.x,
                    y + offset.y,
                    color,
                    size,
                    alpha
                );
            }
        });
    });
}

function getGhostY() {
    let ghostY = player.pos.y;

    while (true) {
        ghostY++;

        const test = {
            matrix: player.matrix,
            pos: {x: player.pos.x, y: ghostY}
        };

        if (collide(grid, test)) {
            return ghostY - 1;
        }
    }
}

function draw() {
    ctx.fillStyle = "#111827";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Grid background
    ctx.strokeStyle = "#ffffff0d";
    ctx.lineWidth = 1;

    for (let x = 0; x <= COLS; x++) {
        ctx.beginPath();
        ctx.moveTo(x * BLOCK, 0);
        ctx.lineTo(x * BLOCK, ROWS * BLOCK);
        ctx.stroke();
    }

    for (let y = 0; y <= ROWS; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * BLOCK);
        ctx.lineTo(COLS * BLOCK, y * BLOCK);
        ctx.stroke();
    }

    // Locked blocks
    grid.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                drawBlock(ctx, x, y, COLORS[value], BLOCK);
            }
        });
    });

    // Ghost piece
    if (running && !gameOver) {
        const ghostY = getGhostY();

        drawMatrix(
            ctx,
            player.matrix,
            {x: player.pos.x, y: ghostY},
            COLORS[player.color],
            0.22
        );
    }

    // Current piece
    if (!gameOver) {
        drawMatrix(
            ctx,
            player.matrix,
            player.pos,
            COLORS[player.color]
        );
    }

    // NEW: lock flash effect
    if (lockFlash) {
        const elapsed = performance.now() - lockFlash.start;

        if (elapsed < 180) {
            const alpha = 1 - elapsed / 180;

            drawMatrix(
                ctx,
                lockFlash.matrix,
                {x: lockFlash.x, y: lockFlash.y},
                "#ffffff",
                alpha * 0.9
            );
        } else {
            lockFlash = null;
        }
    }

    // NEW: completed row clearing effect
    if (clearAnimation) {
        const elapsed = performance.now() - clearAnimation.start;

        if (elapsed < 220) {
            const alpha = 1 - elapsed / 220;

            ctx.fillStyle = `rgba(255,255,255,${alpha * 0.8})`;

            clearAnimation.rows.forEach(row => {
                ctx.fillRect(
                    0,
                    row * BLOCK,
                    canvas.width,
                    BLOCK
                );
            });
        } else {
            clearAnimation = null;
        }
    }
}

function drawNext() {
    nextCtx.clearRect(0, 0, nextCanvas.width, nextCanvas.height);

    nextCtx.fillStyle = "#111827";
    nextCtx.fillRect(0, 0, nextCanvas.width, nextCanvas.height);

    const size = 22;
    const matrix = nextPiece.matrix;

    const offsetX =
        (nextCanvas.width - matrix[0].length * size) / 2;

    const offsetY =
        (nextCanvas.height - matrix.length * size) / 2;

    matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                drawBlock(
                    nextCtx,
                    x + offsetX / size,
                    y + offsetY / size,
                    COLORS[nextPiece.color],
                    size
                );
            }
        });
    });
}

function updateStats() {
    document.getElementById("score").textContent = score;
    document.getElementById("lines").textContent = lines;
    document.getElementById("level").textContent = level;
    document.getElementById("combo").textContent = combo;

    const currentBest = Math.max(
        Number(document.getElementById("best").textContent) || 0,
        score
    );

    document.getElementById("best").textContent = currentBest;
}

function endGame() {
    running = false;
    gameOver = true;

    document.getElementById("gameover").style.display = "block";
    document.getElementById("finalScore").textContent =
        "Final score: " + score;

    showMessage("Game Over!");
    draw();
}

function togglePause() {
    if (gameOver || !running) return;

    paused = !paused;

    document.getElementById("pauseText").textContent =
        paused ? "Resume" : "Pause";

    showMessage(paused ? "Game paused" : "Game resumed");

    if (!paused) {
        lastTime = performance.now();
        requestAnimationFrame(loop);
    }
}

function getDropInterval() {
    return Math.max(
        90,
        START_SPEED - (level - 1) * SPEED_INCREASE
    );
}

function loop(time = 0) {
    if (!running || paused || gameOver) return;

    const delta = time - lastTime;
    lastTime = time;

    dropCounter += delta;

    if (dropCounter > getDropInterval()) {
        player.pos.y++;

        if (collide(grid, player)) {
            player.pos.y--;
            lockPiece();
        }

        dropCounter = 0;
    }

    draw();
    requestAnimationFrame(loop);
}

// ------------------------------------
// NEW: CONTINUOUS KEYBOARD MOVEMENT
// ------------------------------------

document.addEventListener("keydown", event => {
    const key = event.key;

    const controls = [
        "ArrowLeft",
        "ArrowRight",
        "ArrowDown",
        "ArrowUp",
        " "
    ];

    if (controls.includes(key)) {
        event.preventDefault();
    }

    if (heldKeys.has(key)) return;

    heldKeys.add(key);

    if (!running || paused || gameOver) return;

    if (key === "ArrowLeft" || key.toLowerCase() === "a") {
        move(-1);
        repeatTimer = 0;
    }

    if (key === "ArrowRight" || key.toLowerCase() === "d") {
        move(1);
        repeatTimer = 0;
    }

    if (key === "ArrowDown" || key.toLowerCase() === "s") {
        softDrop();
        downTimer = 0;
    }

    if (key === "ArrowUp" || key.toLowerCase() === "w") {
        rotate();
    }

    if (key === " ") {
        hardDrop();
    }

    if (key.toLowerCase() === "p") {
        togglePause();
    }
});

document.addEventListener("keyup", event => {
    heldKeys.delete(event.key);

    if (
        event.key === "ArrowLeft" ||
        event.key === "ArrowRight" ||
        event.key.toLowerCase() === "a" ||
        event.key.toLowerCase() === "d"
    ) {
        repeatTimer = 0;
    }

    if (
        event.key === "ArrowDown" ||
        event.key.toLowerCase() === "s"
    ) {
        downTimer = 0;
    }
});

window.addEventListener("blur", () => {
    heldKeys.clear();
    repeatTimer = 0;
    downTimer = 0;
});

// Repeat movement while a key stays held.
setInterval(() => {
    if (!running || paused || gameOver) return;

    const left =
        heldKeys.has("ArrowLeft") || heldKeys.has("a") || heldKeys.has("A");

    const right =
        heldKeys.has("ArrowRight") || heldKeys.has("d") || heldKeys.has("D");

    const down =
        heldKeys.has("ArrowDown") || heldKeys.has("s") || heldKeys.has("S");

    if (left && !right) {
        repeatTimer += 1;

        if (repeatTimer >= 3) {
            move(-1);
        }
    } else if (right && !left) {
        repeatTimer += 1;

        if (repeatTimer >= 3) {
            move(1);
        }
    } else {
        repeatTimer = 0;
    }

    if (down) {
        downTimer += 1;

        if (downTimer >= 1) {
            softDrop();
        }
    }
}, 35);

// Start game
resetGame();
"""

# -------------------------------
# APP HEADER
# -------------------------------

st.title("🧱 Tetris Studio")
st.caption("Your own customizable Tetris game.")

play_tab, customize_tab, records_tab, editor_tab, guide_tab = st.tabs([
    "🎮 PLAY",
    "🛠️ CUSTOMIZE",
    "🏆 RECORDS",
    "💻 CODE EDITOR",
    "📘 GUIDE"
])

# -------------------------------
# CUSTOMIZATION
# -------------------------------

with customize_tab:
    st.header("Customize your game")

    st.session_state.start_speed = st.slider(
        "Starting fall speed (milliseconds)",
        200, 1200,
        st.session_state.start_speed,
        50
    )

    st.session_state.speed_increase = st.slider(
        "Speed increase per level",
        10, 150,
        st.session_state.speed_increase,
        5
    )

    st.session_state.lines_per_level = st.slider(
        "Lines needed per level",
        5, 20,
        st.session_state.lines_per_level
    )

    st.session_state.grid_width = st.selectbox(
        "Grid width",
        [10],
        index=0
    )

    st.session_state.grid_height = st.selectbox(
        "Grid height",
        [20],
        index=0
    )

    st.info("Your settings are used when the game is started.")

# -------------------------------
# GAME
# -------------------------------

with play_tab:
    left, right = st.columns([2, 1])

    with left:
        st.subheader("Game board")

        game_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    padding: 12px;
    background: #10131d;
    color: white;
    font-family: Arial, sans-serif;
}

.layout {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 18px;
    align-items: flex-start;
}

canvas {
    display: block;
    background: #111827;
    border: 2px solid #46516b;
    border-radius: 8px;
    max-width: 100%;
    height: auto;
}

.side {
    width: 150px;
    text-align: center;
}

.stat {
    background: #202638;
    padding: 10px;
    border-radius: 9px;
    margin-bottom: 9px;
}

.stat small {
    display: block;
    color: #aab5ca;
}

.stat strong {
    font-size: 22px;
}

button {
    padding: 10px 15px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    margin: 4px;
}

.primary {
    background: #45d69a;
    color: #10251c;
}

.secondary {
    background: #39445e;
    color: white;
}

#message {
    text-align: center;
    color: #9bbcff;
    min-height: 25px;
    margin: 10px;
}

#gameover {
    display: none;
    background: #202638;
    border: 1px solid #ff5c83;
    border-radius: 12px;
    padding: 15px;
    text-align: center;
    margin-top: 12px;
}

#gameover h2 {
    color: #ff809d;
}

.controls {
    text-align: center;
    margin-top: 12px;
}

.help {
    text-align: center;
    color: #aab5ca;
    font-size: 12px;
    margin-top: 12px;
}
</style>
</head>

<body>

<div id="message">Loading game...</div>

<div class="layout">
    <div>
        <canvas id="game"></canvas>
    </div>

    <div class="side">
        <div class="stat">
            <small>SCORE</small>
            <strong id="score">0</strong>
        </div>

        <div class="stat">
            <small>BEST</small>
            <strong id="best">0</strong>
        </div>

        <div class="stat">
            <small>LINES</small>
            <strong id="lines">0</strong>
        </div>

        <div class="stat">
            <small>LEVEL</small>
            <strong id="level">1</strong>
        </div>

        <div class="stat">
            <small>COMBO</small>
            <strong id="combo">0</strong>
        </div>

        <p>Next block</p>
        <canvas id="next" width="120" height="100"></canvas>
    </div>
</div>

<div class="controls">
    <button class="primary" onclick="resetGame()">Restart</button>
    <button class="secondary" onclick="togglePause()" id="pauseText">Pause</button>
</div>

<div id="gameover">
    <h2>Game Over!</h2>
    <p id="finalScore"></p>
    <button class="primary" onclick="resetGame()">Play Again</button>
</div>

<div class="help">
    ← → Move | ↓ Soft drop | ↑ Rotate | Space Hard drop | P Pause
    <br>
    You can hold the arrow keys for continuous movement.
</div>

<script>
__ENGINE__
</script>

</body>
</html>
"""

        engine = ENGINE_JS
        engine = engine.replace("__WIDTH__", str(st.session_state.grid_width))
        engine = engine.replace("__HEIGHT__", str(st.session_state.grid_height))
        engine = engine.replace("__START_SPEED__", str(st.session_state.start_speed))
        engine = engine.replace("__SPEED_INCREASE__", str(st.session_state.speed_increase))
        engine = engine.replace("__LINES_PER_LEVEL__", str(st.session_state.lines_per_level))

        final_html = game_html.replace("__ENGINE__", engine)

        components.html(final_html, height=750, scrolling=True)

    with right:
        st.subheader("Controls")
        st.markdown("""
        | Key | Action |
        |---|---|
        | ← | Move left |
        | → | Move right |
        | ↓ | Soft drop |
        | ↑ | Rotate |
        | Space | Hard drop |
        | P | Pause |
        """)

        st.info(
            "Hold Left or Right to keep moving. "
            "Hold Down to drop faster."
        )

# -------------------------------
# RECORDS
# -------------------------------

with records_tab:
    st.header("🏆 Records")

    st.metric(
        "Best score in this session",
        st.session_state.best_score
    )

    st.info(
        "The game currently runs inside a separate browser frame. "
        "Permanent score saving and automatic score transfer "
        "can be added in a future update."
    )

# -------------------------------
# CODE EDITOR
# -------------------------------

with editor_tab:
    st.header("💻 JavaScript Engine")

    st.write(
        "This is the JavaScript engine used by the game. "
        "You can inspect and edit the code here."
    )

    if "engine_editor" not in st.session_state:
        st.session_state.engine_editor = ENGINE_JS

    st.text_area(
        "Game engine source",
        value=st.session_state.engine_editor,
        height=500,
        key="engine_editor"
    )

    st.caption(
        "The Play tab uses the built-in engine. "
        "Changes in this editor are for inspecting and editing the source; "
        "they are not automatically applied to the running game."
    )

# -------------------------------
# GUIDE
# -------------------------------

with guide_tab:
    st.header("📘 How to Play")

    st.markdown("""
    ### Objective
    Fit the falling blocks together to complete horizontal lines.

    ### Scoring
    - Clearing one line gives 100 points.
    - Clearing two lines gives 300 points.
    - Clearing three lines gives 500 points.
    - Clearing four lines gives 800 points.
    - Combo clears give extra points.

    ### Levels
    Every time you clear enough lines, your level increases.
    Blocks fall faster as you progress.

    ### New features
    - Blocks flash briefly when they lock into place.
    - Completed rows have a clearing animation.
    - Hold the arrow keys for continuous movement.
    - Ghost piece shows where your block will land.
    - Next-piece preview helps you plan ahead.
    """)
