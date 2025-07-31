from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import create_db_and_tables
from .routes import router

app = FastAPI(
    title="Tic Tac Toe API",
    description="Backend API for Tic Tac Toe game with user, game, leaderboard, history and real-time updates via polling or websockets. See /games/ws/{game_id} for websocket interface.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Users", "description": "User registration and account operations."},
        {"name": "Games", "description": "Game creation, move submission, and state polling."},
        {"name": "Leaderboard", "description": "Player high-score information."},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/", tags=["Meta"])
def health_check():
    """API health check endpoint."""
    return {"message": "Healthy"}

@app.get("/docs/websockets", tags=["Meta"])
def websocket_help():
    """
    Get info about websocket real-time API.
    """
    return {
        "websocket_endpoint": "/games/ws/{game_id}",
        "usage": "Connect with a websocket client to receive updates (moves/status) in real time for a given game. See docs for details."
    }

app.include_router(router)
