# Phase 0 Inputs

- Mainline commit: d150a2e57f8a6da80bacf146f934d8e0cd87466b
- Backport commit: 007682aa53eebc124e6406977dd03a50d3433630
- Java-only files for agentic phases: 1
- Developer auxiliary hunks (test + non-Java): 2

## Commit Pair Consistency
- Pair mismatch: True
- Reason: mainline_backport_scope_mismatch
- Mainline Java files: ['server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java']
- Developer Java files: ['server/src/main/java/io/crate/execution/ddl/tables/AlterTableOperation.java']
- Overlap Java files: []
- Overlap ratio (mainline): 0.0

## Mainline Patch
```diff
From d150a2e57f8a6da80bacf146f934d8e0cd87466b Mon Sep 17 00:00:00 2001
From: Sebastian Utz <su@rtme.net>
Date: Fri, 1 Nov 2024 15:03:54 +0100
Subject: [PATCH] Forbid adding a sub-column to an object(ignored) if table
 isn't empty

If the table is not empty it may already contain data for the
explicit added new column. The data may be of a different type,
which then breaks collecting and streaming the data.
Thus this may break querying the data or running `ANALYZE`.

As we do not know which data the table already has without processing
each row, we simply throw an exception if we detect that the table
isn't empty.
---
 docs/appendices/release-notes/5.9.3.rst       | 11 ++++++++++
 .../ddl/tables/AlterTableClient.java          | 11 ++++++++++
 .../AlterTableIntegrationTest.java            | 22 +++++++++++++++++++
 3 files changed, 44 insertions(+)

diff --git a/docs/appendices/release-notes/5.9.3.rst b/docs/appendices/release-notes/5.9.3.rst
index 9a864a193a..ea25e72cb6 100644
--- a/docs/appendices/release-notes/5.9.3.rst
+++ b/docs/appendices/release-notes/5.9.3.rst
@@ -71,3 +71,14 @@ Fixes
       |       1.0 |
       +-----------+
 
+- Fixed an issue which can cause the data of a table to not be queried anymore and the
+  :ref:`analyze` to fail, if a sub column is added to an object column with
+  column policy ``IGNORED`` when the table is not empty and the new column's
+  data type is different from the existing column's values.
+  This is not allowed anymore and results in an error. For example::
+
+    CREATE TABLE t (o OBJECT(IGNORED));
+    INSERT INTO t (o) VALUES ({x=1});
+    ALTER TABLE t ADD COLUMN o['x'] AS TEXT; <--- this is not allowed anymore
+    INSERT INTO t (o) VALUES ({x='foo'});
+    ANALYZE; <--- this will fail without the fix
diff --git a/server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java b/server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java
index b18a977bed..76a025034b 100644
--- a/server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java
+++ b/server/src/main/java/io/crate/execution/ddl/tables/AlterTableClient.java
@@ -61,12 +61,14 @@ import io.crate.execution.support.ChainableAction;
 import io.crate.execution.support.ChainableActions;
 import io.crate.metadata.GeneratedReference;
 import io.crate.metadata.PartitionName;
+import io.crate.metadata.Reference;
 import io.crate.metadata.RelationName;
 import io.crate.metadata.table.TableInfo;
 import io.crate.replication.logical.LogicalReplicationService;
 import io.crate.replication.logical.metadata.Publication;
 import io.crate.session.CollectingResultReceiver;
 import io.crate.session.Sessions;
+import io.crate.sql.tree.ColumnPolicy;
 
 @Singleton
 public class AlterTableClient {
@@ -121,11 +123,20 @@ public class AlterTableClient {
     }
 
     public CompletableFuture<Long> addColumn(AddColumnRequest addColumnRequest) {
+        var newReferences = addColumnRequest.references();
         String subject = null;
         if (addColumnRequest.pKeyIndices().isEmpty() == false) {
             subject = "primary key";
         } else if (addColumnRequest.references().stream().anyMatch(ref -> ref instanceof GeneratedReference)) {
             subject = "generated";
+        } else {
+            for (Reference newRef : newReferences) {
+                if (newReferences.stream().anyMatch(r -> r.column().isChildOf(newRef.column()))
+                    && newRef.columnPolicy().equals(ColumnPolicy.IGNORED)) {
+                    subject = "sub column to an OBJECT(IGNORED) parent";
+                    break;
+                }
+            }
         }
         if (subject != null) {
             String finalSubject = subject;
diff --git a/server/src/test/java/io/crate/integrationtests/AlterTableIntegrationTest.java b/server/src/test/java/io/crate/integrationtests/AlterTableIntegrationTest.java
index 9e20311f48..d87b302756 100644
--- a/server/src/test/java/io/crate/integrationtests/AlterTableIntegrationTest.java
+++ b/server/src/test/java/io/crate/integrationtests/AlterTableIntegrationTest.java
@@ -340,4 +340,26 @@ public class AlterTableIntegrationTest extends IntegTestCase {
         execute("select column_name from information_schema.columns where table_name = 't'");
         assertThat(response).hasRows("a2", "o2", "o2['a22']", "o2['b']", "c");
     }
+
+    @Test
+    public void test_cannot_add_sub_column_to_ignored_parent_if_table_is_not_empty() {
+        execute("CREATE TABLE t1 (obj object(ignored))");
+        execute("INSERT INTO t1 (obj) VALUES ({a={b=21, c=22}})");
+        execute("refresh table t1");
+
+        Asserts.assertSQLError(() -> execute("ALTER TABLE t1 ADD COLUMN obj['a'] text"))
+            .hasPGError(INTERNAL_ERROR)
+            .hasHTTPError(BAD_REQUEST, 4004)
+            .hasMessageContaining("Cannot add a sub column to an OBJECT(IGNORED) parent column to a table that isn't empty");
+    }
+
+    @Test
+    public void test_can_add_sub_column_to_ignored_parent_if_table_is_empty() {
+        execute("CREATE TABLE t1 (obj object(ignored))");
+        execute("ALTER TABLE t1 ADD COLUMN obj['a'] text");
+        execute("INSERT INTO t1 (obj) VALUES ({a='bar'})");
+        execute("refresh table t1");
+        execute("SELECT obj['a'] FROM t1");
+        assertThat(response).hasRows("bar");
+    }
 }
-- 
2.53.0


```
