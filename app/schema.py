from pydantic import BaseModel, Field
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1, description="Message content cannot be empty")


class ChatRequest(BaseModel):
    messages: list[Message] = Field(
        min_length=1, description="Conversation must contain at least one message"
    )
