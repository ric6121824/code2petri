const canvasCpu = document.getElementById('game-canvas-cpu');
const canvasGpu = document.getElementById('game-canvas-gpu');
const ctx = canvasCpu.getContext('2d');

const btnStart = document.getElementById('btn-start');
const btnStep = document.getElementById('btn-step');
const btnRandom = document.getElementById('btn-random');
const speedSlider = document.getElementById('speed-slider');
const modeRadios = document.getElementsByName('mode');

// Settings
const CELL_SIZE = 4; // Smaller cells to show off GPU power better
const ROWS = 150;
const COLS = 200;

canvasCpu.width = COLS * CELL_SIZE;
canvasCpu.height = ROWS * CELL_SIZE;
canvasGpu.width = COLS * CELL_SIZE;
canvasGpu.height = ROWS * CELL_SIZE;

// Colors
const COLOR_BG = '#1a2235';
const COLOR_ALIVE = '#00f0ff';

// Engines
const gpuEngine = new WebGLEngine(canvasGpu, COLS, ROWS);

// CPU State
let grid = createGrid();
let isRunning = false;
let mode = 'gpu'; // 'gpu' or 'cpu'
let speed = 100; // ms per tick
let animationId = null;
let lastFrameTime = 0;

// Initialize
init();

function init() {
    randomizeBoth();
    setupEventListeners();
}

function createGrid(random = false) {
    let newGrid = new Array(ROWS);
    for (let i = 0; i < ROWS; i++) {
        newGrid[i] = new Array(COLS);
        for (let j = 0; j < COLS; j++) {
            newGrid[i][j] = random ? (Math.random() > 0.8 ? 1 : 0) : 0;
        }
    }
    return newGrid;
}

function randomizeBoth() {
    // Randomize CPU
    grid = createGrid(true);
    drawCpuGrid();
    
    // Randomize GPU
    gpuEngine.randomize();
}

function drawCpuGrid() {
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, canvasCpu.width, canvasCpu.height);

    ctx.fillStyle = COLOR_ALIVE;
    for (let i = 0; i < ROWS; i++) {
        for (let j = 0; j < COLS; j++) {
            if (grid[i][j] === 1) {
                ctx.fillRect(j * CELL_SIZE, i * CELL_SIZE, CELL_SIZE, CELL_SIZE);
            }
        }
    }
}

function countNeighbors(g, x, y) {
    let sum = 0;
    for (let i = -1; i < 2; i++) {
        for (let j = -1; j < 2; j++) {
            let row = (x + i + ROWS) % ROWS;
            let col = (y + j + COLS) % COLS;
            sum += g[row][col];
        }
    }
    sum -= g[x][y];
    return sum;
}

function stepCpu() {
    let nextGrid = createGrid();
    // Sequential iteration through the grid
    for (let i = 0; i < ROWS; i++) {
        for (let j = 0; j < COLS; j++) {
            let state = grid[i][j];
            let neighbors = countNeighbors(grid, i, j);

            if (state === 0 && neighbors === 3) {
                nextGrid[i][j] = 1;
            } else if (state === 1 && (neighbors < 2 || neighbors > 3)) {
                nextGrid[i][j] = 0;
            } else {
                nextGrid[i][j] = state;
            }
        }
    }
    grid = nextGrid;
    drawCpuGrid();
}

function loop(timestamp) {
    if (!isRunning) return;

    if (timestamp - lastFrameTime > speed) {
        if (mode === 'gpu') {
            gpuEngine.step();
        } else {
            stepCpu();
        }
        lastFrameTime = timestamp;
    }

    animationId = requestAnimationFrame(loop);
}

function startSimulation() {
    if (!isRunning) {
        isRunning = true;
        btnStart.textContent = 'Stop';
        btnStart.style.backgroundColor = '#ff4444'; 
        btnStart.style.boxShadow = '0 0 20px rgba(255, 68, 68, 0.4)';
        lastFrameTime = performance.now();
        animationId = requestAnimationFrame(loop);
    } else {
        stopSimulation();
    }
}

function stopSimulation() {
    isRunning = false;
    btnStart.textContent = 'Start';
    btnStart.style.backgroundColor = 'var(--primary)';
    btnStart.style.boxShadow = 'none';
    cancelAnimationFrame(animationId);
}

function setupEventListeners() {
    btnStart.addEventListener('click', startSimulation);

    btnStep.addEventListener('click', () => {
        stopSimulation();
        if (mode === 'gpu') {
            gpuEngine.step();
        } else {
            stepCpu();
        }
    });

    btnRandom.addEventListener('click', () => {
        stopSimulation();
        randomizeBoth();
    });

    speedSlider.addEventListener('input', (e) => {
        speed = 1010 - e.target.value; 
    });

    modeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            mode = e.target.value;
            if (mode === 'gpu') {
                canvasCpu.style.display = 'none';
                canvasGpu.style.display = 'block';
            } else {
                canvasGpu.style.display = 'none';
                canvasCpu.style.display = 'block';
            }
        });
    });
}
