package ml.adamsprogs.einsteinplaysnodice.games;

import android.support.annotation.NonNull;
import android.graphics.Point;
import android.util.DisplayMetrics;
import android.widget.*;

import java.util.Map;
import java.util.NoSuchElementException;

import ml.adamsprogs.einsteinplaysnodice.R;
import ml.adamsprogs.einsteinplaysnodice.activities.BoardActivity;
import ml.adamsprogs.einsteinplaysnodice.components.*;

import static ml.adamsprogs.einsteinplaysnodice.utilities.Utilities.*;

public abstract class ServerGame implements Player.OnRollListener, Board.OnStoneMoved {
    protected boolean einStein = false;

    protected Board board;

    protected Player currentPlayer;
    protected Player waitingPlayer;

    private BoardActivity context;

    private OnWinListener onWinListener;
    private OnErrorExit onErrorExit;

    public ServerGame(BoardActivity context, int startPlayer) {
        this.context = context;

        createBoard();
        createPlayers(startPlayer);
        setSizes();

        attachInterfaces();
    }

    private void createBoard() {
        board = new Board(this, (ImageView) context.findViewById(R.id.board));
    }

    protected void createPlayers(int startPlayer) {
        int[] dieImages = {R.id.dieLight, R.id.dieDark};

        currentPlayer = new Player(this, startPlayer, (ImageView) context.findViewById(dieImages[startPlayer]));
        waitingPlayer = new Player(this, opponent(startPlayer), (ImageView) context.findViewById(dieImages[opponent(startPlayer)]));
    }

    protected void setSizes() {
        DisplayMetrics metrics = new DisplayMetrics();
        context.getWindowManager().getDefaultDisplay().getMetrics(metrics);
        int width = metrics.widthPixels;
        int height = metrics.heightPixels;

        board.setSize(Math.min(width, height >> 1));
        currentPlayer.setDieHeight(height >> 2);
        currentPlayer.setDieWidth(width);
        waitingPlayer.setDieHeight(height >> 2);
        waitingPlayer.setDieWidth(width);
    }

    private void attachInterfaces() {
        try {
            onWinListener = context;
            onErrorExit = context;
        } catch (Exception ignored) {
        }
    }

    public void start() {
        currentPlayer.drawDie();

        try {
            board.initialise();
            board.draw();
        } catch (IllegalStateException e) {
            Toast.makeText(context, context.getString(R.string.dieDrawError), Toast.LENGTH_SHORT).show();
        }

        currentPlayer.setActive(true);
    }

    @Override
    public void onRoll() {
        passControlsToBoard();
        if (einStein) {
            hintAsEinStein();
        }
        tryToHint();
    }

    private void passControlsToBoard() {
        currentPlayer.setActive(false);
        board.setMovable(true);
    }

    private void hintAsEinStein() {
        Point p = getEinSteinPoint();
        board.processSelectTouch(p);
        einStein = false;
    }

    private void tryToHint() throws IllegalStateException {
        try {
            board.hint(currentPlayer);
        } catch (NoSuchElementException e) {
            throw new IllegalStateException(e.getMessage());
        }
    }

    @Override
    public void onStoneMoved() {
        CheckWin();
        swapControls();
    }

    public BoardActivity getContext() {
        return context;
    }

    public void CheckWin() {
        if (board.isCurrentPlayerWinner(currentPlayer.getId()))
            endingDialogue(currentPlayer.getId());
    }

    private void endingDialogue(int winner) {
        board.setMovable(false);
        currentPlayer.setActive(false);
        waitingPlayer.setActive(false);
        onWinListener.onWin(winner);
    }

    public abstract void swapControls();

    public void destroy() {
        currentPlayer.stopDieAnimationThread();
        waitingPlayer.stopDieAnimationThread();
        board = null;
        currentPlayer = null;
        waitingPlayer = null;
        context = null;
    }

    protected void calculateEinStein() {
        int id = currentPlayer.getId();
        int sum = 0;
        for (Map.Entry<?, Stone> stone : board.getStones().entrySet()) {
            if (stone.getValue().getPlayerId() == id)
                ++sum;
        }
        einStein = (sum == 1);
    }

    @NonNull
    private Point getEinSteinPoint() throws IllegalStateException {
        int id = currentPlayer.getId();
        for (Map.Entry<?, Stone> stone : board.getStones().entrySet()) {
            if (stone.getValue().getPlayerId() == id) {
                return (Point) stone.getKey();
            }
        }
        throw new IllegalStateException("EinStein point not found");
    }

    public void exceptionExit(Exception e) {
        onErrorExit.onError(e);
    }

    public interface OnWinListener {
        void onWin(int winner);
    }

    public interface OnErrorExit {
        void onError(Exception e);
    }
}