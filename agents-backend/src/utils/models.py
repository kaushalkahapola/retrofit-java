from typing import List, Optional
from pydantic import BaseModel, Field

class FileMapping(BaseModel):
    source_file: str = Field(description="The path of the file in the source patch")
    target_file: str = Field(description="The path of the file in the target repository")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation for why this target file was chosen")

class Step(BaseModel):
    step_id: int = Field(description="Sequential ID of the step")
    description: str = Field(description="Detailed description of what to do")
    file_path: str = Field(description="The target file to modify or create")
    action: str = Field(description="Action type: MODIFY, CREATE, DELETE, or RENAME")

class ImplementationPlan(BaseModel):
    patch_intent: str = Field(description="Summary of what the patch aims to achieve")
    file_mappings: List[FileMapping] = Field(description="Mapping of source files to target files")
    steps: List[Step] = Field(description="Step-by-step plan to apply the backport")
