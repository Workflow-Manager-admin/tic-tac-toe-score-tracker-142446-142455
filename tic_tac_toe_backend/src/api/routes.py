from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlmodel import select, Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .db import get_session
from .models import User, Game, Move

router = APIRouter()

class UserCreateModel(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=4)
class UserLoginModel(BaseModel):
    username: str
    password: str
class UserPublicModel(BaseModel):
    id: int
    username: str

class GameCreateModel(BaseModel):
    pass # No payload necessary, optional enhancements
class JoinGameModel(BaseModel):
    game_id: int

class MoveModel(BaseModel):
    game_id: int
    x: int = Field(..., ge=0, le=2)
    y: int = Field(..., ge=0, le=2)

class LeaderboardEntry(BaseModel):
    username: str
    wins: int
    losses: int
    draws: int

# --- Utilities ---

def hash_password(pw: str) -> str:
    """Hash a password (SHA256 for demo; replace with pbkdf2 in prod)."""
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()

def verify_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed

def check_game_winner(moves: List[Move]) -> Optional[str]:
    """Return 'x' or 'o' if winner, 'draw' if board full, else None."""
    board = [["" for _ in range(3)] for _ in range(3)]
    for m in moves:
        board[m.x][m.y] = m.symbol.lower()

    # Check rows, cols, diagonals
    win_lines = (
        [(i, j) for j in range(3)] for i in range(3)
    )  # rows
    win_lines = list(win_lines) + [
        [(j, i) for j in range(3)] for i in range(3)
    ]  # cols
    win_lines += [[(i, i) for i in range(3)], [(i, 2 - i) for i in range(3)]]
    for line in win_lines:
        symbols = [board[x][y] for (x, y) in line]
        for s in ['x', 'o']:
            if all(sym == s for sym in symbols):
                return s
    if all(board[x][y] for x in range(3) for y in range(3)):
        return "draw"
    return None

# In-memory websocket connection store, minimal version
live_games: Dict[int, List[WebSocket]] = {}

# --- User endpoints ---

# PUBLIC_INTERFACE
@router.post("/users/register", response_model=UserPublicModel, tags=["Users"])
async def register_user(payload: UserCreateModel, session: Session = Depends(get_session)):
    """
    Register a new user account.
    """
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(username=payload.username, hashed_password=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserPublicModel(id=user.id, username=user.username)

# PUBLIC_INTERFACE
@router.post("/users/login", response_model=UserPublicModel, tags=["Users"])
async def login(payload: UserLoginModel, session: Session = Depends(get_session)):
    """
    Log in with a username and password.
    """
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return UserPublicModel(id=user.id, username=user.username)

# --- Game endpoints ---

# PUBLIC_INTERFACE
@router.post("/games/create", response_model=Dict[str, Any], tags=["Games"])
async def create_game(user_id: int = Query(..., description="ID of the user creating the game"), session: Session = Depends(get_session)):
    """
    Create a new Tic Tac Toe game. You become player X.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    game = Game(player_x_id=user_id, status="waiting")
    session.add(game)
    session.commit()
    session.refresh(game)
    return {"game_id": game.id, "status": game.status}

# PUBLIC_INTERFACE
@router.post("/games/join", tags=["Games"])
async def join_game(payload: JoinGameModel, user_id: int = Query(..., description="ID of the joining user"), session: Session = Depends(get_session)):
    """
    Join an existing open game. You become player O.
    """
    game = session.get(Game, payload.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != "waiting":
        raise HTTPException(status_code=400, detail="Game already started/finished")
    if game.player_x_id == user_id:
        raise HTTPException(status_code=400, detail="Can't join your own game")
    game.player_o_id = user_id
    game.status = "in_progress"
    session.add(game)
    session.commit()
    return {"game_id": game.id, "status": game.status}

# PUBLIC_INTERFACE
@router.get("/games/available", response_model=List[Dict[str, Any]], tags=["Games"])
async def list_open_games(session: Session = Depends(get_session)):
    """
    List games waiting for an opponent.
    """
    games = session.exec(select(Game).where(Game.status == "waiting")).all()
    return [{"game_id": g.id, "player_x_id": g.player_x_id} for g in games]

# PUBLIC_INTERFACE
@router.get("/games/{game_id}", response_model=Dict[str, Any], tags=["Games"])
async def get_game_state(game_id: int, session: Session = Depends(get_session)):
    """
    Get the current state of a specific game, including moves.
    """
    game = session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    moves = session.exec(select(Move).where(Move.game_id == game_id).order_by(Move.move_number)).all()
    return {
        "game_id": game.id,
        "status": game.status,
        "player_x_id": game.player_x_id,
        "player_o_id": game.player_o_id,
        "winner_id": game.winner_id,
        "moves": [{"x": m.x, "y": m.y, "symbol": m.symbol, "user_id": m.user_id, "move_number": m.move_number} for m in moves],
        "created_at": game.created_at,
    }

# PUBLIC_INTERFACE
@router.post("/games/move", response_model=Dict[str, Any], tags=["Games"])
async def make_move(payload: MoveModel, user_id: int = Query(..., description="ID of the player"), session: Session = Depends(get_session)):
    """
    Submit a move for the given game.
    """
    game = session.get(Game, payload.game_id)
    if not game or game.status != "in_progress":
        raise HTTPException(status_code=400, detail="Game not in progress")
    user = session.get(User, user_id)
    if not user or user.id not in {game.player_x_id, game.player_o_id}:
        raise HTTPException(status_code=403, detail="You are not a participant in this game")

    # Moves must alternate and be on valid, empty squares
    moves = session.exec(select(Move).where(Move.game_id == game.id).order_by(Move.move_number)).all()
    symbol = 'x' if user.id == game.player_x_id else 'o'
    # Enforce turn order
    if moves and moves[-1].symbol.lower() == symbol:
        raise HTTPException(status_code=400, detail="Not your turn")
    # Square empty?
    for m in moves:
        if m.x == payload.x and m.y == payload.y:
            raise HTTPException(status_code=400, detail="Square already taken")

    move = Move(
        game_id=game.id,
        user_id=user.id,
        x=payload.x,
        y=payload.y,
        symbol=symbol,
        move_number=len(moves) + 1,
    )
    session.add(move)
    session.commit()
    session.refresh(move)
    moves = moves + [move]
    result = check_game_winner(moves)
    if result == 'x':
        game.status = "finished"
        game.winner_id = game.player_x_id
    elif result == 'o':
        game.status = "finished"
        game.winner_id = game.player_o_id
    elif result == "draw":
        game.status = "finished"
        game.winner_id = None
    session.add(game)
    session.commit()

    # Notify websocket listeners (if live)
    sockets = live_games.get(game.id)
    if sockets:
        update_msg = {
            "game_id": game.id,
            "status": game.status,
            "winner_id": game.winner_id,
            "move": {
                "x": move.x,
                "y": move.y,
                "symbol": move.symbol,
                "user_id": move.user_id,
                "move_number": move.move_number,
            },
        }
        for ws in sockets:
            try:
                import asyncio
                asyncio.create_task(ws.send_json(update_msg))
            except Exception:
                pass

    return {"success": True, "result": result, "move": {"x": move.x, "y": move.y, "symbol": move.symbol, "user_id": move.user_id, "move_number": move.move_number}}

# --- Real-time/game polling ---

# PUBLIC_INTERFACE
@router.websocket("/games/ws/{game_id}")
async def websocket_game_updates(websocket: WebSocket, game_id: int):
    """Websocket endpoint for real-time updates to a game."""
    await websocket.accept()
    if game_id not in live_games:
        live_games[game_id] = []
    live_games[game_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # Minimal keepalive (could improve)
    except WebSocketDisconnect:
        live_games[game_id].remove(websocket)

# PUBLIC_INTERFACE
@router.get("/games/poll/{game_id}", response_model=Dict[str, Any], tags=["Games"])
async def poll_game_state(game_id: int, last_move_number: Optional[int] = 0, session: Session = Depends(get_session)):
    """HTTP polling for the latest game state (if not using websockets)."""
    game = session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    moves = session.exec(select(Move).where(Move.game_id == game.id).order_by(Move.move_number)).all()
    if last_move_number and len(moves) <= last_move_number:
        return {"new_moves": [], "status": game.status}
    new_moves = moves[last_move_number:]
    return {
        "new_moves": [{"x": m.x, "y": m.y, "symbol": m.symbol, "user_id": m.user_id, "move_number": m.move_number} for m in new_moves],
        "status": game.status,
        "winner_id": game.winner_id,
    }

# --- Leaderboard and Game History ---

# PUBLIC_INTERFACE
@router.get("/leaderboard", response_model=List[LeaderboardEntry], tags=["Leaderboard"])
async def get_leaderboard(limit: int = 10, session: Session = Depends(get_session)):
    """Get the leaderboard of top users (wins/losses/draws)."""
    # Compute win/loss/draw statistics for all users
    users = session.exec(select(User)).all()
    leaderboard = []
    for u in users:
        wins = session.exec(select(Game).where(Game.winner_id == u.id)).count()
        losses = session.exec(select(Game).where(((Game.player_x_id == u.id) | (Game.player_o_id == u.id)) & (Game.winner_id != u.id) & (Game.status == "finished") & (Game.winner_id.is_not(None)))).count()
        draws = session.exec(select(Game).where(((Game.player_x_id == u.id) | (Game.player_o_id == u.id)) & (Game.status == "finished") & (Game.winner_id.is_(None)))).count()
        leaderboard.append({"username": u.username, "wins": wins, "losses": losses, "draws": draws})
    leaderboard = sorted(leaderboard, key=lambda d: (d["wins"], -d["losses"]), reverse=True)
    return leaderboard[:limit]

# PUBLIC_INTERFACE
@router.get("/users/{user_id}/games", response_model=List[Dict[str, Any]], tags=["Games"])
async def user_game_history(user_id: int, session: Session = Depends(get_session)):
    """Fetch all games this user has played (history)."""
    games = session.exec(select(Game).where((Game.player_x_id == user_id) | (Game.player_o_id == user_id))).all()
    result = []
    for g in games:
        res = {
            "game_id": g.id,
            "status": g.status,
            "as_player": "x" if g.player_x_id == user_id else "o",
            "winner_id": g.winner_id,
            "opponent_id": g.player_o_id if g.player_x_id == user_id else g.player_x_id,
            "created_at": g.created_at,
        }
        result.append(res)
    return result
