#!/usr/bin/env python3
import sys

try:
    import curses
except ImportError:
    print("This game needs curses. On Windows run: pip install windows-curses")
    sys.exit(1)

win_lines = [
    ('1', '2', '3'), # across the top
    ('4', '5', '6'), # across the middle
    ('7', '8', '9'), # across the bottom
    ('1', '4', '7'), # down the left side
    ('2', '5', '8'), # down the middle
    ('3', '6', '9'), # down the right side
    ('1', '5', '9'), # diagonal
    ('3', '5', '7')  # diagonal
]

# (row, column) of every square on the board
positions = {str(n): ((n - 1) // 3, (n - 1) % 3) for n in range(1, 10)}

moves = {
    curses.KEY_UP: (-1, 0), 'w': (-1, 0), 'W': (-1, 0),
    curses.KEY_DOWN: (1, 0), 's': (1, 0), 'S': (1, 0),
    curses.KEY_LEFT: (0, -1), 'a': (0, -1), 'A': (0, -1),
    curses.KEY_RIGHT: (0, 1), 'd': (0, 1), 'D': (0, 1)
}

enter_keys = ('\n', '\r', ' ', curses.KEY_ENTER)
backspace_keys = ('\b', '\x7f', curses.KEY_BACKSPACE)
quit_keys = ('q', 'Q', '\x1b')

CELL_W = 7
CELL_H = 3
BOARD_W = CELL_W * 3 + 4
BOARD_H = CELL_H * 3 + 4
MIN_W = 56
MIN_H = 22
NAME_LEN = 12
TITLE_TEXT = "T I C K  ·  T A C K  ·  T O E"

X_PAIR, O_PAIR, GRID, DIM, TITLE, X_CURSOR, O_CURSOR, DIM_CURSOR, X_WIN, O_WIN = range(1, 11)

mark_pairs = {'X': X_PAIR, 'O': O_PAIR}
cursor_pairs = {'X': X_CURSOR, 'O': O_CURSOR, ' ': DIM_CURSOR}
win_pairs = {'X': X_WIN, 'O': O_WIN}

def other(mark):
    return 'O' if mark == 'X' else 'X'

def winning_line(board, turn):
    for line in win_lines:
        if all(board[key] == turn for key in line):
            return line
    return None

def can_still_win(board, player, moves_left):
    # a line is still winnable if the other player has no mark in it and
    # the player has enough turns left to fill its empty squares
    for line in win_lines:
        marks = [board[key] for key in line]
        if all(mark in (' ', player) for mark in marks) and marks.count(' ') <= moves_left:
            return True
    return False

def is_dead_draw(board, next_turn, count):
    empty = 9 - count
    next_moves = (empty + 1) // 2
    other_moves = empty // 2
    return not can_still_win(board, next_turn, next_moves) and not can_still_win(board, other(next_turn), other_moves)

def setup_colors():
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK

    if curses.COLORS >= 256:
        # sky blue X, pink O, slate grid, gold title
        x, o, grid, dim, title, cursor, ink = 81, 211, 60, 243, 222, 237, 16
        curses.init_pair(X_CURSOR, x, cursor)
        curses.init_pair(O_CURSOR, o, cursor)
        curses.init_pair(DIM_CURSOR, 250, cursor)
    else:
        x, o, grid, dim, title, cursor, ink = (curses.COLOR_CYAN, curses.COLOR_MAGENTA, curses.COLOR_BLUE,
                                               curses.COLOR_WHITE, curses.COLOR_YELLOW, curses.COLOR_WHITE,
                                               curses.COLOR_BLACK)
        for pair in (X_CURSOR, O_CURSOR, DIM_CURSOR):
            curses.init_pair(pair, ink, cursor)

    curses.init_pair(X_PAIR, x, bg)
    curses.init_pair(O_PAIR, o, bg)
    curses.init_pair(GRID, grid, bg)
    curses.init_pair(DIM, dim, bg)
    curses.init_pair(TITLE, title, bg)
    curses.init_pair(X_WIN, ink, x)
    curses.init_pair(O_WIN, ink, o)

def show_cursor(visible):
    try:
        curses.curs_set(1 if visible else 0)
    except curses.error:
        pass

def put(scr, y, x, text, attr=0):
    # writing to the bottom-right corner raises even though it draws fine
    try:
        scr.addstr(y, x, text, attr)
    except curses.error:
        pass

def put_centered(scr, y, parts):
    width = scr.getmaxyx()[1]
    x = (width - sum(len(text) for text, attr in parts)) // 2
    for text, attr in parts:
        put(scr, y, x, text, attr)
        x += len(text)
    return x

def name_attr(mark):
    return curses.color_pair(mark_pairs[mark]) | curses.A_BOLD

def too_small(scr):
    height, width = scr.getmaxyx()
    if height >= MIN_H and width >= MIN_W:
        return False
    put(scr, 0, 0, "Make the terminal bigger to play", curses.A_BOLD)
    put(scr, 1, 0, "(at least %dx%d)" % (MIN_W, MIN_H))
    return True

def draw_title(scr):
    put_centered(scr, 1, [(TITLE_TEXT, curses.color_pair(TITLE) | curses.A_BOLD)])

def draw_help(scr, text):
    put_centered(scr, MIN_H - 1, [(text, curses.color_pair(DIM))])

def draw_board(scr, top, board, cursor, line):
    left = (scr.getmaxyx()[1] - BOARD_W) // 2
    grid = curses.color_pair(GRID)
    for i in range(BOARD_H):
        if i == 0:
            text = '╭' + '┬'.join(['─' * CELL_W] * 3) + '╮'
        elif i == BOARD_H - 1:
            text = '╰' + '┴'.join(['─' * CELL_W] * 3) + '╯'
        elif i % (CELL_H + 1) == 0:
            text = '├' + '┼'.join(['─' * CELL_W] * 3) + '┤'
        else:
            text = '│' + '│'.join([' ' * CELL_W] * 3) + '│'
        put(scr, top + i, left, text, grid)

    for key, (row, col) in positions.items():
        mark = board[key]
        y = top + 1 + row * (CELL_H + 1)
        x = left + 1 + col * (CELL_W + 1)

        if line and key in line:
            fill = curses.color_pair(win_pairs[mark]) | curses.A_BOLD
            style = fill
        elif key == cursor:
            fill = curses.color_pair(cursor_pairs[mark])
            style = fill | (curses.A_BOLD if mark != ' ' else 0)
        else:
            fill = 0
            style = name_attr(mark) if mark != ' ' else curses.color_pair(DIM)

        for dy in range(CELL_H):
            put(scr, y + dy, x, ' ' * CELL_W, fill)
        put(scr, y + CELL_H // 2, x + CELL_W // 2, mark if mark != ' ' else key, style)

def draw_game(scr, board, players, score, cursor, line, status, message, help_text):
    scr.erase()
    if too_small(scr):
        scr.refresh()
        return
    dim = curses.color_pair(DIM)
    bold = curses.A_BOLD

    draw_title(scr)
    put_centered(scr, 3, [
        (players['X'], name_attr('X')), ('  ' + str(score['X']), bold),
        ('     ties ', dim), (str(score['tie']), bold), ('     ', 0),
        (str(score['O']) + '  ', bold), (players['O'], name_attr('O'))
    ])
    draw_board(scr, 5, board, cursor, line)
    put_centered(scr, 5 + BOARD_H + 1, status)
    put_centered(scr, 5 + BOARD_H + 2, [(message, curses.color_pair(TITLE))])
    draw_help(scr, help_text)
    scr.refresh()

def draw_names(scr, names, active, message):
    scr.erase()
    if too_small(scr):
        scr.refresh()
        return
    draw_title(scr)
    put_centered(scr, 5, [("Who's playing?", curses.A_BOLD)])

    cursor_at = None
    for i, mark in enumerate(('X', 'O')):
        attr = curses.A_UNDERLINE if mark == active else curses.color_pair(DIM)
        field = names[mark].ljust(NAME_LEN)
        end = put_centered(scr, 8 + i * 2, [(mark, name_attr(mark)), ('   ', 0), (field, attr)])
        if mark == active:
            cursor_at = (8 + i * 2, end - NAME_LEN + len(names[mark]))

    put_centered(scr, 13, [(message, curses.color_pair(TITLE))])
    draw_help(scr, "type a name  ·  Enter next  ·  Esc quit")
    if cursor_at:
        scr.move(*cursor_at)
    scr.refresh()

def ask_players(scr):
    names = {'X': '', 'O': ''}
    defaults = {'X': 'Player 1', 'O': 'Player 2'}
    message = ''
    show_cursor(True)

    for mark in ('X', 'O'):
        while True:
            draw_names(scr, names, mark, message)
            key = read_key(scr)
            if key == '\x1b':
                return None
            if key in enter_keys and key != ' ':
                name = names[mark].strip() or defaults[mark]
                if mark == 'O' and name.lower() == names['X'].lower():
                    message = "Pick a different name from " + names['X']
                    continue
                names[mark] = name
                message = ''
                break
            if key in backspace_keys:
                names[mark] = names[mark][:-1]
            elif isinstance(key, str) and key.isprintable() and len(names[mark]) < NAME_LEN:
                names[mark] += key

    show_cursor(False)
    return names

arrow_codes = {'A': curses.KEY_UP, 'B': curses.KEY_DOWN, 'C': curses.KEY_RIGHT, 'D': curses.KEY_LEFT}

def read_key(scr):
    # some terminals send raw "ESC [ A" style arrows that curses doesn't
    # translate, so turn those into arrow keys instead of a lone Esc
    key = scr.get_wch()
    if key != '\x1b':
        return key
    scr.nodelay(True)
    try:
        rest = ''
        while len(rest) < 2:
            try:
                rest += scr.get_wch()
            except (curses.error, TypeError):
                break
    finally:
        scr.nodelay(False)
    if len(rest) == 2 and rest[0] in '[O' and rest[1] in arrow_codes:
        return arrow_codes[rest[1]]
    return '\x1b'

def step(cursor, d_row, d_col):
    row, col = positions[cursor]
    row = (row + d_row) % 3
    col = (col + d_col) % 3
    return str(row * 3 + col + 1)

def play_round(scr, players, score, turn):
    board = {key: ' ' for key in positions}
    count = 0
    cursor = '5'
    message = ''
    play_help = "arrows/WASD move  ·  Enter place  ·  1-9 place  ·  q quit"

    while True:
        status = [(players[turn], name_attr(turn)), ("'s turn  ", 0), (turn, name_attr(turn))]
        draw_game(scr, board, players, score, cursor, None, status, message, play_help)
        key = read_key(scr)

        if key in quit_keys:
            return 'quit'
        move = None
        if key in moves:
            cursor = step(cursor, *moves[key])
            message = ''
        elif key in enter_keys:
            move = cursor
        elif key in positions:
            cursor = key
            move = key
        if move is None:
            continue

        if board[move] != ' ':
            message = "That square is taken"
            continue

        board[move] = turn
        count += 1
        message = ''

        line = winning_line(board, turn)
        if line:
            score[turn] += 1
            status = [(players[turn], name_attr(turn)), (" wins!", curses.A_BOLD)]
            break

        turn = other(turn)

        if is_dead_draw(board, turn, count):
            score['tie'] += 1
            reason = "Board full" if count == 9 else "No one can win from here"
            status = [(reason + "  ·  ", 0), ("it's a tie", curses.A_BOLD)]
            break

    # blink the winning line a few times before asking to play again
    end_help = "y play again  ·  n new players  ·  q quit"
    if line:
        for i in range(3):
            draw_game(scr, board, players, score, None, line, status, '', end_help)
            curses.napms(220)
            draw_game(scr, board, players, score, None, None, status, '', end_help)
            curses.napms(140)
        curses.flushinp()

    while True:
        draw_game(scr, board, players, score, None, line, status, "Play again? (y/n)", end_help)
        key = read_key(scr)
        if key in ('y', 'Y'):
            return 'again'
        if key in ('n', 'N'):
            return 'new'
        if key in quit_keys:
            return 'quit'

def main(scr):
    setup_colors()
    if hasattr(curses, 'set_escdelay'):
        curses.set_escdelay(25)

    while True:
        players = ask_players(scr)
        if players is None:
            return

        # the score lasts for as long as the same players keep playing
        score = {'X': 0, 'O': 0, 'tie': 0}
        first = 'X'
        while True:
            result = play_round(scr, players, score, first)
            if result == 'quit':
                return
            if result == 'new':
                break
            first = other(first)

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
