const boardElement = document.getElementById('board');
const currentPlayerElement = document.getElementById('current-player');
const blackScoreElement = document.getElementById('black-score');
const whiteScoreElement = document.getElementById('white-score');
const resetButton = document.getElementById('reset-button');

const BOARD_SIZE = 8;
const EMPTY = 0;
const BLACK = 1;
const WHITE = 2;

let board = [];
let currentPlayer = BLACK;

function initGame() {
    board = Array(BOARD_SIZE).fill(0).map(() => Array(BOARD_SIZE).fill(EMPTY));
    board[3][3] = WHITE;
    board[3][4] = BLACK;
    board[4][3] = BLACK;
    board[4][4] = WHITE;
    currentPlayer = BLACK;
    renderBoard();
    updateScore();
    updateCurrentPlayer();
}

function renderBoard() {
    boardElement.innerHTML = '';
    for (let row = 0; row < BOARD_SIZE; row++) {
        for (let col = 0; col < BOARD_SIZE; col++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            cell.addEventListener('click', handleCellClick);

            const disc = document.createElement('div');
            disc.className = 'disc';

            if (board[row][col] === BLACK) {
                disc.classList.add('black');
                cell.appendChild(disc);
            } else if (board[row][col] === WHITE) {
                disc.classList.add('white');
                cell.appendChild(disc);
            }

            boardElement.appendChild(cell);
        }
    }
}

function handleCellClick(event) {
    const row = parseInt(event.target.dataset.row);
    const col = parseInt(event.target.dataset.col);

    if (isValidMove(row, col, currentPlayer)) {
        placeDisc(row, col, currentPlayer);
        flipDiscs(row, col, currentPlayer);
        currentPlayer = (currentPlayer === BLACK) ? WHITE : BLACK;
        renderBoard();
        updateScore();
        updateCurrentPlayer();

        if (!hasValidMove(currentPlayer)) {
            if (!hasValidMove((currentPlayer === BLACK) ? WHITE : BLACK)) {
                endGame();
            } else {
                alert('パスします');
                currentPlayer = (currentPlayer === BLACK) ? WHITE : BLACK;
                updateCurrentPlayer();
            }
        }
    }
}

function isValidMove(row, col, player) {
    if (board[row][col] !== EMPTY) {
        return false;
    }

    const opponent = (player === BLACK) ? WHITE : BLACK;
    const directions = [
        [-1, -1], [-1, 0], [-1, 1],
        [0, -1],           [0, 1],
        [1, -1], [1, 0], [1, 1]
    ];

    for (const [dr, dc] of directions) {
        let r = row + dr;
        let c = col + dc;
        let hasOpponentDisc = false;

        while (r >= 0 && r < BOARD_SIZE && c >= 0 && c < BOARD_SIZE) {
            if (board[r][c] === opponent) {
                hasOpponentDisc = true;
            } else if (board[r][c] === player) {
                if (hasOpponentDisc) {
                    return true;
                }
                break;
            } else {
                break;
            }
            r += dr;
            c += dc;
        }
    }

    return false;
}

function placeDisc(row, col, player) {
    board[row][col] = player;
}

function flipDiscs(row, col, player) {
    const opponent = (player === BLACK) ? WHITE : BLACK;
    const directions = [
        [-1, -1], [-1, 0], [-1, 1],
        [0, -1],           [0, 1],
        [1, -1], [1, 0], [1, 1]
    ];

    for (const [dr, dc] of directions) {
        let r = row + dr;
        let c = col + dc;
        const discsToFlip = [];

        while (r >= 0 && r < BOARD_SIZE && c >= 0 && c < BOARD_SIZE) {
            if (board[r][c] === opponent) {
                discsToFlip.push([r, c]);
            } else if (board[r][c] === player) {
                for (const [fr, fc] of discsToFlip) {
                    board[fr][fc] = player;
                }
                break;
            } else {
                break;
            }
            r += dr;
            c += dc;
        }
    }
}

function hasValidMove(player) {
    for (let row = 0; row < BOARD_SIZE; row++) {
        for (let col = 0; col < BOARD_SIZE; col++) {
            if (isValidMove(row, col, player)) {
                return true;
            }
        }
    }
    return false;
}

function updateScore() {
    let blackScore = 0;
    let whiteScore = 0;
    for (let row = 0; row < BOARD_SIZE; row++) {
        for (let col = 0; col < BOARD_SIZE; col++) {
            if (board[row][col] === BLACK) {
                blackScore++;
            } else if (board[row][col] === WHITE) {
                whiteScore++;
            }
        }
    }
    blackScoreElement.textContent = blackScore;
    whiteScoreElement.textContent = whiteScore;
}

function updateCurrentPlayer() {
    currentPlayerElement.textContent = (currentPlayer === BLACK) ? '黒' : '白';
}

function endGame() {
    const blackScore = parseInt(blackScoreElement.textContent);
    const whiteScore = parseInt(whiteScoreElement.textContent);
    let message = 'ゲーム終了！\n';
    if (blackScore > whiteScore) {
        message += '黒の勝ちです！';
    } else if (whiteScore > blackScore) {
        message += '白の勝ちです！';
    } else {
        message += '引き分けです！';
    }
    alert(message);
}

resetButton.addEventListener('click', initGame);

initGame();
