#!/usr/bin/env python3

import curses
import socket
import threading
import time
import sys
import textwrap

stdscr = curses.initscr()

errorMessages = {'already_exists': 'Game already exists on server', 'invalid_count': 'Wrong number of players',
                 'full': 'All players are already in game', 'not_started': 'Game has not started yet',
                 'already_joined': 'You have already joined the game', 'not_selectable': 'The stone You chose is not selecable',
                 'not_your_turn': 'It’s not Your turn', 'not_needed': 'Voting is not needed', 'invalid': 'Stone cannot be moved there',
                 'no_vote': 'You didn’t vote'}

errorText = ''
hintText = ''
command = ''
myTeam = ''
server = ''
roll = -1

allowedVerbs = {}
votes = {}
gameEnded = False

curses.noecho()
curses.start_color()
curses.use_default_colors()

statusBox = curses.newwin(9, curses.COLS, 0, 0)
boardBox = curses.newwin(15, 30, 10, 0)
textBox = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

board = [[0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0],
         [0, 0, 0, 0, 0]]

curses.init_pair(1, 3, -1)
curses.init_pair(3, 4, -1)
curses.init_pair(5, 3, 15)
curses.init_pair(7, 4, 15)
curses.init_pair(9, 3, 10)
curses.init_pair(11, 4, 10)
curses.init_pair(8, -1, 10)


def socketPrintLine(sock, message):
    sock.sendall(bytes(message + '\n', 'utf-8'))


def socketReadLine(sock):
    response = ''
    while True:
        c = sock.recv(1).decode('utf-8')
        print(c, file=sys.stderr, end='')
        if c != '\n':
            response += c
        else:
            print('\n', file=sys.stderr)
            return response
# todo what if (when `exit`) i close a socket while recv’ing and (throw
# and) catch an exception


def waitForBoard():
    socketReadLine(client)
    response = socketReadLine(client)
    i = 0
    for point in response.split(' ')[2:]:
        board[int(i / 5)][int(i % 5)] = int(point)
        i += 1
    drawBoard()


def drawBoard():
    print('#drawing board', file=sys.stderr)
    # printBoard()
    boardBox.move(0, 0)
    boardBox.addstr('   A   B   C   D   E\n')
    boardBox.addstr(' ╭───┬───┬───┬───┬───╮\n')
    i = 0
    for row in board:
        boardBox.addstr(str(i + 1))
        for box in row:
            boardBox.addstr('│ ')
            digit = 1 if box % 10 > 0 else 0
            colour = int(str(10 * int(box / 10) + digit), 2)
            print('{} {}|'.format(box % 10, colour), file=sys.stderr, end='\t')
            boardBox.addstr(str(box % 10) if box != 0 else ' ', curses.color_pair(colour))
            boardBox.addstr(' ')
        print('', file=sys.stderr)
        boardBox.addstr('│\n')
        print
        if(i < 4):
            boardBox.addstr(' ├───┼───┼───┼───┼───┤\n')
        i += 1
    boardBox.addstr(' ╰───┴───┴───┴───┴───╯\n')
    boardBox.refresh()


def printBoard():
    for row in board:
        for field in row:
            print('{}\t'.format(field), end='', file=sys.stderr)
        print('', file=sys.stderr)


def startGame():
    threading.Thread(target=runGame).start()


def runGame():
    global allowedVerbs
    global votes
    global hintText
    global errorText
    global roll
    won = None
    while won == None:
        response = socketReadLine(client)
        allowedVerbs = {'exit'}
        if response.split(' ')[1] == 'active' and response.split(' ')[2] == myTeam:
            errorText = 'Your move'
            response = socketReadLine(client)
            roll = int(response.split(' ')[2])
            response = socketReadLine(client)
            if response.split(' ')[3] == 'needed':
                highlightSelectables(roll)
                allowedVerbs = {'exit', 'select'}
                hintText = 'Type `select {n}` to vote for Your stone with number n'
            votes = {}
            votingFinished = False
            while not votingFinished:
                response = socketReadLine(client)
                response = response.split(' ')
                if response[-1] == 'selected':
                    votingFinished = True
                    votes = {}
                    selected = response[-3] + ' ' + response[-2]
                elif response[0] == 'success' and response[1] == 'vote':
                    try:
                        votes[response[3] + ' ' + response[4]] += 1
                    except KeyError:
                        votes[response[3] + ' ' + response[4]] = 1
                elif response[-1] == 'not_selected':
                    votes = {}
                elif response[0] == 'error':
                    errorText = errorMessages[response[3]]

            response = socketReadLine(client)
            if response.split(' ')[3] == 'needed':
                highlightMoveTargets(selected)
                allowedVerbs = {'exit', 'move'}
                hintText = 'Type `move {target}` (e.g. move A2) to move vote for the move'
            votes = {}
            votingFinished = False
            while not votingFinished:
                response = socketReadLine(client)
                response = response.split(' ')
                if response[0] == 'success' and response[1] == 'vote':
                    try:
                        votes[response[3] + ' ' + response[4]] += 1
                    except KeyError:
                        votes[response[3] + ' ' + response[4]] = 1
                elif response[-1] == 'not_moved':
                    votes = {}
                elif response[0] == 'error':
                    errorText = errorMessages[response[3]]
                elif response[4] == 'moved':
                    votingFinished = True
                    votes = {}
                    target = response[6] + ' ' + response[7]
            moveStone(selected, target)
        elif response.split(' ')[1] == 'active':
            errorText = 'Waiting for opponent’s move'
            response = socketReadLine(client)
            if response.split(' ')[4] == 'moved':
                moveStone(' '.join(response.split(' ')[2:4]), ' '.join(
                    response.split(' ')[6:8]))
            else:
                won = response.split(' ')[3]
                errorText = '{} team won by {}.'.format(response.split(' ')[3].capitalize(),
                                                        {'corner': 'corner reaching', 'no_stones': 'opponent capturing',
                                                         'no_vote': 'opponent disconnection'}[response.split(' ')[4]])
                allowedVerbs = {'exit', 'create', 'join'}
                hintText = 'Type `exit` to quit, `create {n}` to create a game for n players per team  or `join` to join an existing game'
        elif response.split(' ')[1] == 'game':
            won = response.split(' ')[3]
            errorText = '{} team won by {}.'.format(response.split(' ')[3].capitalize(),
                                                    {'corner': 'corner reaching', 'no_stones': 'opponent capturing',
                                                     'no_vote': 'opponent disconnection'}[response.split(' ')[4]])
            allowedVerbs = {'exit', 'create', 'join'}
            hintText = 'Type `exit` to quit, `create {n}` to create a game for n players per team  or `join` to join an existing game'


def highlightSelectables(rolledValue):
    teamModifier = 0 if myTeam == 'yellow' else 10
    stones = [0, 0, 0, 0, 0, 0, 0]
    i = 0
    for row in board:
        j = 0
        for field in row:
            if int(field / 10) * 10 == teamModifier:
                stones[field % 10] = (i, j)
            j += 1
        i += 1

    lower = None
    for stone in stones[:rolledValue]:
        if stone != 0:
            lower = stone
    upper = None
    print('# rolled: ' + str(rolledValue), file=sys.stderr)
    print(stones[rolledValue + 1:], file=sys.stderr)
    for stone in stones[rolledValue + 1:]:
        print(stone, file=sys.stderr)
        if stone != 0:
            upper = stone
            print('returning', file=sys.stderr)
            break
    print(stones, file=sys.stderr)

    i, j = lower
    board[i][j] += 100
    i, j = upper
    board[i][j] += 100
    drawBoard()


def highlightMoveTargets(selected):
    dehighlight()
    direction = 1 if myTeam == 'yellow' else -1
    selected = selected.split(' ')
    i, j = int(selected[0]), int(selected[1])
    board[i + direction][j] += 1000
    board[i][j + direction] += 1000
    board[i + direction][j + direction] += 1000
    drawBoard()


def moveStone(source, target):
    dehighlight()
    source = source.split(' ')
    target = target.split(' ')
    board[int(target[0])][int(target[1])] = board[
        int(source[0])][int(source[1])]
    board[int(source[0])][int(source[1])] = 0
    drawBoard()


def dehighlight():
    for i in range(len(board)):
        for j in range(len(board[i])):
            board[i][j] %= 100


def parseVotes():
    votesString = ''
    for pos, vote in votes.items():
        votesString += translateToChessNotation(pos) + ': ' + str(vote) + ', '
    return votesString[:-2]


def translateToChessNotation(position):
    row = int(position.split(' ')[0])
    column = int(position.split(' ')[1])
    row += 1
    column += ord('A')
    column = chr(column)
    return '{}{}'.format(row, column)


def do(command):
    global errorText
    global hintText
    global allowedVerbs
    global server
    global myTeam
    verb = command.split(' ')[0]
    if verb not in allowedVerbs:
        errorText = verb + ' not allowed now'
        return
    if verb == 'exit':
        curses.endwin()
        client.close()
        # todo interrupt runGame thread
        return True
    elif verb == 'connect':
        try:
            address = command.split(' ')[1]
            port = command.split(' ')[2]
        except IndexError:
            errorText = 'Syntax error in {}'.format(command)
            return
        try:
            client.connect((address, int(port)))
        except Exception as e:
            errorText = str(e)
        else:
            errorText = 'Connected to game.'
            hintText = 'Type `create {n}` to create a game for n players per team or `join` to join an existing game'
            server = address + ':' + port
            allowedVerbs = {'exit', 'create', 'join'}
    elif verb == 'create':
        try:
            number = command.split(' ')[1]
        except IndexError:
            errorText = 'Syntax error in {}'.format(command)
            return
        socketPrintLine(client, command)
        response = socketReadLine(client)
        if response.split(' ')[0] == 'error':
            errorText = errorMessages[response.split(' ')[2]]
        else:
            errorText = 'Successfully created game for {}'.format(number)
            response = socketReadLine(client)
            errorText = 'Successfully joined {} team. Waiting for all players'.format(
                response.split(' ')[2])
            myTeam = response.split(' ')[2]

            waitForBoard()
            startGame()

    elif verb == 'join':
        socketPrintLine(client, command)
        response = socketReadLine(client)
        if response.split(' ')[0] == 'error':
            errorText = errorMessages[response.split(' ')[2]]
        else:
            errorText = 'Successfully joined {} team'.format(
                response.split(' ')[2])
            myTeam = response.split(' ')[2]

            waitForBoard()
            startGame()

    elif verb == 'select':
        try:
            socketPrintLine(client, 'vote stone ' +
                        findStonePosition(command.split(' ')[1]))
        except Exception as e:
            errorText = str(e)

    elif verb == 'move':
        try:
            socketPrintLine(client, 'vote move ' +
                        translateChessNotation(command.split(' ')[1]))
        except Exception as e:
            errorText = str(e)

    else:
        errorText = 'No such command {}'.format(command)


def findStonePosition(stoneNumber):
    teamModifier = 0 if myTeam == 'yellow' else 10
    try:
        stoneNumber = int(stoneNumber) + teamModifier
    except ValueError:
        raise Exception('Not a number ' + stoneNumber)
    i, j = 0, 0
    for row in board:
        j = 0
        for field in row:
            if field % 100 == stoneNumber:
                return '{} {}'.format(i, j)
            j += 1
        i += 1
    return None


def translateChessNotation(chessField):
    chessField = chessField.upper()
    if chessField[0] >= 'A' and chessField[0] <= 'E':
        column = chessField[0]
        row = chessField[1]
    elif chessField[0] >= '1' and chessField[0] <= '5':
        column = chessField[1]
        row = chessField[0]
    else:
        raise Exception('wrong chess notation ' + chessField)
    row = int(row) - 1
    column = ord(column) - ord('A')
    return '{} {}'.format(row, column)


def inputFunction():
    global command
    global gameEnded
    while not gameEnded:
        c = stdscr.getch()
        if c == 10:
            textBox.clear()
            gameEnded = do(command)
            command = ''
            textBox.move(0, 0)
            textBox.refresh()
        elif c == 127 or c == 8:
            textBox.clear()
            command = command[:-1]
            textBox.move(0, 0)
            textBox.addstr(command)
            textBox.refresh()
        else:
            command += chr(c)
            textBox.addstr(chr(c))
            textBox.refresh()


def statusFunction():
    global gameEnded
    while not gameEnded:
        statusBox.clear()
        statusBox.move(0, 0)
        statusBox.addstr(textwrap.fill(hintText, curses.COLS) + '\n')
        statusBox.addstr(textwrap.fill(errorText, curses.COLS) + '\n')
        statusStr = ('Connected to ' + server if server !=
                     '' else 'Not connected')
        statusStr += '; Team ' + myTeam if myTeam != '' else ''
        statusStr += '; Rolled {}'.format(roll) if roll != -1 else ''
        statusStr += '; Votes: ' + parseVotes() if votes != {} else ''
        statusBox.addstr(textwrap.fill(statusStr, curses.COLS))
        textBox.move(0, len(command))
        statusBox.refresh()
        textBox.refresh()
        time.sleep(.5)

allowedVerbs = {'connect', 'exit'}
statusText = 'Not connected.'
hintText = 'Type `connect {address} {port}` to connect'

inputThread = threading.Thread(target=inputFunction)
inputThread.start()
statusThread = threading.Thread(target=statusFunction)
statusThread.start()
