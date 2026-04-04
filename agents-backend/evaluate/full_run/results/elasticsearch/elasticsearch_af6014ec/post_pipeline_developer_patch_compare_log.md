# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']
- Developer Java files: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']
- Overlap Java files: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']

## File State Comparison
- Compared files: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']
- Mismatched files: ['server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java']
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java

- Developer hunks: 1
- Generated hunks: 0

#### Hunk 1

Developer
```diff
@@ -46,7 +46,7 @@
     static {
         PARSER.declareString(Builder::setId, new ParseField("id"));
         PARSER.declareField(
-            (parser, builder, aVoid) -> builder.setConfig(parser.map()),
+            (parser, builder, aVoid) -> builder.setConfig(parser.mapOrdered()),
             new ParseField("config"),
             ObjectParser.ValueType.OBJECT
         );

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -46,7 +46,7 @@
-     static {
-         PARSER.declareString(Builder::setId, new ParseField("id"));
-         PARSER.declareField(
--            (parser, builder, aVoid) -> builder.setConfig(parser.map()),
-+            (parser, builder, aVoid) -> builder.setConfig(parser.mapOrdered()),
-             new ParseField("config"),
-             ObjectParser.ValueType.OBJECT
-         );
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
diff --git a/docs/changelog/123403.yaml b/docs/changelog/123403.yaml
new file mode 100644
index 00000000000..836c4b685d7
--- /dev/null
+++ b/docs/changelog/123403.yaml
@@ -0,0 +1,5 @@
+pr: 123403
+summary: Use ordered maps for `PipelineConfiguration` xcontent deserialization
+area: Ingest Node
+type: bug
+issues: []
diff --git a/server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java b/server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java
index 9f3f3aaba62..44cd32b9103 100644
--- a/server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java
+++ b/server/src/main/java/org/elasticsearch/ingest/PipelineConfiguration.java
@@ -46,7 +46,7 @@ public final class PipelineConfiguration implements SimpleDiffable<PipelineConfi
     static {
         PARSER.declareString(Builder::setId, new ParseField("id"));
         PARSER.declareField(
-            (parser, builder, aVoid) -> builder.setConfig(parser.map()),
+            (parser, builder, aVoid) -> builder.setConfig(parser.mapOrdered()),
             new ParseField("config"),
             ObjectParser.ValueType.OBJECT
         );
diff --git a/server/src/test/java/org/elasticsearch/ingest/PipelineConfigurationTests.java b/server/src/test/java/org/elasticsearch/ingest/PipelineConfigurationTests.java
index 7be6e97762c..78e3213e690 100644
--- a/server/src/test/java/org/elasticsearch/ingest/PipelineConfigurationTests.java
+++ b/server/src/test/java/org/elasticsearch/ingest/PipelineConfigurationTests.java
@@ -28,9 +28,11 @@ import java.io.IOException;
 import java.nio.charset.StandardCharsets;
 import java.util.HashMap;
 import java.util.Map;
+import java.util.Set;
 import java.util.function.Predicate;
 
 import static org.hamcrest.Matchers.anEmptyMap;
+import static org.hamcrest.Matchers.contains;
 import static org.hamcrest.Matchers.equalTo;
 import static org.hamcrest.Matchers.not;
 import static org.hamcrest.Matchers.sameInstance;
@@ -143,6 +145,41 @@ public class PipelineConfigurationTests extends AbstractXContentTestCase<Pipelin
         }
     }
 
+    @SuppressWarnings("unchecked")
+    public void testMapKeyOrderingRoundTrip() throws IOException {
+        // make up two random keys
+        String key1 = randomAlphaOfLength(10);
+        String key2 = randomValueOtherThan(key1, () -> randomAlphaOfLength(10));
+        // stick them as mappings onto themselves in the _meta of a pipeline configuration
+        // this happens to use the _meta as a convenient map to test that the ordering of the key sets is the same
+        String configJson = Strings.format("""
+            {"description": "blah", "_meta" : {"foo": "bar", "%s": "%s", "%s": "%s"}}""", key1, key1, key2, key2);
+        PipelineConfiguration configuration = new PipelineConfiguration(
+            "1",
+            new BytesArray(configJson.getBytes(StandardCharsets.UTF_8)),
+            XContentType.JSON
+        );
+
+        // serialize it to bytes
+        XContentType xContentType = randomFrom(XContentType.values());
+        final BytesReference bytes;
+        try (XContentBuilder builder = XContentBuilder.builder(xContentType.xContent())) {
+            configuration.toXContent(builder, ToXContent.EMPTY_PARAMS);
+            bytes = BytesReference.bytes(builder);
+        }
+
+        // deserialize it back
+        ContextParser<Void, PipelineConfiguration> parser = PipelineConfiguration.getParser();
+        XContentParser xContentParser = xContentType.xContent()
+            .createParser(NamedXContentRegistry.EMPTY, DeprecationHandler.THROW_UNSUPPORTED_OPERATION, bytes.streamInput());
+        PipelineConfiguration parsed = parser.parse(xContentParser, null);
+
+        // make sure the _meta key sets are in the same order
+        Set<String> keys1 = ((Map<String, Object>) configuration.getConfig().get("_meta")).keySet();
+        Set<String> keys2 = ((Map<String, Object>) parsed.getConfig().get("_meta")).keySet();
+        assertThat(keys1, contains(keys2.toArray(new String[0])));
+    }
+
     @Override
     protected PipelineConfiguration createTestInstance() {
         BytesArray config;

```
