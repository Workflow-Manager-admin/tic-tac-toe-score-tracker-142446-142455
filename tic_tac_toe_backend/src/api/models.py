from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship


# PUBLIC_INTERFACE
class User(SQLModel, table=True):
    """Represents a player/user account for Tic Tac Toe."""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, description="The unique username for the player")
    hashed_password: str = Field(description="Password hash")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship: list of games where user was player_x or player_o
    games_as_x: List["Game"] = Relationship(back_populates="player_x", sa_relationship_kwargs={"foreign_keys": "[Game.player_x_id]"})
    games_as_o: List["Game"] = Relationship(back_populates="player_o", sa_relationship_kwargs={"foreign_keys": "[Game.player_o_id]"})
    moves: List["Move"] = Relationship(back_populates="user")


# PUBLIC_INTERFACE
class Game(SQLModel, table=True):
    """Represents a Tic Tac Toe game between two users."""
    id: Optional[int] = Field(default=None, primary_key=True)
    player_x_id: Optional[int] = Field(foreign_key="user.id")
    player_o_id: Optional[int] = Field(foreign_key="user.id")
    status: str = Field(default="waiting", description="waiting/in_progress/finished")
    winner_id: Optional[int] = Field(foreign_key="user.id", default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Player relationships
    player_x: Optional[User] = Relationship(back_populates="games_as_x", sa_relationship_kwargs={"foreign_keys": "[Game.player_x_id]"})
    player_o: Optional[User] = Relationship(back_populates="games_as_o", sa_relationship_kwargs={"foreign_keys": "[Game.player_o_id]"})
    moves: List["Move"] = Relationship(back_populates="game")


# PUBLIC_INTERFACE
class Move(SQLModel, table=True):
    """Represents a move made in a game."""
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    user_id: int = Field(foreign_key="user.id")
    x: int = Field(ge=0, le=2)
    y: int = Field(ge=0, le=2)
    symbol: str = Field(regex="^[xoXO]$")
    move_number: int = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)

    game: Optional[Game] = Relationship(back_populates="moves")
    user: Optional[User] = Relationship(back_populates="moves")
