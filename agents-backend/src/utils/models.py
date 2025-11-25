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
    code_snippet: Optional[str] = Field(description="Specific code to add or modify (if applicable)")

class CompatibilityAnalysis(BaseModel):
    java_version_differences: str = Field(description="Analysis of Java version mismatches (e.g., var usage, switch expressions)")
    refactoring_notes: str = Field(description="Notes on renamed methods, variables, or class structure changes in target")
    missing_dependencies: List[str] = Field(description="List of dependencies present in patch but missing in target")

class ImplementationPlan(BaseModel):
    patch_intent: str = Field(description="Summary of what the patch aims to achieve")
    compatibility_analysis: CompatibilityAnalysis = Field(description="Deep analysis of compatibility between patch and target")
    file_mappings: List[FileMapping] = Field(description="Mapping of source files to target files")
    steps: List[Step] = Field(description="Step-by-step plan to apply the backport")
