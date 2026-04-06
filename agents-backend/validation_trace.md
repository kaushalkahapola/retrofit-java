# Validation Trace

## Blueprint Summary
- **Root Cause**: Deterministic inference: target branch diverges from mainline; adapt hunks with exact target context.
- **Fix Logic**: Apply each source hunk with target-verified context and symbol consistency while preserving behavior.
- **Dependent APIs**: ['if', 'fullDocSizeEstimate', 'estimation', 'estimate', 'estimatedSizePerRow']

## Hunk Segregation
- Code files: 18
- Test files: 0
- Developer auxiliary hunks: 28

## Agent Tool Steps

  - `Agent calls apply_adapted_hunks` with `{"code_count": 9, "developer_aux_count": 28, "effective_code_count": 37, "test_count": 0}`
  - `Tool: apply_adapted_hunks` -> {'success': True, 'output': 'All hunks applied successfully.', 'applied_files': ['server/src/main/java/io/crate/execution/dml/upsert/ShardUpsertRequest.java', 'server/src/main/java/io/crate/execution/dsl/projection/ColumnIndexWriterProjection.java', 'server/src/main/java/io/crate/execution/dsl/projection/UpdateProjection.java', 'server/src/main/java/io/crate/execution/engine/indexing/ColumnIndexWriterProjector.java', 'server/src/main/java/io/crate/execution/engine/indexing/IndexWriterProjector.java', 'server/src/main/java/io/crate/planner/consumer/InsertFromSubQueryPlanner.java', 'server/src/main/java/io/crate/planner/consumer/UpdatePlanner.java', 'server/src/main/java/io/crate/planner/operators/InsertFromValues.java', 'server/src/main/java/io/crate/statistics/TableStats.java', 'docs/appendices/release-notes/5.10.5.rst', 'server/src/main/java/io/crate/execution/engine/pipeline/ProjectionToProjectorVisitor.java', 'server/src/test/java/io/crate/execution/dml/upsert/ShardUpsertRequestTest... [TRUNCATED]
  - `Agent calls run_build_script` with `{}`
  - `Tool: run_build_script` -> {'success': False, 'output': '--- Building code for d60fe8f ---\nCPU detected: 12\nMaven threads: 12\n--- Changing directory to /home/kaushal/retrofit-java/temp_repo_storage/crate ---\nmaven-cache-crate\n--- Building Docker image... ---\n--- Setting cache permissions... ---\n--- Building with Maven... ---\n[INFO] Scanning for projects...\n[INFO] ------------------------------------------------------------------------\n[INFO] Reactor Build Order:\n[INFO] \n[INFO] crate                                                              [pom]\n[INFO] crate-libs-shared                                                  [jar]\n[INFO] crate-libs-dex                                                     [jar]\n[INFO] crate-libs-es-x-content                                            [jar]\n[INFO] crate-libs-cli                                                     [jar]\n[INFO] crate-libs-guice                                                   [jar]\n[INFO] crate-libs-sql-parser                          ... [TRUNCATED]

**Final Status: BUILD FAILED**

**Agent Analysis:**
API/signature mismatch in generated patch against target branch.