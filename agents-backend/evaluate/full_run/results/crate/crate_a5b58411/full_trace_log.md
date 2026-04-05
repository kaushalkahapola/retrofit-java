# Full Trace of Agentic File Edits

## Attempt #1

### Final Output Diff
**server/src/main/java/io/crate/planner/node/management/ExplainPlan.java** [replace]
```java
// --- OLD ---
<developer patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/planner/node/management/ExplainPlan.java b/server/src/main/java/io/crate/planner/node/management/ExplainPlan.java
index fe20bbb9bb..b3085d0d98 100644
--- a/server/src/main/java/io/crate/planner/node/management/ExplainPlan.java
+++ b/server/src/main/java/io/crate/planner/node/management/ExplainPlan.java
@@ -141,6 +141,12 @@ public class ExplainPlan implements Plan {
         if (context != null) {
             assert subPlan instanceof LogicalPlan : "subPlan must be a LogicalPlan";
             LogicalPlan plan = (LogicalPlan) subPlan;
+            var ramAccounting = ConcurrentRamAccounting.forCircuitBreaker(
+                "multi-phase",
+                dependencies.circuitBreaker(HierarchyCircuitBreakerService.QUERY),
+                plannerContext.transactionContext().sessionSettings().memoryLimitInBytes()
+            );
+            consumer.completionFuture().whenComplete((_, _) -> ramAccounting.close());
             executePlan(
                 plan,
                 dependencies,
@@ -150,7 +156,7 @@ public class ExplainPlan implements Plan {
                 subQueryResults,
                 new IdentityHashMap<>(),
                 new ArrayList<>(plan.dependencies().size()),
-                null,
+                ramAccounting,
                 null
             );
         } else {
@@ -236,20 +242,10 @@ public class ExplainPlan implements Plan {
                                              SubQueryResults subQueryResults,
                                              Map<SelectSymbol, Object> valuesBySubQuery,
                                              List<Map<String, Object>> explainResults,
-                                             @Nullable RamAccounting ramAccounting,
+                                             RamAccounting ramAccounting,
                                              @Nullable SelectSymbol selectSymbol) {
         boolean isTopLevel = selectSymbol == null;
 
-        assert ramAccounting != null || isTopLevel : "ramAccounting must NOT be null for subPlans";
-
-        if (ramAccounting == null) {
-            ramAccounting = ConcurrentRamAccounting.forCircuitBreaker(
-                "multi-phase",
-                executor.circuitBreaker(HierarchyCircuitBreakerService.QUERY),
-                plannerContext.transactionContext().sessionSettings().memoryLimitInBytes()
-            );
-        }
-
         if (isTopLevel == false) {
             plannerContext = PlannerContext.forSubPlan(plannerContext);
         }
```