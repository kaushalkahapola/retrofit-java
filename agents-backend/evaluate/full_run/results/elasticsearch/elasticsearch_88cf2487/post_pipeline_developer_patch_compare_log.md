# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']
- Developer Java files: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']
- Overlap Java files: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']

## File State Comparison
- Compared files: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']
- Mismatched files: ['server/src/main/java/org/elasticsearch/script/ScriptStats.java']
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/org/elasticsearch/script/ScriptStats.java

- Developer hunks: 2
- Generated hunks: 0

#### Hunk 1

Developer
```diff
@@ -25,6 +25,7 @@
 import java.util.Map;
 import java.util.Objects;
 
+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;
 import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;
 import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;
 import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1 @@-@@ -25,6 +25,7 @@
- import java.util.Map;
- import java.util.Objects;
- 
-+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;
- import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;
- import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;
- import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;
+*No hunk*
```

#### Hunk 2

Developer
```diff
@@ -199,7 +200,7 @@
                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);
             }
             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {
-                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);
             }
             ob.array(CONTEXTS, contextStats.iterator());
         });

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -199,7 +200,7 @@
-                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);
-             }
-             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {
--                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
-+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);
-             }
-             ob.array(CONTEXTS, contextStats.iterator());
-         });
+*No hunk*
```



## Full Generated Patch (Agent-Only, code-only)
```diff

```

## Full Generated Patch (Final Effective, code-only)
```diff

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/docs/changelog/123384.yaml b/docs/changelog/123384.yaml
new file mode 100644
index 00000000000..33d42b79c41
--- /dev/null
+++ b/docs/changelog/123384.yaml
@@ -0,0 +1,5 @@
+pr: 123384
+summary: Fixing serialization of `ScriptStats` `cache_evictions_history`
+area: Stats
+type: bug
+issues: []
diff --git a/server/src/main/java/org/elasticsearch/script/ScriptStats.java b/server/src/main/java/org/elasticsearch/script/ScriptStats.java
index f24052ef7e3..e085eb50ffb 100644
--- a/server/src/main/java/org/elasticsearch/script/ScriptStats.java
+++ b/server/src/main/java/org/elasticsearch/script/ScriptStats.java
@@ -25,6 +25,7 @@ import java.util.List;
 import java.util.Map;
 import java.util.Objects;
 
+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;
 import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;
 import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;
 import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;
@@ -199,7 +200,7 @@ public record ScriptStats(
                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);
             }
             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {
-                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);
             }
             ob.array(CONTEXTS, contextStats.iterator());
         });
diff --git a/server/src/test/java/org/elasticsearch/script/ScriptStatsTests.java b/server/src/test/java/org/elasticsearch/script/ScriptStatsTests.java
index df81e8ebcbb..b60afca0939 100644
--- a/server/src/test/java/org/elasticsearch/script/ScriptStatsTests.java
+++ b/server/src/test/java/org/elasticsearch/script/ScriptStatsTests.java
@@ -78,6 +78,37 @@ public class ScriptStatsTests extends ESTestCase {
         assertThat(Strings.toString(builder), equalTo(expected));
     }
 
+    public void testXContentChunkedHistory() throws Exception {
+        ScriptStats stats = new ScriptStats(5, 6, 7, new TimeSeries(10, 20, 30, 40), new TimeSeries(100, 200, 300, 400));
+        final XContentBuilder builder = XContentFactory.jsonBuilder().prettyPrint();
+
+        builder.startObject();
+        for (var it = stats.toXContentChunked(ToXContent.EMPTY_PARAMS); it.hasNext();) {
+            it.next().toXContent(builder, ToXContent.EMPTY_PARAMS);
+        }
+        builder.endObject();
+        String expected = """
+            {
+              "script" : {
+                "compilations" : 5,
+                "cache_evictions" : 6,
+                "compilation_limit_triggered" : 7,
+                "compilations_history" : {
+                  "5m" : 10,
+                  "15m" : 20,
+                  "24h" : 30
+                },
+                "cache_evictions_history" : {
+                  "5m" : 100,
+                  "15m" : 200,
+                  "24h" : 300
+                },
+                "contexts" : [ ]
+              }
+            }""";
+        assertThat(Strings.toString(builder), equalTo(expected));
+    }
+
     public void testSerializeEmptyTimeSeries() throws IOException {
         ScriptContextStats stats = new ScriptContextStats("c", 3333, new TimeSeries(1111), new TimeSeries(2222));
 

```
