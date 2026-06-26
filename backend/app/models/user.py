#every layer that touches the user data needs a shared definition of what a "user" looks like.
#fastAPI uses it to serialize API response dependencies.py uses it
# to type the current_user object injected into endpoints

from pydantic import BaseModel
from datetime import datetime
from typing import Literal

#user profile looks like coming out of the database 
class UserProfile(BaseModel):
    id: str
    github_id: str
    username: str | None
    avatar_url: str | None
    plan: Literal["free", "pro"]  = "free"
    repos_used: int = 0
    created_at: datetime | None = None

    class config:
        # Extra fields are silently ignored instead of raising an error
        extra = "ignore"


#what we send to the frontend in auth/me

class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    avatar_url: str | None
    plan: Literal["free", "pro"]
    repos_used: int
