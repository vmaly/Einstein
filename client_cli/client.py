#!/usr/bin/env python3

import curses
import socket
import threading
import time
import sys
import textwrap
import signal
import datetime
import os


def socketPrintLine(sock, message):
    sock.sendall(bytes(message + '\n', 'utf-8'))


def socketReadLine(sock):
    response = ''
    while True:
        try:
            character = sock.recv(1).decode('utf-8')
        except socket.timeout:
            pass
        if not character:
            raise IOError('disconnected')
        print(character, file=sys.stderr, end='')
        if character != '\n':
            response += character
        else:
            print('\n', file=sys.stderr)
            return response


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
    boardBox.addstr('    A   B   C   D   E\n')
    boardBox.addstr('  ╭───┬───┬───┬───┬───╮\n')
    i = 0
    for row in board:
        boardBox.addstr(' ' + str(i + 1))
        for box in row:
            boardBox.addstr('│ ')
            digit = 1 if box % 10 > 0 else 0
            colour = int(str(10 * int(box / 10) + digit), 2)
            print('{} {}|'.format(box % 10, colour), file=sys.stderr, end='\t')
            boardBox.addstr(str(box % 10) if digit !=
                            0 else ' ', curses.color_pair(colour))
            boardBox.addstr(' ')
        print('', file=sys.stderr)
        boardBox.addstr('│\n')
        if i < 4:
            boardBox.addstr('  ├───┼───┼───┼───┼───┤\n')
        i += 1
    boardBox.addstr('  ╰───┴───┴───┴───┴───╯\n')
    boardBox.refresh()


def printBoard():
    for row in board:
        for field in row:
            print('{}\t'.format(field), end='', file=sys.stderr)
        print('', file=sys.stderr)


def startGame():
    global runGameThread
    runGameThread = threading.Thread(target=safeRunGame)
    runGameThread.start()


def safeRunGame():
    global gameEnded
    global errorText
    global hintText
    global statusText
    global serverDisconnected
    try:
        waitForBoard()
        runGame()
    except (IOError, OSError):
        if not gameEnded:
            gameEnded = True
            serverDisconnected = True
    print('runGame end', file=sys.stderr)


def runGame():
    global allowedVerbs
    global votes
    global hintText
    global errorText
    global roll
    won = None
    while won is None:
        response = socketReadLine(client)
        allowedVerbs = {'exit'}
        if response.split(' ')[1] == 'active' and\
                response.split(' ')[2] == myTeam:
            errorText = 'Your move'
            response = socketReadLine(client)
            roll = int(response.split(' ')[2])
            response = socketReadLine(client)
            if response.split(' ')[3] == 'needed':
                highlightSelectables(roll)
                allowedVerbs = {'exit', 'select'}
                hintText = 'Type `select {n}` to vote for Your stone with \
number n'
            elif response.split(' ')[1] == 'game':
                won, errorText, allowedVerbs, hintText = onWin(response)
            votes = {}
            votingFinished = False
            while not votingFinished:
                response = socketReadLine(client)
                response = response.split(' ')
                if response[-1] == 'needed':
                    votes = {}
                elif response[-1] == 'selected':
                    votingFinished = True
                    votes = {}
                    selected = response[-3] + ' ' + response[-2]
                elif response[0] == 'success' and response[1] == 'vote':
                    try:
                        votes[stoneAt(response[3] + ' ' + response[4])] += 1
                    except KeyError:
                        votes[stoneAt(response[3] + ' ' + response[4])] = 1
                elif response[-1] == 'not_selected':
                    errorText = 'There was a tie. Vote again'
                    votes = {}
                elif response[0] == 'error':
                    errorText = errorMessages[response[3]]
                elif response[1] == 'game':
                    won, errorText, allowedVerbs, hintText = onWin(
                        ' '.join(response))

            response = socketReadLine(client)
            if response.split(' ')[3] == 'needed':
                highlightMoveTargets(selected)
                allowedVerbs = {'exit', 'move'}
                hintText = 'Type `move {target}` (e.g. move A2) to move vote \
for the move'
            elif response.split(' ')[1] == 'game':
                won, errorText, allowedVerbs, hintText = onWin(response)
            votes = {}
            votingFinished = False
            while not votingFinished:
                response = socketReadLine(client)
                response = response.split(' ')
                if response[3] == 'needed':
                    votes = {}
                elif response[0] == 'success' and response[1] == 'vote':
                    try:
                        votes[response[3] + ' ' + response[4]] += 1
                    except KeyError:
                        votes[response[3] + ' ' + response[4]] = 1
                elif response[-1] == 'not_moved':
                    errorText = 'There was a tie. Vote again'
                    votes = {}
                elif response[0] == 'error':
                    errorText = errorMessages[response[3]]
                elif response[4] == 'moved':
                    votingFinished = True
                    votes = {}
                    target = response[6] + ' ' + response[7]
                elif response[1] == 'game':
                    won, errorText, allowedVerbs, hintText = onWin(
                        ' '.join(response))
            moveStone(selected, target)
        elif response.split(' ')[1] == 'active':
            errorText = 'Waiting for opponent’s move'
            response = socketReadLine(client)
            if response.split(' ')[4] == 'moved':
                moveStone(' '.join(response.split(' ')[2:4]), ' '.join(
                    response.split(' ')[6:8]))
            else:
                won, errorText, allowedVerbs, hintText = onWin(response)
        elif response.split(' ')[1] == 'game':
            won, errorText, allowedVerbs, hintText = onWin(response)
    curses.endwin()
    if serverDisconnected:
        print('Server disconnected')


def onWin(response):
    winGrounds = {'corner': 'corner reaching',
                  'no_stones': 'opponent capturing',
                  'no_vote': 'opponent disconnection',
                  'disconnection': 'opponent disconnection'}
    won = response.split(' ')[3]
    errorText = '{} team won by {}.'.format(
        response.split(' ')[3].capitalize(),
        winGrounds[response.split(' ')[4]])
    allowedVerbs = {'exit', 'create', 'join'}
    hintText = 'Type `exit` to quit, `create {n}` to create a game for n \
players per team  or `join` to join an existing game'
    return won, errorText, allowedVerbs, hintText


def stoneAt(position):
    i = int(position.split(' ')[0])
    j = int(position.split(' ')[1])

    return board[i][j]


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
    for key, votesNumber in votes.items():
        try:
            votesString += translateToChessNotation(
                key) + ': ' + str(votesNumber) + ', '
        except AttributeError:
            votesString += '{}: {}, '.format(key % 10, votesNumber)
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
        return True
    elif verb == 'connect':
        address = ''
        port = ''
        try:
            address = command.split(' ')[1]
            port = command.split(' ')[2]
        except IndexError:
            if not address:
                address = defaults['server']
            port = defaults['port']
        try:
            client.settimeout(10)
            client.connect((address, int(port)))  # results
            client.settimeout(None)
        except ValueError:
            errorText = 'Port must be a number'
        except Exception as e:
            if str(e).split(' ')[1].strip(']') == '111':
                errorText = 'Server is not available at {}:{}'.format(
                    address, port)
            elif str(e).split(' ')[1].strip(']') == '-2':
                errorText = 'Name {} is not known'.format(address)
            elif str(e).split(' ')[1].strip(']') == '101':
                errorText = 'Network unreachable. Are You connected to the \
Internet?'
            elif str(e) == 'timed out':
                errorText = 'Timeout while connecting. Aren’t You behind a \
firewall?'
            else:
                errorText = str(e)
        else:
            errorText = 'Connected to game.'
            hintText = 'Type `create {n}` to create a game for n players per \
team or `join` to join an existing game'
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
        elif response.split(' ')[0] == 'success':
            errorText = 'Successfully created game for {}'.format(number)
            response = socketReadLine(client)
            errorText = 'Successfully joined {} team. Waiting for all \
players'.format(response.split(' ')[2])
            myTeam = response.split(' ')[2]

            startGame()

    elif verb == 'join':
        socketPrintLine(client, command)
        response = socketReadLine(client)
        if response.split(' ')[0] == 'error':
            errorText = errorMessages[response.split(' ')[2]]
        elif response.split(' ')[0] == 'success':
            errorText = 'Successfully joined {} team'.format(
                response.split(' ')[2])
            myTeam = response.split(' ')[2]

            startGame()

    elif verb == 'select':
        arg = ''
        try:
            arg = command.split(' ')[1]
        except IndexError:
            errorText = 'Syntax error in {}'.format(command)
            return
        try:
            socketPrintLine(client, 'vote stone ' + findStonePosition(arg))
        except ValueError as exception:
            errorText = str(exception)
        except TypeError:
            errorText = 'No stone {} on the board'.format(arg)

    elif verb == 'move':
        arg = ''
        try:
            arg = command.split(' ')[1]
        except IndexError:
            errorText = 'Syntax error in {}'.format(command)
        try:
            socketPrintLine(client, 'vote move ' + translateChessNotation(arg))
        except ValueError as exception:
            errorText = str(exception)

    else:
        errorText = 'No such command {}'.format(command)


def findStonePosition(stoneNumber):
    teamModifier = 0 if myTeam == 'yellow' else 10
    try:
        stoneNumber = int(stoneNumber) + teamModifier
    except ValueError:
        raise ValueError('Not a number ' + stoneNumber)
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
    if len(chessField) < 2:
        raise ValueError('Wrong chess notation ' + chessField)
    if 'E' >= chessField[0] >= 'A' and '5' >= chessField[1] >= '1':
        column = chessField[0]
        row = chessField[1]
    elif 'E' >= chessField[1] >= 'A' and '5' >= chessField[0] >= '1':
        column = chessField[1]
        row = chessField[0]
    else:
        raise ValueError('Wrong chess notation ' + chessField)
    row = int(row) - 1
    column = ord(column) - ord('A')
    return '{} {}'.format(row, column)


def inputFunction():
    global command
    global gameEnded
    global serverDisconnected
    while not gameEnded:
        try:
            character = stdscr.get_wch()
        except curses.error:
            pass
        else:
            print('input ' + str(character), file=sys.stderr)
            if character == '\u001b':
                stdscr.get_wch()
                stdscr.get_wch()
            if character == chr(10):
                textBox.clear()
                try:
                    gameEnded = do(command)
                except (IOError, OSError):
                    gameEnded = True
                    serverDisconnected = True
                finally:
                    command = ''
                    textBox.move(0, 0)
                    textBox.refresh()
            elif character == chr(127) or character == chr(8):
                textBox.clear()
                command = command[:-1]
                textBox.move(0, 0)
                textBox.addstr(command)
                textBox.refresh()
            elif 'z' >= character >= 'a' or 'Z' >= character >= 'A'\
                    or '9' >= character >= '0' or character in{' ', '.', ':', '-'}:
                command += character
                textBox.addstr(character)
                textBox.refresh()
    try:
        client.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    else:
        client.close()
    print('input ended', file=sys.stderr)
    curses.endwin()
    if serverDisconnected:
        print('Server disconnected')


def statusFunction():
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
    print('status ended', file=sys.stderr)
    curses.endwin()
    os.environ['TERM'] = term
    if serverDisconnected:
        print('Server disconnected')


def onErrorExit(signal, frame):
    global gameEnded
    gameEnded = True
    try:
        client.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    else:
        client.close()


def initialise():
    global errorMessages
    global allowedVerbs
    global errorText
    global statusText
    global hintText
    global board
    global votes

    global command
    global myTeam
    global server
    global roll
    global gameEnded

    global statusBox
    global boardBox
    global textBox

    global client
    global stdscr
    global serverDisconnected

    global defaults
    global term

    defaults = {}

    try:
        with open('defaults.conf') as defaultsFile:
            for line in defaultsFile:
                splitLine = line.split('=')
                try:
                    defaults[splitLine[0].strip(' \n\r')] =\
                        splitLine[1].strip(' \n\r')
                except IndexError:
                    pass
    except IOError:
        with open('defaults.conf', 'w') as defaultFile:
            defaultFile.write('server=localhost\nport=2500\n')
            defaults['server'] = 'localhost'
            defaults['port'] = '2500'

    serverDisconnected = False

    allowedVerbs = {'connect', 'exit'}
    errorText = ''
    statusText = 'Not connected.'
    hintText = 'Type `connect {address} {port}` to connect'

    command = ''
    myTeam = ''
    server = ''
    roll = -1
    votes = {}

    term = os.environ['TERM']
    os.environ['TERM'] = 'xterm-256color'

    gameEnded = False

    try:
        stdscr = curses.initscr()
    except curses.error as exception:
        try:
            os.environ['TERM'] = 'xterm-16color'
        except:
            if str(exception) == 'setupterm: could not find terminal':
                print('You need a terminal that supports at least 16 colours')
            else:
                print(str(exception))
            quit()
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

    stdscr.timeout(500)
    signal.signal(signal.SIGINT, onErrorExit)

    sys.stderr = open('einstein_cli_{}.log'.format(datetime.datetime.now()),
                      'w')

    errorMessages = {'already_exists': 'Game already exists on server',
                     'invalid_count': 'Wrong number of players',
                     'full': 'All players are already in game',
                     'not_started': 'Game has not started yet',
                     'already_joined': 'You have already joined the game',
                     'not_selectable': 'The stone You chose is not selectable',
                     'not_your_turn': 'It’s not Your turn',
                     'not_needed': 'Voting is not needed',
                     'invalid': 'Stone cannot be moved there',
                     'no_vote': 'You didn’t vote',
                     'already_voted': 'You’ve already voted in this turn'}


initialise()

inputThread = threading.Thread(target=inputFunction)
inputThread.start()
statusThread = threading.Thread(target=statusFunction)
statusThread.start()
