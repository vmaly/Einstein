#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netdb.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/epoll.h>
#include <errno.h>
#include <algorithm>
#include <sstream>
#include <iostream>
#include <cstdlib>
#include <vector>
#include <set>
#include <utility>
#include <thread>
#include <chrono>
#include <future>

#define MAXEVENTS 64

using namespace std;

int board[5][5];
int numberOfPlayers = 0;
int numberOfConnectedPlayers = 0;
bool gameCreated = false;
bool gameStarted = false;
vector<int> yellowTeam;
vector<int> blueTeam;
string strArray[10];
string activeTeam = "none";
int numberRolled = 0;
vector<pair<int, int>> possibleStones;
pair<int, int> selectedStone;
vector<pair<int, int>> possibleMoves;
pair<int, int> votesForStone;
int votesForMove[3];
bool voteStoneNeeded = false;
bool voteMoveNeeded = false;
bool gameEnded = false;
int voteNumber = 0;
const int maxNumberOfPlayers = 10;
set<int> playerVotes;
int numberOfTies = 0;
const int voteTimeLimit = 15;
thread::id mainThreadID;

void endVoteForMove();

void endVoteForStone();

void startTurn(string color);

void initializeAll();

int roll(){
    srand(time(0));
    return rand() % 6 + 1;
}

void setPossibleStones(){
    //TODO valgrind Conditional jump or move depends on uninitialised value(s)
    bool myNumbers[6];
    for(int i = 0; i < 6; ++i){
        myNumbers[i] = 0;
    }
    for(int i = 0; i < 5; ++i){
        for(int j = 0; j < 5; ++j){
            if(activeTeam == "yellow"){
                if(board[i][j] > 0 && board[i][j] < 7){
                    myNumbers[board[i][j]] = true;
                }
            }
            else{
                if(board[i][j] > 10 && board[i][j] < 17){
                    myNumbers[board[i][j] - 10] = true;
                }
            }
        }
    }
    possibleStones.clear();
    if(myNumbers[numberRolled]){
        for(int i = 0; i < 5; ++i){
            for(int j = 0; j < 5; ++j){
                if(activeTeam == "yellow"){
                    if(board[i][j] == numberRolled){
                        pair<int, int> stone = make_pair(i, j);
                        possibleStones.push_back(stone);
                    }
                }
                else{
                    if(board[i][j] - 10 == numberRolled){
                        pair<int, int> stone = make_pair(i, j);
                        possibleStones.push_back(stone);
                    }
                }
            }
        }
    }
    else{
        int n = numberRolled + 1;
        while(n < 7){
            if(myNumbers[n]){
                for(int i = 0; i < 5; ++i){
                    for(int j = 0; j < 5; ++j){
                        if(activeTeam == "yellow"){
                            if(board[i][j] == n){
                                pair<int, int> stone = make_pair(i, j);
                                possibleStones.push_back(stone);
                            }
                        }
                        else{
                            if(board[i][j] - 10 == n){
                                pair<int, int> stone = make_pair(i, j);
                                possibleStones.push_back(stone);
                            }
                        }
                    }
                }
                break;
            }
            ++n;
        }
        n = numberRolled - 1;
        while(n > 0){
            if(myNumbers[n]){
                for(int i = 0; i < 5; ++i){
                    for(int j = 0; j < 5; ++j){
                        if(activeTeam == "yellow"){
                            if(board[i][j] == n){
                                pair<int, int> stone = make_pair(i, j);
                                possibleStones.push_back(stone);
                            }
                        }
                        else{
                            if(board[i][j] - 10 == n){
                                pair<int, int> stone = make_pair(i, j);
                                possibleStones.push_back(stone);
                            }
                        }
                    }
                }
                break;
            }
            --n;
        }
    }
}

void writeN(int sender, string msg){
    char a[100];
    int i;
    for(i = 0; i < msg.size(); ++i){
        a[i] = msg[i];
    }
    if(write(sender, a, msg.size()) == -1){
        perror("errorCode");
    }
}

void sendToAll(string message){
    for(int i = 0; i < yellowTeam.size(); ++i){
        writeN(yellowTeam[i], message);
    }
    for(int j = 0; j < blueTeam.size(); ++j){
        writeN(blueTeam[j], message);
    }
}

void sendToActiveTeam(string message){
    if(activeTeam == "yellow"){
        for(int i = 0; i < yellowTeam.size(); ++i){
            writeN(yellowTeam[i], message);
        }
    }
    else if(activeTeam == "blue"){
        for(int i = 0; i < blueTeam.size(); ++i){
            writeN(blueTeam[i], message);
        }
    }
}

void createBoard(){
    srand(time(0));
    for(int i = 0; i < 5; ++i){
        for(int j = 0; j < 5; ++j){
            board[i][j] = 0;
        }
    }
    {
        int tab[6] = {1, 2, 3, 4, 5, 6};
        random_shuffle(tab, tab + 5);
        board[0][0] = tab[0];
        board[0][1] = tab[1];
        board[0][2] = tab[2];
        board[1][0] = tab[3];
        board[1][1] = tab[4];
        board[2][0] = tab[5];
    }
    {
        int tab[6] = {11, 12, 13, 14, 15, 16};
        random_shuffle(tab, tab + 5);
        board[4][4] = tab[0];
        board[4][3] = tab[1];
        board[4][2] = tab[2];
        board[3][4] = tab[3];
        board[3][3] = tab[4];
        board[2][4] = tab[5];
    }
}

void printBoard(){
    for(int i = 0; i < 5; ++i){
        for(int j = 0; j < 5; ++j){
            cout << board[i][j] << " ";
        }
        cout << endl;
    }
}

string intToString(int i){
    stringstream ss;
    string s;
    ss << i;
    ss >> s;
    if(ss.fail()){
        return "e";
        //TODO e - error
    } else{
        return s;
    }
}

int stringToInt(string s){
    stringstream ss(s);
    int i;
    ss >> i;
    if(ss.fail()){
        return -1;
    } else{
        return i;
    }
}

void messageToStringArray(char message[]){
    stringstream ss(message);
    int i = 0;
    string tmp;
    while(ss >> tmp && i < 10){
        strArray[i] = tmp;
        ++i;
    }
    while(i < 10){
        strArray[i].clear();
        ++i;
    }
}

string boardToString(){
    string b = "board";
    for(int i = 0; i < 5; ++i){
        for(int j = 0; j < 5; ++j){
            b += " ";
            b += intToString(board[i][j]);
        }
    }
    return b;
}

void sendRolled(){
    string message = "success rolled ";
    message += intToString(numberRolled);
    message += '\n';
    sendToActiveTeam(message);
}

void sendActiveTeam(){
    string message;
    if(activeTeam == "yellow"){
        message = "success active yellow\n";
    }
    else{
        message = "success active blue\n";
    }
    sendToAll(message);
}

void sendStoneVote(bool needed){
    string message = "success vote stone ";
    if(needed){
        message += "needed\n";
    }
    else{
        message += "not_needed\n";
    }
    sendToActiveTeam(message);
}

void sendMoveVote(bool needed){
    string message = "success vote move ";
    if(needed){
        message += "needed\n";
    }
    else{
        message += "not_needed\n";
    }
    sendToActiveTeam(message);
}

void sendStoneSelected(bool selected){
    string message = "success stone ";
    if(selected){
        message += intToString(selectedStone.first);
        message += " ";
        message += intToString(selectedStone.second);
        message += " selected\n";
    }
    else{
        message += "not_selected\n";
    }
    sendToActiveTeam(message);
}

void sendMoveDone(pair<int, int> destination){
    string message = "success stone ";
    message += intToString(selectedStone.first);
    message += " ";
    message += intToString(selectedStone.second);
    message += " moved to ";
    message += intToString(destination.first);
    message += " ";
    message += intToString(destination.second);
    message += " by ";
    message += activeTeam;
    message += '\n';
    sendToAll(message);
}

void sendMoveNotDone(){
    string message = "success stone ";
    message += intToString(selectedStone.first);
    message += " ";
    message += intToString(selectedStone.second);
    message += " not_moved\n";
    sendToActiveTeam(message);
}

void setPossibleMoves(){
    possibleMoves.clear();
    if(activeTeam == "yellow"){
        if(selectedStone.first < 4){
            pair<int, int> p = make_pair(selectedStone.first + 1, selectedStone.second);
            possibleMoves.push_back(p);
        }
        if(selectedStone.second < 4){
            pair<int, int> p = make_pair(selectedStone.first, selectedStone.second + 1);
            possibleMoves.push_back(p);
        }
        if(possibleMoves.size() == 2){
            pair<int, int> p = make_pair(selectedStone.first + 1, selectedStone.second + 1);
            possibleMoves.push_back(p);
        }
    }
    else{
        if(selectedStone.first > 0){
            pair<int, int> p = make_pair(selectedStone.first - 1, selectedStone.second);
            possibleMoves.push_back(p);
        }
        if(selectedStone.second > 0){
            pair<int, int> p = make_pair(selectedStone.first, selectedStone.second - 1);
            possibleMoves.push_back(p);
        }
        if(possibleMoves.size() == 2){
            pair<int, int> p = make_pair(selectedStone.first - 1, selectedStone.second - 1);
            possibleMoves.push_back(p);
        }
    }
}

void sendEndGame(string winner, string reason){
    cout << winner << " won " << "because of " << reason << endl;
    string message = "success game ended ";
    message += winner;
    message += " ";
    message += reason;
    message += '\n';
    sendToAll(message);
}

void endGame(string winner, string reason){
    sendEndGame(winner, reason);
    //gameEnded = true;
    initializeAll();
    if(this_thread::get_id() == mainThreadID){
        //throw 42;
    }
    else{
        cout << "not main thread" << endl;
        pthread_cancel(pthread_self());
    }
}

void checkIfEndGame(){
    if(board[0][0] > 10){
        endGame("blue", "corner");
    }
    if(board[4][4] > 0 && board[4][4] < 7){
        endGame("yellow", "corner");
    }
    bool yellowStonesOnTheBoard = false;
    bool blueStonesOnTheBoard = false;
    for(int i = 0; i < 5; ++i){
        for(int j = 0; j < 5; ++j){
            if(board[i][j] > 0){
                if(board[i][j] > 10){
                    blueStonesOnTheBoard = true;
                }
                else{
                    yellowStonesOnTheBoard = true;
                }
            }
        }
    }
    if(!blueStonesOnTheBoard){
        endGame("yellow", "no_stones");
    }
    if(!yellowStonesOnTheBoard){
        endGame("blue", "no_stones");
    }
}

void changeTurn(){
    if(activeTeam == "yellow"){
        startTurn("blue");
    }
    else{
        startTurn("yellow");
    }
}

void doMove(pair<int, int> destination){
    int selectedStoneNumber = board[selectedStone.first][selectedStone.second];
    board[selectedStone.first][selectedStone.second] = 0;
    board[destination.first][destination.second] = selectedStoneNumber;
    cout << "moved " << selectedStone.first << " " << selectedStone.second
    << " to " << destination.first << " " << destination.second << " by " << activeTeam << endl;
    sendMoveDone(destination);
    checkIfEndGame();
    numberOfTies = 0;
    changeTurn();
}

void sendErrorNoVote(){
    if(activeTeam == "yellow"){
        for(int i = 0; i < yellowTeam.size(); ++i){
            if(playerVotes.find(yellowTeam[i]) == playerVotes.end()){
                if(voteMoveNeeded){
                    writeN(yellowTeam[i], "error vote move no_vote\n");
                }
                else{
                    writeN(yellowTeam[i], "error vote stone no_vote\n");
                }
            }
        }
    }
    else{
        for(int i = 0; i < blueTeam.size(); ++i){
            if(playerVotes.find(blueTeam[i]) == playerVotes.end()){
                writeN(blueTeam[i], "error vote move no_vote\n");
            }
            else{
                writeN(blueTeam[i], "error vote stone no_vote\n");
            }
        }
    }
}

void delay(int seconds, int currentVoteNumber){
    this_thread::sleep_for(chrono::seconds(seconds));
    if(currentVoteNumber == voteNumber){
        cout << "time is up" << endl;
        sendErrorNoVote();
        if(voteMoveNeeded){
            endVoteForMove();
        }
        else{
            endVoteForStone();
        }
    }
}

void delayAndCheckIfVoted(int seconds = voteTimeLimit){
    ++voteNumber;
    cout << "vote number: " << voteNumber << endl;
    thread(delay, seconds, voteNumber).detach();
}

void startMoveVote(){
    for(int i = 0; i < 3; ++i){
        votesForMove[i] = 0;
    }
    playerVotes.clear();
    cout << "vote move needed" << endl;
    sendMoveVote(true);
    delayAndCheckIfVoted();
}

void startStoneVote(){
    votesForStone.first = 0;
    votesForStone.second = 0;
    playerVotes.clear();
    cout << "vote stone needed" << endl;
    sendStoneVote(true);
    cout << "possible stones: " << endl;
    for(int i = 0; i < possibleStones.size(); ++i){
        cout << possibleStones[i].first << " " << possibleStones[i].second << endl;
    }
    delayAndCheckIfVoted();
}

void selectStone(pair<int, int> stone){
    selectedStone.first = stone.first;
    selectedStone.second = stone.second;
    cout << "selected stone " << selectedStone.first << " " << selectedStone.second << endl;
    sendStoneSelected(true);
    numberOfTies = 0;
    voteMoveNeeded = false;
    setPossibleMoves();
    cout << "possible moves: " << endl;
    for(int i = 0; i < possibleMoves.size(); ++i){
        cout << possibleMoves[i].first << " " << possibleMoves[i].second << endl;
    }
    if(possibleMoves.size() > 1){
        voteMoveNeeded = true;
    }
    if(voteMoveNeeded){
        startMoveVote();
    }
    else{
        cout << "vote move not needed" << endl;
        sendMoveVote(false);
        doMove(possibleMoves[0]);
    }
}

void startTurn(string color){
    activeTeam = color;
    cout << color << " turn" << endl;
    printBoard();
    sendActiveTeam();
    numberRolled = roll();
    cout << "rolled " << numberRolled << endl;
    sendRolled();
    setPossibleStones();
    voteStoneNeeded = false;
    voteMoveNeeded = false;
    if(possibleStones.size() > 1){
        voteStoneNeeded = true;
    }
    if(voteStoneNeeded){
        startStoneVote();
    }
    else{
        cout << "vote stone not needed" << endl;
        sendStoneVote(false);
        selectStone(possibleStones[0]);

    }
}

void sendGameStarted(){
    string message = "success game started\n";
    sendToAll(message);
}

void sendBoard(){
    string message = "success ";
    message += boardToString();
    message += '\n';
    sendToAll(message);
}

void startGame(){
    gameStarted = true;
    cout << "game starts" << endl;
    sendGameStarted();
    sendBoard();
    startTurn("yellow");
}

bool alreadyJoined(int sender){
    for(int i = 0; i < yellowTeam.size(); ++i){
        if(sender == yellowTeam[i]){
            return true;
        }
    }
    for(int i = 0; i < blueTeam.size(); ++i){
        if(sender == blueTeam[i]){
            return true;
        }
    }
    return false;
}

void joinIfPossible(int sender){
    if(alreadyJoined(sender)){
        cout << "player already joined" << endl;
        writeN(sender, "error join already_joined\n");
    }
    else{
        if(numberOfConnectedPlayers < 2 * numberOfPlayers){
            if(yellowTeam.size() < numberOfPlayers){
                yellowTeam.push_back(sender);
                cout << "player joined yellow team" << endl;
                writeN(sender, "success join yellow\n");
            }
            else{
                blueTeam.push_back(sender);
                cout << "player joined blue team" << endl;
                writeN(sender, "success join blue\n");
            }
            ++numberOfConnectedPlayers;
            if(numberOfConnectedPlayers == 2 * numberOfPlayers){
                startGame();
            }
        }
        else{
            cout << "both teams are full" << endl;
            writeN(sender, "error join full\n");
        }
    }
}

void initializeAll(){
    createBoard();
    numberOfPlayers = 0;
    numberOfConnectedPlayers = 0;
    gameCreated = false;
    gameStarted = false;
    yellowTeam = vector<int>();
    blueTeam = vector<int>();
    activeTeam = "none";
    numberRolled = 0;
    possibleStones = vector<pair<int, int>>();
    possibleMoves = vector<pair<int, int>>();
    voteStoneNeeded = false;
    voteMoveNeeded = false;
    gameEnded = false;
    voteNumber = 0;
    playerVotes = set<int>();
    numberOfTies = 0;
}

void createGame(int sender){
    initializeAll();
    numberOfPlayers = stringToInt(strArray[1]);
    if(numberOfPlayers < 1 || numberOfPlayers > maxNumberOfPlayers){
        cout << "invalid player count" << endl;
        writeN(sender, "error create invalid_count\n");
    }
    else{
        gameCreated = true;
        cout << "game created for " << numberOfPlayers << " players" << endl;
        writeN(sender, "success create\n");
        joinIfPossible(sender);
    }
}

bool isHisTurn(int sender){
    if(activeTeam == "yellow"){
        for(int i = 0; i < yellowTeam.size(); ++i){
            if(sender == yellowTeam[i]){
                return true;
            }
        }
    }
    else{
        for(int i = 0; i < blueTeam.size(); ++i){
            if(sender == blueTeam[i]){
                return true;
            }
        }
    }
    return false;
}

void setPlayerVote(int sender){
    playerVotes.insert(sender);
}

void doRandomMove(){
    doMove(possibleMoves[rand() % 3]);
}

void endVoteForMove(){
    cout << "voting finished" << endl;
    if(votesForMove[0] > votesForMove[1] && votesForMove[0] > votesForMove[2]){
        doMove(possibleMoves[0]);
        //TODO voteMoveNeeded = false;
    }
    else if(votesForMove[1] > votesForMove[0] && votesForMove[1] > votesForMove[2]){
        doMove(possibleMoves[1]);
        //TODO voteMoveNeeded = false;
    }
    else if(votesForMove[2] > votesForMove[0] && votesForMove[2] > votesForMove[1]){
        doMove(possibleMoves[2]);
        //TODO voteMoveNeeded = false;
    }
    else{
        if(votesForMove[0] + votesForMove[1] + votesForMove[2] == 0){
            cout << "there was no votes for move" << endl;
        }
        else{
            cout << "tie" << endl;
        }
        ++numberOfTies;
        sendMoveNotDone();
        if(numberOfTies == 3){
            doRandomMove();
        }
        else{
            startMoveVote();
        }
    }
}

void checkIfVoteForMoveCanEnd(){
    if(activeTeam == "yellow"){
        if(votesForMove[0] + votesForMove[1] + votesForMove[2] == yellowTeam.size()){
            endVoteForMove();
        }
    }
    else{
        if(votesForMove[0] + votesForMove[1] + votesForMove[2] == blueTeam.size()){
            endVoteForMove();
        }
    }
}

void voteForMove(int sender, pair<int, int> move){
    if(playerVotes.find(sender) == playerVotes.end()){
        string message = "success vote move ";
        message += intToString(move.first);
        message += " ";
        message += intToString(move.second);
        message += '\n';
        bool correctMove = false;
        for(int j = 0; j < 3; ++j){
            if(possibleMoves[j].first == move.first && possibleMoves[j].second == move.second){
                ++votesForMove[j];
                setPlayerVote(sender);
                cout << "voted for move " << move.first << " " << move.second << endl;
                correctMove = true;
                sendToActiveTeam(message);
                break;
            }
        }
        if(!correctMove){
            cout << "failed to vote for move " << move.first << " " << move.second << endl;
            writeN(sender, "error vote move invalid\n");
        }
        cout << "current votes: ";
        for(int k = 0; k < 3; ++k){
            cout << votesForMove[k] << " ";
        }
        cout << endl;
        checkIfVoteForMoveCanEnd();
    }
    else{
        cout << "player already voted" << endl;
        writeN(sender, "error vote move already_voted\n");
    }
}

void selectRandomStone(){
    selectStone(possibleStones[rand() % 2]);
}

void endVoteForStone(){
    cout << "voting finished" << endl;
    if(votesForStone.first > votesForStone.second){
        selectStone(possibleStones[0]);
        //TODO voteStoneNeeded = false;
    }
    else if(votesForStone.first < votesForStone.second){
        selectStone(possibleStones[1]);
        //TODO voteStoneNeeded = false;

    }
    else{
        if(votesForStone.first + votesForStone.second == 0){
            cout << "there was no votes for stone" << endl;
        }
        else{
            cout << "tie" << endl;
        }
        ++numberOfTies;
        sendStoneSelected(false);
        if(numberOfTies == 3){
            selectRandomStone();
        }
        else{
            startStoneVote();
        }
    }
}

void checkIfVoteForStoneCanEnd(){
    if(activeTeam == "yellow"){
        if(votesForStone.first + votesForStone.second == yellowTeam.size()){
            endVoteForStone();
        }
    }
    else{
        if(votesForStone.first + votesForStone.second == blueTeam.size()){
            endVoteForStone();
        }
    }
}

void voteForStone(int sender, pair<int, int> stone){
    if(playerVotes.find(sender) == playerVotes.end()){
        string message = "success vote stone ";
        message += intToString(stone.first);
        message += " ";
        message += intToString(stone.second);
        message += '\n';
        if(possibleStones[0].first == stone.first && possibleStones[0].second == stone.second){
            ++votesForStone.first;
            setPlayerVote(sender);
            cout << "voted for stone " << stone.first << " " << stone.second << endl;
            sendToActiveTeam(message);
        }
        else if(possibleStones[1].first == stone.first && possibleStones[1].second == stone.second){
            ++votesForStone.second;
            setPlayerVote(sender);
            cout << "voted for stone " << stone.first << " " << stone.second << endl;
            sendToActiveTeam(message);
        }
        else{
            cout << "failed to vote for stone " << stone.first << " " << stone.second << endl;
            writeN(sender, "error vote stone not_selectable\n");
        }
        checkIfVoteForStoneCanEnd();
        cout << "current votes: " << votesForStone.first << " " << votesForStone.second << endl;
    }
    else{
        cout << "player already voted" << endl;
        writeN(sender, "error vote stone already_voted\n");
    }
}

void handleMessage(char message[], int sender){
    messageToStringArray(message);
    if(gameEnded){
        cout << "gameEnded" << endl;
    }
    if(strArray[0] == "create"){
        if(!gameCreated){
            createGame(sender);
        }
        else{
            cout << "game already exists" << endl;
            writeN(sender, "error create already_exists\n");
            joinIfPossible(sender);
        }
    }
    else if(strArray[0] == "join"){
        if(gameCreated){
            joinIfPossible(sender);
        }
        else{
            cout << "game hasn't started yet" << endl;
            writeN(sender, "error join not_started\n");
        }
    }
    else if(strArray[0] == "vote"){
        if(!gameStarted){
            cout << "game hasn't started yet" << endl;
            writeN(sender, "error game not_started\n");
        }//else if not your turn
        else if(isHisTurn(sender)){
            if(strArray[1] == "stone"){
                if(voteStoneNeeded){
                    int x = stringToInt(strArray[2]);
                    int y = stringToInt(strArray[3]);
                    pair<int, int> stone = make_pair(x, y);
                    voteForStone(sender, stone);
                }
                else{
                    cout << "vote for stone is not needed at this moment" << endl;
                    writeN(sender, "error vote stone not_needed\n");
                }
            }
            else if(strArray[1] == "move"){
                if(voteMoveNeeded){
                    int x = stringToInt(strArray[2]);
                    int y = stringToInt(strArray[3]);
                    pair<int, int> move = make_pair(x, y);
                    voteForMove(sender, move);
                }
                else{
                    cout << "vote for move is not needed at this moment" << endl;
                    writeN(sender, "error vote move not_needed\n");
                }
            }
            else{
                cout << "unknown request" << endl;
                writeN(sender, "error request_unknown\n");
            }
        }
        else{
            cout << "it is not player turn" << endl;
            writeN(sender, "error vote move not_your_turn\n");
        }
    }
    else{
        cout << "unknown request" << endl;
        writeN(sender, "error request_unknown\n");
    }
}

void removeFromTeamIfPossible(int sender){
    for(int i = 0; i < yellowTeam.size(); ++i){
        if(sender == yellowTeam[i]){
            yellowTeam.erase(yellowTeam.begin() + i);
            --numberOfConnectedPlayers;
            cout << "deleted " << sender << " from yellow team" << endl;
            break;
        }
    }
    for(int i = 0; i < blueTeam.size(); ++i){
        if(sender == blueTeam[i]){
            blueTeam.erase(blueTeam.begin() + i);
            --numberOfConnectedPlayers;
            cout << "deleted " << sender << " from blue team" << endl;
            break;
        }
    }
    if(gameStarted){
        if(blueTeam.size() == 0){
            endGame("yellow", "disconnection");
        }
        else if(yellowTeam.size() == 0){
            endGame("blue", "disconnection");
        }
    }
}

static int make_socket_non_blocking(int sfd){
    int flags, s;

    flags = fcntl(sfd, F_GETFL, 0);
    if(flags == -1){
        perror("fcntl");
        return -1;
    }

    flags |= O_NONBLOCK;
    s = fcntl(sfd, F_SETFL, flags);
    if(s == -1){
        perror("fcntl");
        return -1;
    }

    return 0;
}

static int create_and_bind(char *port){
    struct addrinfo hints;
    struct addrinfo *result, *rp;
    int s, sfd;

    memset(&hints, 0, sizeof(struct addrinfo));
    hints.ai_family = AF_UNSPEC;     /* Return IPv4 and IPv6 choices */
    hints.ai_socktype = SOCK_STREAM; /* We want a TCP socket */
    hints.ai_flags = AI_PASSIVE;     /* All interfaces */

    s = getaddrinfo(NULL, port, &hints, &result);
    if(s != 0){
        fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(s));
        return -1;
    }

    for(rp = result; rp != NULL; rp = rp->ai_next){
        sfd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if(sfd == -1)
            continue;

        //setting SO_REUSEADDR so that immediate restart of a server is possible
        int option = 1;
        setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &option, sizeof(option));

        s = bind(sfd, rp->ai_addr, rp->ai_addrlen);
        if(s == 0){
            /* We managed to bind successfully! */
            break;
        }

        close(sfd);
    }

    if(rp == NULL){
        fprintf(stderr, "Could not bind\n");
        return -1;
    }

    freeaddrinfo(result);

    return sfd;
}

int main(int argc, char *argv[]){
    cout << "start" << endl;
    mainThreadID = this_thread::get_id();
    int sfd, s;
    int efd;
    struct epoll_event event;
    struct epoll_event *events;

    if(argc != 2){
        fprintf(stderr, "Usage: %s [port]\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    sfd = create_and_bind(argv[1]);
    if(sfd == -1)
        abort();

    s = make_socket_non_blocking(sfd);
    if(s == -1)
        abort();

    s = listen(sfd, SOMAXCONN);
    if(s == -1){
        perror("listen");
        abort();
    }

    efd = epoll_create1(0);
    if(efd == -1){
        perror("epoll_create");
        abort();
    }

    event.data.fd = sfd;
    event.events = EPOLLIN | EPOLLET;
    //TODO epoll_ctl valgrind error
    s = epoll_ctl(efd, EPOLL_CTL_ADD, sfd, &event);
    if(s == -1){
        perror("epoll_ctl");
        abort();
    }

    /* Buffer where events are returned */
    events = (epoll_event *)calloc(MAXEVENTS, sizeof event);

    /* The event loop */
    while(!gameEnded){
        int n, i;

        n = epoll_wait(efd, events, MAXEVENTS, -1);
        for(i = 0; i < n; i++){
            if((events[i].events & EPOLLERR) ||
               (events[i].events & EPOLLHUP) ||
               (!(events[i].events & EPOLLIN))){
                /* An error has occured on this fd, or the socket is not
                   ready for reading (why were we notified then?) */
                fprintf(stderr, "epoll error\n");
                close(events[i].data.fd);
                removeFromTeamIfPossible(events[i].data.fd);
                continue;
            }

            else if(sfd == events[i].data.fd){
                /* We have a notification on the listening socket, which
                   means one or more incoming connections. */
                while(1){
                    struct sockaddr in_addr;
                    socklen_t in_len;
                    int infd;
                    char hbuf[NI_MAXHOST], sbuf[NI_MAXSERV];

                    in_len = sizeof in_addr;
                    infd = accept(sfd, &in_addr, &in_len);

                    if(infd == -1){
                        if((errno == EAGAIN) ||
                           (errno == EWOULDBLOCK)){
                            /* We have processed all incoming
                               connections. */
                            break;
                        } else{
                            perror("accept");
                            break;
                        }
                    }

                    s = getnameinfo(&in_addr, in_len,
                                    hbuf, sizeof hbuf,
                                    sbuf, sizeof sbuf,
                                    NI_NUMERICHOST | NI_NUMERICSERV);
                    if(s == 0){
                        printf("Accepted connection on descriptor %d "
                                       "(host=%s, port=%s)\n", infd, hbuf, sbuf);
                    }

                    /* Make the incoming socket non-blocking and add it to the
                       list of fds to monitor. */
                    s = make_socket_non_blocking(infd);
                    if(s == -1)
                        abort();

                    event.data.fd = infd;
                    event.events = EPOLLIN | EPOLLET;
                    //TODO epoll_ctl valgrind error
                    s = epoll_ctl(efd, EPOLL_CTL_ADD, infd, &event);
                    if(s == -1){
                        perror("epoll_ctl");
                        abort();
                    }
                }
                continue;
            } else{
                /* We have data on the fd waiting to be read. Read and
                   display it. We must read whatever data is available
                   completely, as we are running in edge-triggered mode
                   and won't get a notification again for the same
                   data. */
                int done = 0;

                while(!gameEnded){
                    ssize_t count;
                    char buf[512];

                    count = read(events[i].data.fd, buf, sizeof buf);
                    if(count == -1){
                        /* If errno == EAGAIN, that means we have read all
                           data. So go back to the main loop. */
                        if(errno != EAGAIN){
                            perror("read");
                            done = 1;
                        }
                        break;
                    } else if(count == 0){
                        /* End of file. The remote has closed the
                           connection. */
                        done = 1;
                        break;
                    }
                    /* Write the buffer to standard output */
                    s = write(1, buf, count);
                    handleMessage(buf, events[i].data.fd);
                    if(s == -1){
                        perror("write");
                        abort();
                    }
                }

                if(done){
                    printf("Closed connection on descriptor %d\n",
                           events[i].data.fd);

                    /* Closing the descriptor will make epoll remove it
                       from the set of descriptors which are monitored. */
                    close(events[i].data.fd);
                    removeFromTeamIfPossible(events[i].data.fd);
                }
            }
        }
    }

    free(events);

    close(sfd);

    return EXIT_SUCCESS;
}
