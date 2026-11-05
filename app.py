
import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path

st.set_page_config(
    page_title="Tetris Studio",
    page_icon="🧱",
    layout="wide"
)

ENGINE_FILE = Path("tetris_engine.js")

DEFAULT_SETTINGS = {
    "start_speed": 700,
    "speed_increase": 50,
    "lines_per_level": 10,
    "grid_width": 10,
    "grid_height": 20
}

DEFAULT_ENGINE = r"""
const canvas = document.getElementById("board");
const ctx = canvas.getContext("2d");

const COLS = 10;
const ROWS = 20;
const SIZE = 28;

const COLORS = [
    null,
    "#42d9ff",
    "#3978ff",
    "#ff9f43",
    "#ffe45c",
    "#54e68a",
    "#bd70ff",
    "#ff607c"
];

const SHAPES = [
    [],
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
let running = false;
let paused = false;
let gameEnded = false;
let dropCounter = 0;
let lastTime = 0;
let dropSpeed = SETTINGS.start_speed;

function createGrid() {
    return Array.from(
        {length: ROWS},
        () => Array(COLS).fill(0)
    );
}

function randomPiece() {
    const id = 1 + Math.floor(Math.random() * 7);

    return {
        matrix: SHAPES[id].map(row => [...row]),
        id: id,
        x: 3,
        y: 0
    };
}

function resetGame() {
    grid = createGrid();

    player = randomPiece();
    nextPiece = randomPiece();

    score = 0;
    lines = 0;
    level = 1;

    dropSpeed = SETTINGS.start_speed;
    dropCounter = 0;
    lastTime = 0;

    paused = false;
    gameEnded = false;

    updateStats();
    drawNext();
    draw();
}

function collide(piece, offsetX = 0, offsetY = 0, matrix = piece.matrix) {
    for (let y = 0; y < matrix.length; y++) {
        for (let x = 0; x < matrix[y].length; x++) {

            if (!matrix[y][x]) continue;

            const nx = piece.x + x + offsetX;
            const ny = piece.y + y + offsetY;

            if (
                nx < 0 ||
                nx >= COLS ||
                ny >= ROWS
            ) {
                return true;
            }

            if (ny >= 0 && grid[ny][nx]) {
                return true;
            }
        }
    }

    return false;
}

function merge() {
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                const gy = player.y + y;
                const gx = player.x + x;

                if (gy >= 0) {
                    grid[gy][gx] = value;
                }
            }
        });
    });
}

function rotateMatrix(matrix) {
    return matrix[0].map((_, i) =>
        matrix.map(row => row[i]).reverse()
    );
}

function rotate() {
    const rotated = rotateMatrix(player.matrix);

    if (!collide(player, 0, 0, rotated)) {
        player.matrix = rotated;
    } else {
        // Small wall adjustment when rotating near an edge.
        for (const shift of [-1, 1, -2, 2]) {
            if (!collide(player, shift, 0, rotated)) {
                player.x += shift;
                player.matrix = rotated;
                break;
            }
        }
    }

    draw();
}

function move(direction) {
    if (!running || paused || gameEnded) return;

    if (!collide(player, direction, 0)) {
        player.x += direction;
    }

    draw();
}

function softDrop() {
    if (!running || paused || gameEnded) return;

    if (!collide(player, 0, 1)) {
        player.y++;
        score += 1;
    } else {
        lockPiece();
    }

    updateStats();
    draw();
}

function hardDrop() {
    if (!running || paused || gameEnded) return;

    let distance = 0;

    while (!collide(player, 0, 1)) {
        player.y++;
        distance++;
    }

    score += distance * 2;

    lockPiece();
    updateStats();
    draw();
}

function lockPiece() {
    merge();
    clearLines();

    player = nextPiece;
    player.x = 3;
    player.y = 0;

    nextPiece = randomPiece();

    drawNext();

    if (collide(player)) {
        endGame();
    }
}

function clearLines() {
    let cleared = 0;

    outer:
    for (let y = ROWS - 1; y >= 0; y--) {
        for (let x = 0; x < COLS; x++) {
            if (!grid[y][x]) {
                continue outer;
            }
        }

        grid.splice(y, 1);
        grid.unshift(Array(COLS).fill(0));

        cleared++;
        y++;
    }

    if (cleared > 0) {
        const points = [0, 100, 300, 500, 800];

        score += points[cleared] * level;
        lines += cleared;

        level = Math.floor(lines / SETTINGS.lines_per_level) + 1;

        dropSpeed = Math.max(
            90,
            SETTINGS.start_speed -
            (level - 1) * SETTINGS.speed_increase
        );

        showMessage(cleared);
    }

    updateStats();
}

function showMessage(cleared) {
    const message = document.getElementById("message");

    message.textContent =
        cleared === 4 ? "TETRIS!" :
        cleared === 3 ? "TRIPLE!" :
        cleared === 2 ? "DOUBLE!" :
        "LINE CLEAR!";

    message.style.opacity = 1;

    setTimeout(() => {
        message.style.opacity = 0;
    }, 900);
}

function drawBlock(x, y, id, size = SIZE) {
    ctx.fillStyle = COLORS[id];

    ctx.fillRect(
        x * size + 1,
        y * size + 1,
        size - 2,
        size - 2
    );

    ctx.strokeStyle = "#ffffff44";
    ctx.lineWidth = 1;

    ctx.strokeRect(
        x * size + 2,
        y * size + 2,
        size - 4,
        size - 4
    );

    ctx.fillStyle = "#ffffff20";

    ctx.fillRect(
        x * size + 4,
        y * size + 4,
        size - 8,
        3
    );
}

function draw() {
    ctx.fillStyle = "#091329";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Background grid
    ctx.strokeStyle = "#ffffff0b";

    for (let x = 0; x <= COLS; x++) {
        ctx.beginPath();
        ctx.moveTo(x * SIZE, 0);
        ctx.lineTo(x * SIZE, ROWS * SIZE);
        ctx.stroke();
    }

    for (let y = 0; y <= ROWS; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * SIZE);
        ctx.lineTo(COLS * SIZE, y * SIZE);
        ctx.stroke();
    }

    // Locked blocks
    grid.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                drawBlock(x, y, value);
            }
        });
    });

    // Ghost piece
    let ghostY = player.y;

    while (!collide(
        {...player, y: ghostY},
        0,
        1
    )) {
        ghostY++;
    }

    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                ctx.globalAlpha = 0.2;
                drawBlock(
                    player.x + x,
                    ghostY + y,
                    value
                );
                ctx.globalAlpha = 1;
            }
        });
    });

    // Active piece
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value) {
                drawBlock(
                    player.x + x,
                    player.y + y,
                    value
                );
            }
        });
    });
}

function drawNext() {
    const nextCanvas = document.getElementById("next");
    const nctx = nextCanvas.getContext("2d");

    nctx.fillStyle = "#091329";
    nctx.fillRect(0, 0, 130, 110);

    const matrix = nextPiece.matrix;
    const size = 22;

    const offsetX =
        (130 - matrix[0].length * size) / 2;

    const offsetY =
        (110 - matrix.length * size) / 2;

    matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (!value) return;

            nctx.fillStyle = COLORS[value];

            nctx.fillRect(
                offsetX + x * size + 1,
                offsetY + y * size + 1,
                size - 2,
                size - 2
            );
        });
    });
}

function updateStats() {
    document.getElementById("score").textContent =
        score.toLocaleString();

    document.getElementById("lines").textContent = lines;
    document.getElementById("level").textContent = level;
}

function endGame() {
    running = false;
    gameEnded = true;

    const overlay = document.getElementById("overlay");

    overlay.style.display = "flex";

    overlay.innerHTML = `
        <h1>GAME OVER</h1>
        <p>Score: ${score.toLocaleString()}</p>
        <p>Lines cleared: ${lines}</p>
        <button id="restart">PLAY AGAIN</button>
    `;

    document.getElementById("restart").onclick = startGame;

    document.getElementById("finalScore").value = score;
}

function startGame() {
    resetGame();

    running = true;
    paused = false;
    gameEnded = false;

    document.getElementById("overlay").style.display = "none";

    requestAnimationFrame(loop);
}

function loop(time = 0) {
    if (!running) return;

    const delta = time - lastTime;
    lastTime = time;

    if (!paused) {
        dropCounter += delta;

        if (dropCounter > dropSpeed) {
            softDrop();
            dropCounter = 0;
        }

        draw();
    }

    requestAnimationFrame(loop);
}

window.addEventListener("keydown", event => {
    const key = event.key.toLowerCase();

    if (
        ["arrowleft", "arrowright", "arrowdown", "arrowup", " "].includes(key)
    ) {
        event.preventDefault();
    }

    if (key === "arrowleft" || key === "a") move(-1);
    if (key === "arrowright" || key === "d") move(1);
    if (key === "arrowdown" || key === "s") softDrop();

    if (key === "arrowup" || key === "w") rotate();
    if (key === " ") hardDrop();

    if (key === "p" && running) {
        paused = !paused;
    }
});

document.getElementById("start").onclick = startGame;

document.getElementById("pause").onclick = () => {
    if (running) paused = !paused;
};

resetGame();
"""

if "settings" not in st.session_state:
    st.session_state.settings = DEFAULT_SETTINGS.copy()

if "engine" not in st.session_state:
    st.session_state.engine = (
        ENGINE_FILE.read_text(encoding="utf-8")
        if ENGINE_FILE.exists()
        else DEFAULT_ENGINE
    )

# -------------------------------
# DESIGN
# -------------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(140deg,#07101f,#171638,#080c19);
    color: white;
}

.block-container {
    max-width: 1300px;
    padding-top: 1.5rem;
}

.hero {
    padding: 22px;
    border: 1px solid #344c78;
    border-radius: 16px;
    background: linear-gradient(100deg,#102746,#251644);
}

.hero h1 {
    color: #8cecff;
    letter-spacing: 5px;
    margin: 0;
}

.hero p {
    color: #bdcbe5;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🧱 TETRIS STUDIO</h1>
    <p>Play, customize and edit your own Tetris game.</p>
</div>
""", unsafe_allow_html=True)

# -------------------------------
# TABS
# -------------------------------

play, customize, records, editor, guide = st.tabs([
    "🎮 PLAY",
    "🛠️ CUSTOMIZE",
    "🏆 RECORDS",
    "💻 CODE EDITOR",
    "📘 GUIDE"
])

# -------------------------------
# PLAY
# -------------------------------

with play:
    cfg = st.session_state.settings

    page = r"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    body {
        margin: 0;
        background: #080d20;
        color: white;
        font-family: Arial;
    }

    #layout {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        gap: 22px;
        padding: 15px;
        flex-wrap: wrap;
    }

    #board {
        width: 280px;
        height: 560px;
        border: 2px solid #36527d;
        border-radius: 8px;
        background: #091329;
    }

    #side {
        width: 175px;
    }

    .panel {
        background: #111d3a;
        border: 1px solid #2d426d;
        border-radius: 9px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .value {
        color: #7cecff;
        font-size: 24px;
        font-weight: bold;
    }

    button {
        background: linear-gradient(90deg,#00b8d4,#755aff);
        color: white;
        border: none;
        border-radius: 7px;
        padding: 11px;
        cursor: pointer;
        font-weight: bold;
        width: 100%;
        margin-top: 7px;
    }

    #message {
        color: #ffe45c;
        font-size: 22px;
        font-weight: bold;
        height: 28px;
        text-align: center;
        opacity: 0;
        transition: opacity .2s;
    }

    #overlay {
        position: absolute;
        inset: 0;
        background: #050a19ed;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }

    #overlay h1 {
        color: #7cecff;
        letter-spacing: 4px;
    }

    #stage {
        position: relative;
    }

    #overlay button {
        width: 170px;
    }

    .controls {
        color: #a6bad9;
        font-size: 12px;
        line-height: 1.8;
    }
    </style>
    </head>

    <body>

    <div id="layout">

        <div id="stage">

            <canvas id="board" width="280" height="560"></canvas>

            <div id="overlay">
                <h1>TETRIS</h1>
                <p>Stack blocks. Clear lines. Beat your record.</p>
                <button id="start">START GAME</button>
            </div>

        </div>

        <div id="side">

            <div class="panel">
                <b>SCORE</b>
                <div class="value" id="score">0</div>
            </div>

            <div class="panel">
                <b>LINES</b>
                <div class="value" id="lines">0</div>
            </div>

            <div class="panel">
                <b>LEVEL</b>
                <div class="value" id="level">1</div>
            </div>

            <div class="panel">
                <b>NEXT PIECE</b>
                <canvas id="next" width="130" height="110"></canvas>
            </div>

            <div id="message"></div>

            <button id="pause">PAUSE / RESUME</button>

            <div class="panel controls">
                <b>CONTROLS</b><br>
                ← → Move<br>
                ↓ Soft drop<br>
                ↑ Rotate<br>
                SPACE Hard drop<br>
                P Pause
            </div>

        </div>

    </div>

    <input id="finalScore" type="hidden" value="0">

    <script>
    const SETTINGS = __SETTINGS__;
    </script>

    <script>
    __ENGINE__
    </script>

    </body>
    </html>
    """

    page = page.replace(
        "__SETTINGS__",
        json.dumps(cfg)
    )

    page = page.replace(
        "__ENGINE__",
        st.session_state.engine
    )

    components.html(page, height=640, scrolling=False)

    st.info(
        "Click inside the game and use your keyboard. "
        "Press Space to instantly drop a piece."
    )

# -------------------------------
# CUSTOMIZE
# -------------------------------

with customize:
    st.subheader("🛠️ Game Settings")

    cfg = st.session_state.settings

    a, b = st.columns(2)

    with a:
        cfg["start_speed"] = st.slider(
            "Starting fall speed (milliseconds)",
            200, 1200, cfg["start_speed"], 50
        )

        cfg["speed_increase"] = st.slider(
            "Speed increase per level",
            10, 100, cfg["speed_increase"], 5
        )

    with b:
        cfg["lines_per_level"] = st.slider(
            "Lines required per level",
            5, 20, cfg["lines_per_level"]
        )

        cfg["grid_width"] = st.selectbox(
            "Board width",
            [10],
            index=0
        )

    st.session_state.settings = cfg

    st.success(
        "Settings updated. Start a new game to apply them."
    )

# -------------------------------
# RECORDS
# -------------------------------

with records:
    st.subheader("🏆 Your Tetris Records")

    st.write(
        "This starter version displays your current game settings. "
        "Automatic browser-to-Streamlit score saving is not connected yet."
    )

    st.metric("Starting fall speed", cfg["start_speed"])
    st.metric("Lines per level", cfg["lines_per_level"])

# -------------------------------
# CODE EDITOR
# -------------------------------

with editor:
    st.subheader("💻 JavaScript Code Editor")

    st.warning(
        "Changing the game engine can break the game if the JavaScript "
        "contains errors. Keep a backup."
    )

    edited = st.text_area(
        "Edit the Tetris engine",
        value=st.session_state.engine,
        height=500
    )

    st.session_state.engine = edited

    if st.button("💾 SAVE GAME ENGINE", type="primary"):
        ENGINE_FILE.write_text(
            edited,
            encoding="utf-8"
        )

        st.success("Saved to tetris_engine.js.")

    if st.button("↩️ RESTORE ORIGINAL ENGINE"):
        st.session_state.engine = DEFAULT_ENGINE

        if ENGINE_FILE.exists():
            ENGINE_FILE.unlink()

        st.success("Original engine restored. Reload the app.")

# -------------------------------
# GUIDE
# -------------------------------

with guide:
    st.subheader("📘 Tetris Studio Guide")

    st.markdown("""
    ### Controls
    - Left / Right: Move blocks.
    - Down: Move the block down faster.
    - Up: Rotate.
    - Space: Hard drop.
    - P: Pause.

    ### Scoring
    - 1 line: 100 points.
    - 2 lines: 300 points.
    - 3 lines: 500 points.
    - 4 lines: 800 points.

    ### Project files
    - `app.py`: Main game and dashboard.
    - `tetris_engine.js`: Saved JavaScript game engine.
    - `requirements.txt`: Python dependencies.
    """)

    st.code(
        "pip install -r requirements.txt\n"
        "streamlit run app.py",
        language="bash"
    )
