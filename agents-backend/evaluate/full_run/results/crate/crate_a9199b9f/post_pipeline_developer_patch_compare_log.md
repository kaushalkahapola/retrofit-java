# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/io/crate/planner/operators/Collect.java']
- Developer Java files: ['server/src/main/java/io/crate/planner/operators/Collect.java']
- Overlap Java files: ['server/src/main/java/io/crate/planner/operators/Collect.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/io/crate/planner/operators/Collect.java']

## File State Comparison
- Compared files: ['server/src/main/java/io/crate/planner/operators/Collect.java']
- Mismatched files: ['server/src/main/java/io/crate/planner/operators/Collect.java']
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/io/crate/planner/operators/Collect.java

- Developer hunks: 3
- Generated hunks: 3

#### Hunk 1

Developer
```diff
@@ -123,6 +123,14 @@
         this.tableInfo = relation.tableInfo();
     }
 
+    /// @return a new Collect operator with changed outputs
+    public Collect withOutputs(List<Symbol> newOutputs) {
+        Collect collect = new Collect(relation, newOutputs, immutableWhere);
+        collect.mutableBoundWhere = mutableBoundWhere;
+        collect.detailedQuery = detailedQuery;
+        return collect;
+    }
+
     @Override
     public ExecutionPlan build(DependencyCarrier executor,
                                PlannerContext plannerContext,

```

Generated
```diff
@@ -109,6 +109,14 @@
         this.detailedQuery = detailedQuery;
     }
 
+    /// @return a new Collect operator with changed outputs
+    public Collect withOutputs(List<Symbol> newOutputs) {
+        Collect collect = new Collect(relation, newOutputs, immutableWhere);
+        collect.mutableBoundWhere = mutableBoundWhere;
+        collect.detailedQuery = detailedQuery;
+        return collect;
+    }
+
     public Collect(AbstractTableRelation<?> relation,
                    List<Symbol> outputs,
                    WhereClause where) {

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,5 +1,5 @@-@@ -123,6 +123,14 @@
-         this.tableInfo = relation.tableInfo();
+@@ -109,6 +109,14 @@
+         this.detailedQuery = detailedQuery;
      }
  
 +    /// @return a new Collect operator with changed outputs
@@ -10,6 +10,6 @@ +        return collect;
 +    }
 +
-     @Override
-     public ExecutionPlan build(DependencyCarrier executor,
-                                PlannerContext plannerContext,
+     public Collect(AbstractTableRelation<?> relation,
+                    List<Symbol> outputs,
+                    WhereClause where) {

```

#### Hunk 2

Developer
```diff
@@ -345,7 +353,7 @@
         if (newOutputs.size() == outputs.size() && newOutputs.containsAll(outputs)) {
             return this;
         }
-        return new Collect(relation, List.copyOf(newOutputs), immutableWhere);
+        return withOutputs(List.copyOf(newOutputs));
     }
 
     @Nullable

```

Generated
```diff
@@ -345,7 +353,7 @@
         if (newOutputs.size() == outputs.size() && newOutputs.containsAll(outputs)) {
             return this;
         }
-        return new Collect(relation, List.copyOf(newOutputs), immutableWhere);
+        return withOutputs(List.copyOf(newOutputs));
     }
 
     @Nullable

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 3

Developer
```diff
@@ -382,14 +390,7 @@
             return null;
         }
         newOutputs.add(0, fetchMarker);
-        return new FetchRewrite(
-            replacedOutputs,
-            new Collect(
-                relation,
-                newOutputs,
-                immutableWhere
-            )
-        );
+        return new FetchRewrite(replacedOutputs, withOutputs(newOutputs));
     }
 
     @Override

```

Generated
```diff
@@ -384,11 +392,7 @@
         newOutputs.add(0, fetchMarker);
         return new FetchRewrite(
             replacedOutputs,
-            new Collect(
-                relation,
-                newOutputs,
-                immutableWhere
-            )
+            withOutputs(newOutputs)
         );
     }
 

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,16 +1,13 @@-@@ -382,14 +390,7 @@
-             return null;
-         }
+@@ -384,11 +392,7 @@
          newOutputs.add(0, fetchMarker);
--        return new FetchRewrite(
--            replacedOutputs,
+         return new FetchRewrite(
+             replacedOutputs,
 -            new Collect(
 -                relation,
 -                newOutputs,
 -                immutableWhere
 -            )
--        );
-+        return new FetchRewrite(replacedOutputs, withOutputs(newOutputs));
++            withOutputs(newOutputs)
+         );
      }
  
-     @Override

```



## Full Generated Patch (Agent-Only, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/operators/Collect.java b/server/src/main/java/io/crate/planner/operators/Collect.java
index 42786e0c19..0406a9d773 100644
--- a/server/src/main/java/io/crate/planner/operators/Collect.java
+++ b/server/src/main/java/io/crate/planner/operators/Collect.java
@@ -109,6 +109,14 @@ public class Collect implements LogicalPlan {
         this.detailedQuery = detailedQuery;
     }
 
+    /// @return a new Collect operator with changed outputs
+    public Collect withOutputs(List<Symbol> newOutputs) {
+        Collect collect = new Collect(relation, newOutputs, immutableWhere);
+        collect.mutableBoundWhere = mutableBoundWhere;
+        collect.detailedQuery = detailedQuery;
+        return collect;
+    }
+
     public Collect(AbstractTableRelation<?> relation,
                    List<Symbol> outputs,
                    WhereClause where) {
@@ -345,7 +353,7 @@ public class Collect implements LogicalPlan {
         if (newOutputs.size() == outputs.size() && newOutputs.containsAll(outputs)) {
             return this;
         }
-        return new Collect(relation, List.copyOf(newOutputs), immutableWhere);
+        return withOutputs(List.copyOf(newOutputs));
     }
 
     @Nullable
@@ -384,11 +392,7 @@ public class Collect implements LogicalPlan {
         newOutputs.add(0, fetchMarker);
         return new FetchRewrite(
             replacedOutputs,
-            new Collect(
-                relation,
-                newOutputs,
-                immutableWhere
-            )
+            withOutputs(newOutputs)
         );
     }
 

```

## Full Generated Patch (Final Effective, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/operators/Collect.java b/server/src/main/java/io/crate/planner/operators/Collect.java
index 42786e0c19..0406a9d773 100644
--- a/server/src/main/java/io/crate/planner/operators/Collect.java
+++ b/server/src/main/java/io/crate/planner/operators/Collect.java
@@ -109,6 +109,14 @@ public class Collect implements LogicalPlan {
         this.detailedQuery = detailedQuery;
     }
 
+    /// @return a new Collect operator with changed outputs
+    public Collect withOutputs(List<Symbol> newOutputs) {
+        Collect collect = new Collect(relation, newOutputs, immutableWhere);
+        collect.mutableBoundWhere = mutableBoundWhere;
+        collect.detailedQuery = detailedQuery;
+        return collect;
+    }
+
     public Collect(AbstractTableRelation<?> relation,
                    List<Symbol> outputs,
                    WhereClause where) {
@@ -345,7 +353,7 @@ public class Collect implements LogicalPlan {
         if (newOutputs.size() == outputs.size() && newOutputs.containsAll(outputs)) {
             return this;
         }
-        return new Collect(relation, List.copyOf(newOutputs), immutableWhere);
+        return withOutputs(List.copyOf(newOutputs));
     }
 
     @Nullable
@@ -384,11 +392,7 @@ public class Collect implements LogicalPlan {
         newOutputs.add(0, fetchMarker);
         return new FetchRewrite(
             replacedOutputs,
-            new Collect(
-                relation,
-                newOutputs,
-                immutableWhere
-            )
+            withOutputs(newOutputs)
         );
     }
 

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/server/src/main/java/io/crate/planner/operators/Collect.java b/server/src/main/java/io/crate/planner/operators/Collect.java
index 42786e0c19..97aba6cd76 100644
--- a/server/src/main/java/io/crate/planner/operators/Collect.java
+++ b/server/src/main/java/io/crate/planner/operators/Collect.java
@@ -123,6 +123,14 @@ public class Collect implements LogicalPlan {
         this.tableInfo = relation.tableInfo();
     }
 
+    /// @return a new Collect operator with changed outputs
+    public Collect withOutputs(List<Symbol> newOutputs) {
+        Collect collect = new Collect(relation, newOutputs, immutableWhere);
+        collect.mutableBoundWhere = mutableBoundWhere;
+        collect.detailedQuery = detailedQuery;
+        return collect;
+    }
+
     @Override
     public ExecutionPlan build(DependencyCarrier executor,
                                PlannerContext plannerContext,
@@ -345,7 +353,7 @@ public class Collect implements LogicalPlan {
         if (newOutputs.size() == outputs.size() && newOutputs.containsAll(outputs)) {
             return this;
         }
-        return new Collect(relation, List.copyOf(newOutputs), immutableWhere);
+        return withOutputs(List.copyOf(newOutputs));
     }
 
     @Nullable
@@ -382,14 +390,7 @@ public class Collect implements LogicalPlan {
             return null;
         }
         newOutputs.add(0, fetchMarker);
-        return new FetchRewrite(
-            replacedOutputs,
-            new Collect(
-                relation,
-                newOutputs,
-                immutableWhere
-            )
-        );
+        return new FetchRewrite(replacedOutputs, withOutputs(newOutputs));
     }
 
     @Override
diff --git a/server/src/test/java/io/crate/planner/PlannerTest.java b/server/src/test/java/io/crate/planner/PlannerTest.java
index 200afe344e..d2e61e2eac 100644
--- a/server/src/test/java/io/crate/planner/PlannerTest.java
+++ b/server/src/test/java/io/crate/planner/PlannerTest.java
@@ -32,6 +32,8 @@ import static org.mockito.Mockito.when;
 import java.io.IOException;
 import java.util.Collections;
 import java.util.List;
+import java.util.Map;
+import java.util.Map.Entry;
 import java.util.UUID;
 
 import org.elasticsearch.common.Randomness;
@@ -39,15 +41,22 @@ import org.elasticsearch.index.shard.ShardId;
 import org.junit.Before;
 import org.junit.Test;
 
+import io.crate.metadata.PartitionName;
+import io.crate.metadata.RelationName;
 import io.crate.session.Cursors;
 import io.crate.data.Row1;
 import io.crate.exceptions.ConversionException;
 import io.crate.exceptions.UnavailableShardsException;
+import com.carrotsearch.hppc.IntIndexedContainer;
+
+import io.crate.execution.dsl.phases.RoutedCollectPhase;
 import io.crate.expression.symbol.Literal;
 import io.crate.metadata.CoordinatorTxnCtx;
 import io.crate.metadata.RoutingProvider;
 import io.crate.metadata.settings.CoordinatorSessionSettings;
 import io.crate.planner.node.ddl.UpdateSettingsPlan;
+import io.crate.planner.node.dql.Collect;
+import io.crate.planner.node.dql.QueryThenFetch;
 import io.crate.planner.operators.LogicalPlan;
 import io.crate.planner.operators.LogicalPlanner;
 import io.crate.planner.operators.SubQueryResults;
@@ -152,4 +161,34 @@ public class PlannerTest extends CrateDummyClusterServiceUnitTest {
             .hasHTTPError(INTERNAL_SERVER_ERROR, 5002)
             .hasMessageContaining("the shard 11 of table [tbl/uuid] is not available");
     }
+
+    @Test
+    public void test_table_with_clustered_by_and_partition_filter_routing() throws Exception {
+        String schema = e.getSessionSettings().currentSchema();
+        RelationName relName = new RelationName(schema, "t1");
+        e.addPartitionedTable(
+            """
+            CREATE TABLE t1 (
+               a int,
+               impression_id text,
+               "time" TIMESTAMP WITH TIME ZONE,
+               "daypart" TIMESTAMP WITH TIME ZONE GENERATED ALWAYS AS date_trunc('day', "time")
+           ) CLUSTERED BY ("impression_id") INTO 10 SHARDS PARTITIONED BY ("daypart")
+            """,
+            new PartitionName(relName, List.of("1760392800000")).asIndexName(),
+            new PartitionName(relName, List.of("1760306400000")).asIndexName(),
+            new PartitionName(relName, List.of("1760220000000")).asIndexName()
+        );
+        QueryThenFetch qtf = e.plan(
+            "SELECT * FROM t1 WHERE impression_id='10-uuid' AND daypart=1760306400000 ORDER BY a DESC LIMIT 3");
+        RoutedCollectPhase collectPhase = (RoutedCollectPhase) ((Collect) qtf.subPlan()).collectPhase();
+        Map<String, IntIndexedContainer> indicesAndShards = collectPhase.routing().locations().entrySet().iterator().next().getValue();
+        assertThat(indicesAndShards)
+            .as("Routing includes only one partition because of daypart filter")
+            .hasSize(1);
+        Entry<String, IntIndexedContainer> firstEntry = indicesAndShards.entrySet().iterator().next();
+        assertThat(firstEntry.getValue())
+            .as("Routing includes only one shard because of impression_id filter (clustered by)")
+            .hasSize(1);
+    }
 }

```
