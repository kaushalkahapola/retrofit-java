from typing import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    patch_path: str
    patch_analysis: list  # List[FileChange]
    target_repo_path: str
    mainline_repo_path: str
    experiment_mode: bool
    backport_commit: str
    original_commit: str
    retrieval_results: dict  # Map: source_file -> list of candidates
    implementation_plan: dict # ImplementationPlan (as dict)
