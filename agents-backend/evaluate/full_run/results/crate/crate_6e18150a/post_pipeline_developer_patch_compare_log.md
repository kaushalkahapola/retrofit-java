# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: True

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java']
- Developer Java files: ['server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java']
- Overlap Java files: ['server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java']

## File State Comparison
- Compared files: ['server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java']
- Mismatched files: []
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -62,7 +62,7 @@
             DataType<?> refInnerType = ArrayType.unnest(ref.valueType());
             DataType<?> literalInnerType = ArrayType.unnest(literal.valueType());
             if (!DataTypes.isNumeric(literalInnerType) || !DataTypes.isNumeric(refInnerType)) {
-                return true;
+                return literalInnerType.isConvertableTo(refInnerType, false);
             }
             if (isSafeConversion(literalInnerType, refInnerType)) {
                 return true;

```

Generated
```diff
@@ -62,7 +62,7 @@
             DataType<?> refInnerType = ArrayType.unnest(ref.valueType());
             DataType<?> literalInnerType = ArrayType.unnest(literal.valueType());
             if (!DataTypes.isNumeric(literalInnerType) || !DataTypes.isNumeric(refInnerType)) {
-                return true;
+                return literalInnerType.isConvertableTo(refInnerType, false);
             }
             if (isSafeConversion(literalInnerType, refInnerType)) {
                 return true;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```



## Full Generated Patch (Agent-Only, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
index 87130eac33..e00bc5eec6 100644
--- a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
+++ b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
@@ -62,7 +62,7 @@ public class SwapCastsInComparisonOperators implements Rule<Function> {
             DataType<?> refInnerType = ArrayType.unnest(ref.valueType());
             DataType<?> literalInnerType = ArrayType.unnest(literal.valueType());
             if (!DataTypes.isNumeric(literalInnerType) || !DataTypes.isNumeric(refInnerType)) {
-                return true;
+                return literalInnerType.isConvertableTo(refInnerType, false);
             }
             if (isSafeConversion(literalInnerType, refInnerType)) {
                 return true;

```

## Full Generated Patch (Final Effective, code-only)
```diff
diff --git a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
index 87130eac33..e00bc5eec6 100644
--- a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
+++ b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
@@ -62,7 +62,7 @@ public class SwapCastsInComparisonOperators implements Rule<Function> {
             DataType<?> refInnerType = ArrayType.unnest(ref.valueType());
             DataType<?> literalInnerType = ArrayType.unnest(literal.valueType());
             if (!DataTypes.isNumeric(literalInnerType) || !DataTypes.isNumeric(refInnerType)) {
-                return true;
+                return literalInnerType.isConvertableTo(refInnerType, false);
             }
             if (isSafeConversion(literalInnerType, refInnerType)) {
                 return true;

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/docs/appendices/release-notes/5.10.2.rst b/docs/appendices/release-notes/5.10.2.rst
index a57deb0641..d9132347b3 100644
--- a/docs/appendices/release-notes/5.10.2.rst
+++ b/docs/appendices/release-notes/5.10.2.rst
@@ -62,3 +62,8 @@ Fixes
 
 - Fixed an issue that caused a ``NullPointerException`` when binding to a
   non-existing prepared statement via PostgreSQL wire protocol.
+
+- Fixed an issue that caused a ``SELECT`` query to fail if a ``WHERE`` clause
+  had a comparison of a non-boolean column with a boolean literal, e.g.::
+
+    SELECT int_col FROM t where int_col = true;
diff --git a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
index 87130eac33..e00bc5eec6 100644
--- a/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
+++ b/server/src/main/java/io/crate/planner/optimizer/symbol/rule/SwapCastsInComparisonOperators.java
@@ -62,7 +62,7 @@ public class SwapCastsInComparisonOperators implements Rule<Function> {
             DataType<?> refInnerType = ArrayType.unnest(ref.valueType());
             DataType<?> literalInnerType = ArrayType.unnest(literal.valueType());
             if (!DataTypes.isNumeric(literalInnerType) || !DataTypes.isNumeric(refInnerType)) {
-                return true;
+                return literalInnerType.isConvertableTo(refInnerType, false);
             }
             if (isSafeConversion(literalInnerType, refInnerType)) {
                 return true;
diff --git a/server/src/test/java/io/crate/lucene/CommonQueryBuilderTest.java b/server/src/test/java/io/crate/lucene/CommonQueryBuilderTest.java
index f27aeaea57..c3f51fb141 100644
--- a/server/src/test/java/io/crate/lucene/CommonQueryBuilderTest.java
+++ b/server/src/test/java/io/crate/lucene/CommonQueryBuilderTest.java
@@ -831,4 +831,11 @@ public class CommonQueryBuilderTest extends LuceneQueryBuilderTest {
         assertThat(query).isExactlyInstanceOf(GenericFunctionQuery.class);
         assertThat(query).hasToString("(f = 0.99999999)");
     }
+
+    @Test
+    public void test_can_compare_any_type_with_boolean() {
+        Query query = convert("x = true");
+        assertThat(query).isExactlyInstanceOf(GenericFunctionQuery.class);
+        assertThat(query).hasToString("(x = true)");
+    }
 }

```
