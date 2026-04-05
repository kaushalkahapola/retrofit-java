# Full Trace of Agentic File Edits

## Attempt #1

### Final Output Diff
**x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java** [replace]
```java
// --- OLD ---
<developer patch fast path>
// --- NEW ---
diff --git a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
index 302ccbd854b..2b799d98479 100644
--- a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
+++ b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
@@ -13,6 +13,7 @@ import org.elasticsearch.cluster.metadata.MappingMetadata;
 import org.elasticsearch.common.TriFunction;
 import org.elasticsearch.common.time.DateFormatter;
 import org.elasticsearch.common.time.LegacyFormatNames;
+import org.elasticsearch.core.Strings;
 import org.elasticsearch.index.IndexModule;
 import org.elasticsearch.index.IndexSettings;
 import org.elasticsearch.index.IndexVersion;
@@ -97,25 +98,39 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, false) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.CRITICAL,
-                "Old index with a compatibility version < 8.0",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "One or more Transforms write to this index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and requires action before upgrading to 9.0. The following transforms are "
+                            + "configured to write to this index: [%s]. Refer to the migration guide to learn more about how to prepare "
+                            + "transforms destination indices for your upgrade.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "Old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html",
+                    "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
 
-    private Map<String, Object> meta(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
-        var transforms = indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
-        if (transforms.isEmpty()) {
-            return Map.of("reindex_required", true);
-        } else {
-            return Map.of("reindex_required", true, "transform_ids", transforms);
-        }
+    private List<String> transformIdsForIndex(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
+        return indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
     }
 
     private DeprecationIssue ignoredOldIndicesCheck(
@@ -126,16 +141,35 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, true) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.WARNING,
-                "Old index with a compatibility version < 8.0 Has Been Ignored",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This read-only index has version: "
-                    + currentCompatibilityVersion.toReleaseVersion()
-                    + " and will be supported as read-only in 9.0",
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "One or more Transforms write to this old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and will be supported as a read-only index in 9.0. The following "
+                            + "transforms are no longer able to write to this index: [%s]. Refer to the migration guide to learn more "
+                            + "about how to handle your transforms destination indices.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "Old index with a compatibility version < 8.0 has been ignored",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/breaking-changes-9.0.html",
+                    "This read-only index has version: "
+                        + currentCompatibilityVersion.toReleaseVersion()
+                        + " and will be supported as read-only in 9.0",
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
```

## Attempt #2

### Final Output Diff
**x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java** [replace]
```java
// --- OLD ---
<developer patch fast path>
// --- NEW ---
diff --git a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
index 302ccbd854b..2b799d98479 100644
--- a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
+++ b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
@@ -13,6 +13,7 @@ import org.elasticsearch.cluster.metadata.MappingMetadata;
 import org.elasticsearch.common.TriFunction;
 import org.elasticsearch.common.time.DateFormatter;
 import org.elasticsearch.common.time.LegacyFormatNames;
+import org.elasticsearch.core.Strings;
 import org.elasticsearch.index.IndexModule;
 import org.elasticsearch.index.IndexSettings;
 import org.elasticsearch.index.IndexVersion;
@@ -97,25 +98,39 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, false) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.CRITICAL,
-                "Old index with a compatibility version < 8.0",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "One or more Transforms write to this index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and requires action before upgrading to 9.0. The following transforms are "
+                            + "configured to write to this index: [%s]. Refer to the migration guide to learn more about how to prepare "
+                            + "transforms destination indices for your upgrade.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "Old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html",
+                    "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
 
-    private Map<String, Object> meta(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
-        var transforms = indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
-        if (transforms.isEmpty()) {
-            return Map.of("reindex_required", true);
-        } else {
-            return Map.of("reindex_required", true, "transform_ids", transforms);
-        }
+    private List<String> transformIdsForIndex(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
+        return indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
     }
 
     private DeprecationIssue ignoredOldIndicesCheck(
@@ -126,16 +141,35 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, true) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.WARNING,
-                "Old index with a compatibility version < 8.0 Has Been Ignored",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This read-only index has version: "
-                    + currentCompatibilityVersion.toReleaseVersion()
-                    + " and will be supported as read-only in 9.0",
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "One or more Transforms write to this old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and will be supported as a read-only index in 9.0. The following "
+                            + "transforms are no longer able to write to this index: [%s]. Refer to the migration guide to learn more "
+                            + "about how to handle your transforms destination indices.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "Old index with a compatibility version < 8.0 has been ignored",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/breaking-changes-9.0.html",
+                    "This read-only index has version: "
+                        + currentCompatibilityVersion.toReleaseVersion()
+                        + " and will be supported as read-only in 9.0",
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
```

## Attempt #3

### Final Output Diff
**x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java** [replace]
```java
// --- OLD ---
<developer patch fast path>
// --- NEW ---
diff --git a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
index 302ccbd854b..2b799d98479 100644
--- a/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
+++ b/x-pack/plugin/deprecation/src/main/java/org/elasticsearch/xpack/deprecation/IndexDeprecationChecker.java
@@ -13,6 +13,7 @@ import org.elasticsearch.cluster.metadata.MappingMetadata;
 import org.elasticsearch.common.TriFunction;
 import org.elasticsearch.common.time.DateFormatter;
 import org.elasticsearch.common.time.LegacyFormatNames;
+import org.elasticsearch.core.Strings;
 import org.elasticsearch.index.IndexModule;
 import org.elasticsearch.index.IndexSettings;
 import org.elasticsearch.index.IndexVersion;
@@ -97,25 +98,39 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, false) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.CRITICAL,
-                "Old index with a compatibility version < 8.0",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "One or more Transforms write to this index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and requires action before upgrading to 9.0. The following transforms are "
+                            + "configured to write to this index: [%s]. Refer to the migration guide to learn more about how to prepare "
+                            + "transforms destination indices for your upgrade.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.CRITICAL,
+                    "Old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html",
+                    "This index has version: " + currentCompatibilityVersion.toReleaseVersion(),
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
 
-    private Map<String, Object> meta(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
-        var transforms = indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
-        if (transforms.isEmpty()) {
-            return Map.of("reindex_required", true);
-        } else {
-            return Map.of("reindex_required", true, "transform_ids", transforms);
-        }
+    private List<String> transformIdsForIndex(IndexMetadata indexMetadata, Map<String, List<String>> indexToTransformIds) {
+        return indexToTransformIds.getOrDefault(indexMetadata.getIndex().getName(), List.of());
     }
 
     private DeprecationIssue ignoredOldIndicesCheck(
@@ -126,16 +141,35 @@ public class IndexDeprecationChecker implements ResourceDeprecationChecker {
         IndexVersion currentCompatibilityVersion = indexMetadata.getCompatibilityVersion();
         // We intentionally exclude indices that are in data streams because they will be picked up by DataStreamDeprecationChecks
         if (DeprecatedIndexPredicate.reindexRequired(indexMetadata, true) && isNotDataStreamIndex(indexMetadata, clusterState)) {
-            return new DeprecationIssue(
-                DeprecationIssue.Level.WARNING,
-                "Old index with a compatibility version < 8.0 Has Been Ignored",
-                "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-8.0.html#breaking-changes-8.0",
-                "This read-only index has version: "
-                    + currentCompatibilityVersion.toReleaseVersion()
-                    + " and will be supported as read-only in 9.0",
-                false,
-                meta(indexMetadata, indexToTransformIds)
-            );
+            var transforms = transformIdsForIndex(indexMetadata, indexToTransformIds);
+            if (transforms.isEmpty() == false) {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "One or more Transforms write to this old index with a compatibility version < 8.0",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/migrating-9.0.html"
+                        + "#breaking_90_transform_destination_index",
+                    Strings.format(
+                        "This index was created in version [%s] and will be supported as a read-only index in 9.0. The following "
+                            + "transforms are no longer able to write to this index: [%s]. Refer to the migration guide to learn more "
+                            + "about how to handle your transforms destination indices.",
+                        currentCompatibilityVersion.toReleaseVersion(),
+                        String.join(", ", transforms)
+                    ),
+                    false,
+                    Map.of("reindex_required", true, "transform_ids", transforms)
+                );
+            } else {
+                return new DeprecationIssue(
+                    DeprecationIssue.Level.WARNING,
+                    "Old index with a compatibility version < 8.0 has been ignored",
+                    "https://www.elastic.co/guide/en/elasticsearch/reference/current/breaking-changes-9.0.html",
+                    "This read-only index has version: "
+                        + currentCompatibilityVersion.toReleaseVersion()
+                        + " and will be supported as read-only in 9.0",
+                    false,
+                    Map.of("reindex_required", true)
+                );
+            }
         }
         return null;
     }
```