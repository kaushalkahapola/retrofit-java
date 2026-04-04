# Full Trace of Agentic File Edits

## Attempt #1

### ReAct Agent Actions
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;",
  "resolved_new_preview": "import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 25,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 210,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 200,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 201,
  "radius": 5
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 28,
  "radius": 5
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATION_LIMIT_TRIGGERED;\nimport static org.elasticsearch.script.ScriptStats.Fields.CONTEXTS;\nimport static org.elasticsearch.script.ScriptStats.Fields.SCRIPT_STATS;",
  "new_string": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATION_LIMIT_TRIGGERED;\nimport static org.elasticsearch.script.ScriptStats.Fields.CONTEXTS;\nimport static org.elasticsearch.script.ScriptStats.Fields.SCRIPT_STATS;",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);\n            }",
  "new_string": "            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n            }",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 150,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 190,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `git_diff_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `verify_guidelines`
```json
{
  "diff_text": "diff --git a/server/src/main/java/org/elasticsearch/script/ScriptStats.java b/server/src/main/java/org/elasticsearch/script/ScriptStats.java\nindex f24052ef7e3..f4b62ad687b 100644\n--- a/server/src/main/java/org/elasticsearch/script/ScriptStats.java\n+++ b/server/src/main/java/org/elasticsearch/script/ScriptStats.java\n@@ -26,6 +26,7 @@ import java.util.Map;\n import java.util.Objects;\n \n import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\n+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\n import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\n import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;\n import static org.elasticsearch.script.ScriptStats.Fields.COMPILATION_LIMIT_TRIGGERED;\n@@ -199,7 +200,7 @@ public record ScriptStats(\n                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);\n             }\n             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n-                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);\n+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n             }\n             ob.array(CONTEXTS, contextStats.iterator());\n         });\n"
}
```

### Final Output Diff

## Attempt #2

### ReAct Agent Actions
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;",
  "resolved_new_preview": "import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `manage_todo`
```json
{
  "action": "add",
  "task": "Read file head to verify import section and locate existing imports around line 28"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 28,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;",
  "new_string": "import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\nimport static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\nimport static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 215,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 200,
  "radius": 15
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);\n            }",
  "new_string": "            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n            }",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 150,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 190,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 140,
  "radius": 20
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 153,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 170,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 190,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 203,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 150,
  "radius": 20
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 100,
  "radius": 20
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 50,
  "radius": 20
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 55,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "center_line": 153,
  "radius": 10
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "@Override"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "implements Writeable"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "writeTo"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "toXContentChunked"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "@Override\n    public Iterator<? extends ToXContent> toXContentChunked"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "public Iterator<? extends ToXContent> toXContentChunked"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "@Override\n    public void writeTo(StreamOutput out) throws IOException"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "search_text": "public void writeTo(StreamOutput out) throws IOException"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "    @Override\n    public Iterator<? extends ToXContent> toXContentChunked(ToXContent.Params params) {\n        return ChunkedToXContent.builder(params).object(SCRIPT_STATS, ob -> {\n            ob.field(COMPILATIONS, compilations);\n            ob.field(CACHE_EVICTIONS, cacheEvictions);\n            ob.field(COMPILATION_LIMIT_TRIGGERED, compilationLimitTriggered);\n            if (compilationsHistory != null && compilationsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);\n            }\n            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n            }\n            ob.array(CONTEXTS, contextStats.iterator());\n        });\n    }",
  "new_string": "    public Iterator<? extends ToXContent> toXContentChunked(ToXContent.Params params) {\n        return ChunkedToXContent.builder(params).object(SCRIPT_STATS, ob -> {\n            ob.field(COMPILATIONS, compilations);\n            ob.field(CACHE_EVICTIONS, cacheEvictions);\n            ob.field(COMPILATION_LIMIT_TRIGGERED, compilationLimitTriggered);\n            if (compilationsHistory != null && compilationsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);\n            }\n            if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n            }\n            ob.array(CONTEXTS, contextStats.iterator());\n        });\n    }",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "    @Override\n    public void writeTo(StreamOutput out) throws IOException {\n        if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {\n            compilationsHistory.writeTo(out);\n            cacheEvictionsHistory.writeTo(out);\n        } else {\n            out.writeVLong(compilations);\n            out.writeVLong(cacheEvictions);\n        }\n        out.writeVLong(compilationLimitTriggered);\n        out.writeCollection(contextStats);\n    }",
  "new_string": "    public void writeTo(StreamOutput out) throws IOException {\n        if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {\n            compilationsHistory.writeTo(out);\n            cacheEvictionsHistory.writeTo(out);\n        } else {\n            out.writeVLong(compilations);\n            out.writeVLong(cacheEvictions);\n        }\n        out.writeVLong(compilationLimitTriggered);\n        out.writeCollection(contextStats);\n    }",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `read_full_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java",
  "old_string": "    @Override\n    public void writeTo(StreamOutput out) throws IOException {\n        if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {\n            compilationsHistory.writeTo(out);\n            cacheEvictionsHistory.writeTo(out);\n        } else {\n            out.writeVLong(compilations);\n            out.writeVLong(cacheEvictions);\n        }\n        out.writeVLong(compilationLimitTriggered);\n        out.writeCollection(contextStats);\n    }",
  "new_string": "    public void writeTo(StreamOutput out) throws IOException {\n        if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {\n            compilationsHistory.writeTo(out);\n            cacheEvictionsHistory.writeTo(out);\n        } else {\n            out.writeVLong(compilations);\n            out.writeVLong(cacheEvictions);\n        }\n        out.writeVLong(compilationLimitTriggered);\n        out.writeCollection(contextStats);\n    }",
  "replace_all": false
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `git_diff_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/script/ScriptStats.java"
}
```
- **server/src/main/java/org/elasticsearch/script/ScriptStats.java**: Called `verify_guidelines`
```json
{
  "diff_text": "diff --git a/server/src/main/java/org/elasticsearch/script/ScriptStats.java b/server/src/main/java/org/elasticsearch/script/ScriptStats.java\nindex f24052ef7e3..f44a51e738d 100644\n--- a/server/src/main/java/org/elasticsearch/script/ScriptStats.java\n+++ b/server/src/main/java/org/elasticsearch/script/ScriptStats.java\n@@ -26,6 +26,7 @@ import java.util.Map;\n import java.util.Objects;\n \n import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;\n+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;\n import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;\n import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;\n import static org.elasticsearch.script.ScriptStats.Fields.COMPILATION_LIMIT_TRIGGERED;\n@@ -149,7 +150,6 @@ public record ScriptStats(\n         );\n     }\n \n-    @Override\n     public void writeTo(StreamOutput out) throws IOException {\n         if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {\n             compilationsHistory.writeTo(out);\n             cacheEvictionsHistory.writeTo(out);\n         } else {\n             out.writeVLong(compilations);\n             out.writeVLong(cacheEvictions);\n         }\n         out.writeVLong(compilationLimitTriggered);\n         out.writeCollection(contextStats);\n     }\n \n-    @Override\n     public Iterator<? extends ToXContent> toXContentChunked(ToXContent.Params params) {\n         return ChunkedToXContent.builder(params).object(SCRIPT_STATS, ob -> {\n             ob.field(COMPILATIONS, compilations);\n             ob.field(CACHE_EVICTIONS, cacheEvictions);\n             ob.field(COMPILATION_LIMIT_TRIGGERED, compilationLimitTriggered);\n             if (compilationsHistory != null && compilationsHistory.areTimingsEmpty() == false) {\n                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);\n             }\n             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {\n-                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);\n+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);\n             }\n             ob.array(CONTEXTS, contextStats.iterator());\n         });\n     }\n"
}
```

### Final Output Diff
**server/src/main/java/org/elasticsearch/script/ScriptStats.java** [replace]
```diff
diff --git a/server/src/main/java/org/elasticsearch/script/ScriptStats.java b/server/src/main/java/org/elasticsearch/script/ScriptStats.java
index f24052ef7e3..f44a51e738d 100644
--- a/server/src/main/java/org/elasticsearch/script/ScriptStats.java
+++ b/server/src/main/java/org/elasticsearch/script/ScriptStats.java
@@ -26,6 +26,7 @@ import java.util.Map;
 import java.util.Objects;
 
 import static org.elasticsearch.script.ScriptContextStats.Fields.COMPILATIONS_HISTORY;
+import static org.elasticsearch.script.ScriptContextStats.Fields.CACHE_EVICTIONS_HISTORY;
 import static org.elasticsearch.script.ScriptStats.Fields.CACHE_EVICTIONS;
 import static org.elasticsearch.script.ScriptStats.Fields.COMPILATIONS;
 import static org.elasticsearch.script.ScriptStats.Fields.COMPILATION_LIMIT_TRIGGERED;
@@ -149,7 +150,6 @@ public record ScriptStats(
         );
     }
 
-    @Override
     public void writeTo(StreamOutput out) throws IOException {
         if (out.getTransportVersion().onOrAfter(TransportVersions.V_8_1_0)) {
             compilationsHistory.writeTo(out);
@@ -189,7 +189,6 @@ public record ScriptStats(
         return new ScriptCacheStats(contexts);
     }
 
-    @Override
     public Iterator<? extends ToXContent> toXContentChunked(ToXContent.Params params) {
         return ChunkedToXContent.builder(params).object(SCRIPT_STATS, ob -> {
             ob.field(COMPILATIONS, compilations);
@@ -199,7 +198,7 @@ public record ScriptStats(
                 ob.xContentObject(COMPILATIONS_HISTORY, compilationsHistory);
             }
             if (cacheEvictionsHistory != null && cacheEvictionsHistory.areTimingsEmpty() == false) {
-                ob.xContentObject(COMPILATIONS_HISTORY, cacheEvictionsHistory);
+                ob.xContentObject(CACHE_EVICTIONS_HISTORY, cacheEvictionsHistory);
             }
             ob.array(CONTEXTS, contextStats.iterator());
         });
```