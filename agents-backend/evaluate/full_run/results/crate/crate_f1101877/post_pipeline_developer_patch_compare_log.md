# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: True

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/io/crate/planner/operators/InsertFromValues.java']
- Developer Java files: ['server/src/main/java/io/crate/planner/operators/InsertFromValues.java']
- Overlap Java files: ['server/src/main/java/io/crate/planner/operators/InsertFromValues.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/io/crate/planner/operators/InsertFromValues.java']

## File State Comparison
- Compared files: ['server/src/main/java/io/crate/planner/operators/InsertFromValues.java']
- Mismatched files: []
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/io/crate/planner/operators/InsertFromValues.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -131,11 +131,11 @@
     }
 
     @Override
-    public void execute(DependencyCarrier dependencies,
-                        PlannerContext plannerContext,
-                        RowConsumer consumer,
-                        Row params,
-                        SubQueryResults subQueryResults) {
+    public void executeOrFail(DependencyCarrier dependencies,
+                              PlannerContext plannerContext,
+                              RowConsumer consumer,
+                              Row params,
+                              SubQueryResults subQueryResults) {
         DocTableInfo tableInfo = dependencies
             .schemas()
             .getTableInfo(writerProjection.tableIdent());

```

Generated
```diff
@@ -131,11 +131,11 @@
     }
 
     @Override
-    public void execute(DependencyCarrier dependencies,
-                        PlannerContext plannerContext,
-                        RowConsumer consumer,
-                        Row params,
-                        SubQueryResults subQueryResults) {
+    public void executeOrFail(DependencyCarrier dependencies,
+                              PlannerContext plannerContext,
+                              RowConsumer consumer,
+                              Row params,
+                              SubQueryResults subQueryResults) {
         DocTableInfo tableInfo = dependencies
             .schemas()
             .getTableInfo(writerProjection.tableIdent());

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```



## Full Generated Patch (Agent-Only, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
index 4aac71b026..7a4aee6f4c 100644
--- a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
+++ b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
@@ -131,11 +131,11 @@ public class InsertFromValues implements LogicalPlan {
     }
 
     @Override
-    public void execute(DependencyCarrier dependencies,
-                        PlannerContext plannerContext,
-                        RowConsumer consumer,
-                        Row params,
-                        SubQueryResults subQueryResults) {
+    public void executeOrFail(DependencyCarrier dependencies,
+                              PlannerContext plannerContext,
+                              RowConsumer consumer,
+                              Row params,
+                              SubQueryResults subQueryResults) {
         DocTableInfo tableInfo = dependencies
             .schemas()
             .getTableInfo(writerProjection.tableIdent());

```

## Full Generated Patch (Final Effective, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
index 4aac71b026..7a4aee6f4c 100644
--- a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
+++ b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
@@ -131,11 +131,11 @@ public class InsertFromValues implements LogicalPlan {
     }
 
     @Override
-    public void execute(DependencyCarrier dependencies,
-                        PlannerContext plannerContext,
-                        RowConsumer consumer,
-                        Row params,
-                        SubQueryResults subQueryResults) {
+    public void executeOrFail(DependencyCarrier dependencies,
+                              PlannerContext plannerContext,
+                              RowConsumer consumer,
+                              Row params,
+                              SubQueryResults subQueryResults) {
         DocTableInfo tableInfo = dependencies
             .schemas()
             .getTableInfo(writerProjection.tableIdent());

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/docs/appendices/release-notes/6.0.4.rst b/docs/appendices/release-notes/6.0.4.rst
index b8d96773ab..bb5b25802f 100644
--- a/docs/appendices/release-notes/6.0.4.rst
+++ b/docs/appendices/release-notes/6.0.4.rst
@@ -90,3 +90,7 @@ Fixes
 - Fixed an issue with ``atttypid`` column of the ``pg_attribute`` table not
   being reset to ``0`` for dropped columns, which contradicts with the
   PostgreSQL behavior.
+
+- Fixed an issue resulting in stuck :ref:`sys-jobs` entries when an
+  :ref:`sql-insert` statement using :ref:`ref-values` results in an execution
+  error, e.g. due to implicit cast or parsing issues.
diff --git a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
index 4aac71b026..7a4aee6f4c 100644
--- a/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
+++ b/server/src/main/java/io/crate/planner/operators/InsertFromValues.java
@@ -131,11 +131,11 @@ public class InsertFromValues implements LogicalPlan {
     }
 
     @Override
-    public void execute(DependencyCarrier dependencies,
-                        PlannerContext plannerContext,
-                        RowConsumer consumer,
-                        Row params,
-                        SubQueryResults subQueryResults) {
+    public void executeOrFail(DependencyCarrier dependencies,
+                              PlannerContext plannerContext,
+                              RowConsumer consumer,
+                              Row params,
+                              SubQueryResults subQueryResults) {
         DocTableInfo tableInfo = dependencies
             .schemas()
             .getTableInfo(writerProjection.tableIdent());
diff --git a/server/src/test/java/io/crate/integrationtests/InsertIntoIntegrationTest.java b/server/src/test/java/io/crate/integrationtests/InsertIntoIntegrationTest.java
index 0b2d234bbc..ae1cb23a89 100644
--- a/server/src/test/java/io/crate/integrationtests/InsertIntoIntegrationTest.java
+++ b/server/src/test/java/io/crate/integrationtests/InsertIntoIntegrationTest.java
@@ -2843,4 +2843,16 @@ public class InsertIntoIntegrationTest extends IntegTestCase {
         assertThat(response.cols()).containsExactly("a", "b", "c", "d", "e");
         assertThat(response).hasRows("1| 2| 3| NULL| 5", "2| NULL| NULL| 4| NULL");
     }
+
+    @Test
+    public void test_insert_from_values_with_execution_error_gets_removed_from_sys_jobs() {
+        execute("CREATE TABLE doc.ti1 (\"a\" OBJECT(DYNAMIC))");
+        try {
+            execute("INSERT INTO doc.ti1 VALUES (?)", new Object[] {"{\"a\" 1}"});
+        } catch (Exception e) {
+            // ignore
+        }
+        execute("SELECT count(*) FROM sys.jobs WHERE stmt like 'INSERT%'");
+        assertThat(response).hasRows("0");
+    }
 }

```
