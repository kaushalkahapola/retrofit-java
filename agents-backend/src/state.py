from typing import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    patch_path: str
    patch_analysis: list  # List[FileChange]
