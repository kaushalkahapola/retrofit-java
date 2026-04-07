# Full Trace of Agentic File Edits

## Attempt #1

### ReAct Agent Actions
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "insert_after",
  "resolution_reason": "exact",
  "resolved_old_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;",
  "resolved_new_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;\nimport static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 20,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Predicate;",
  "new_string": "import java.util.Map;\nimport java.util.Objects;\nimport static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n\nimport java.util.function.Function;\nimport org.elasticsearch.cluster.metadata.IndexMetadata;\nimport org.elasticsearch.common.settings.Settings;\nimport org.jetbrains.annotations.VisibleForTesting;",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        Predicate<String> indexFilter = indexName -> {\n            var indexMetadata = state.metadata().index(indexName);\n            if (indexMetadata != null) {\n                var routingTable = state.routingTable().index(indexName);\n                assert routingTable != null : \"routingTable must not be null\";\n                return routingTable.allPrimaryShardsActive();\n\n            }\n            // Partitioned table case (template, no index).\n            return true;\n        };",
  "new_string": "",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "skip indices where not all shards are active yet"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `get_exact_lines`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "start_line": 125,
  "end_line": 140
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `get_exact_lines`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "start_line": 130,
  "end_line": 140
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `get_exact_lines`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "start_line": 141,
  "end_line": 150
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        Predicate<String> indexFilter = indexName -> {\n            var indexMetadata = state.metadata().index(indexName);\n            if (indexMetadata != null) {\n                var routingTable = state.routingTable().index(indexName);\n                assert routingTable != null : \"routingTable must not be null\";\n                return routingTable.allPrimaryShardsActive();\n\n            }\n            // Partitioned table case (template, no index).\n            return true;\n        };",
  "new_string": "",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        Predicate<String> indexFilter = indexName -> {\n            var indexMetadata = state.metadata().index(indexName);\n            if (indexMetadata != null) {\n                var routingTable = state.routingTable().index(indexName);\n                assert routingTable != null : \"routingTable must not be null\";\n                return routingTable.allPrimaryShardsActive();\n\n            }\n            // Partitioned table case (template, no index).\n            return true;\n        };",
  "new_string": "",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "indexFilter"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `get_exact_lines`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "start_line": 170,
  "end_line": 185
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        return relations.stream()\n            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))",
  "new_string": "        return relations.stream()\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n    @VisibleForTesting\n    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        return im -> {\n            var routingTable = state.routingTable().index(im.getIndex());\n            assert routingTable != null : \"routingTable must not be null\";\n            boolean isActive = routingTable.allPrimaryShardsActive();\n            IndexMetadata.Builder builder = IndexMetadata.builder(im);\n            return builder.settings(Settings.builder()\n                    .put(im.getSettings())\n                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))\n                .build();\n        };\n    }\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `get_exact_lines`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "start_line": 175,
  "end_line": 185
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        return relations.stream()\n            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));",
  "new_string": "        return relations.stream()\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));\n    }\n\n    @VisibleForTesting\n    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        return im -> {\n            var routingTable = state.routingTable().index(im.getIndex());\n            assert routingTable != null : \"routingTable must not be null\";\n            boolean isActive = routingTable.allPrimaryShardsActive();\n            IndexMetadata.Builder builder = IndexMetadata.builder(im);\n            return builder.settings(Settings.builder()\n                    .put(im.getSettings())\n                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))\n                .build();\n        };\n    }"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 220,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 185,
  "radius": 40
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "    }\n\n    }\n\n    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {",
  "new_string": "    }\n\n    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java"
}
```

### Final Output Diff
**server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java b/server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java
index 6786ce5b5e..d7a466e0d2 100644
--- a/server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java
+++ b/server/src/main/java/io/crate/replication/logical/LogicalReplicationService.java
@@ -52,6 +52,7 @@ import org.elasticsearch.action.support.master.AcknowledgedResponse;
 import org.elasticsearch.client.Client;
 import org.elasticsearch.cluster.ClusterChangedEvent;
 import org.elasticsearch.cluster.ClusterStateListener;
+import org.elasticsearch.cluster.metadata.IndexMetadata;
 import org.elasticsearch.cluster.routing.allocation.AllocationService;
 import org.elasticsearch.cluster.service.ClusterService;
 import org.elasticsearch.common.Strings;
@@ -264,9 +265,10 @@ public class LogicalReplicationService implements ClusterStateListener, Closeabl
             );
             throw new RelationAlreadyExists(relation, message);
         };
-        for (var index : stateResponse.concreteIndices()) {
-            if (metadata.hasIndex(index)) {
-                onExists.accept(RelationName.fromIndexName(index));
+        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {
+            String indexName = indexMetadata.getIndex().getName();
+            if (metadata.hasIndex(indexName)) {
+                onExists.accept(RelationName.fromIndexName(indexName));
             }
         }
         for (var template : stateResponse.concreteTemplates()) {
```
**server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java b/server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java
index 11e05e2d93..2138aa808d 100644
--- a/server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java
+++ b/server/src/main/java/io/crate/replication/logical/LogicalReplicationSettings.java
@@ -102,6 +102,17 @@ public class LogicalReplicationSettings {
         Setting.Property.IndexScope
     );
 
+    /**
+     * Internal index setting to mark the index as active (all primary shards active) and such can be restored.
+     * It should be filtered out on the subscriber cluster when restoring or tracking indices.
+     */
+    public static final Setting<Boolean> REPLICATION_INDEX_ROUTING_ACTIVE = Setting.boolSetting(
+        "index.replication.logical.source_routing_active",
+        true,
+        Setting.Property.InternalIndex,
+        Setting.Property.IndexScope
+    );
+
     /**
      * These settings are not suitable to replicate between subscribed/replicated indices
      */
@@ -146,7 +157,8 @@ public class LogicalReplicationSettings {
         MergeSchedulerConfig.AUTO_THROTTLE_SETTING,
         MergeSchedulerConfig.MAX_MERGE_COUNT_SETTING,
         MergeSchedulerConfig.MAX_THREAD_COUNT_SETTING,
-        EngineConfig.INDEX_CODEC_SETTING
+        EngineConfig.INDEX_CODEC_SETTING,
+        REPLICATION_INDEX_ROUTING_ACTIVE
     );
 
     private int batchSize;
```
**server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java b/server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java
index d9914c03aa..430c2efb80 100644
--- a/server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java
+++ b/server/src/main/java/io/crate/replication/logical/action/PublicationsStateAction.java
@@ -39,6 +39,7 @@ import org.elasticsearch.action.support.master.TransportMasterNodeReadAction;
 import org.elasticsearch.cluster.ClusterState;
 import org.elasticsearch.cluster.block.ClusterBlockException;
 import org.elasticsearch.cluster.block.ClusterBlockLevel;
+import org.elasticsearch.cluster.metadata.IndexMetadata;
 import org.elasticsearch.cluster.service.ClusterService;
 import org.elasticsearch.common.inject.Inject;
 import org.elasticsearch.common.inject.Singleton;
@@ -218,10 +219,9 @@ public class PublicationsStateAction extends ActionType<PublicationsStateAction.
             return "Response{" + "relationsInPublications:" + relationsInPublications + '.' + "unknownPublications:" + unknownPublications + '}';
         }
 
-        public List<String> concreteIndices() {
+        public List<IndexMetadata> concreteIndices() {
             return relationsInPublications.values().stream()
                 .flatMap(x -> x.indices().stream())
-                .map(x -> x.getIndex().getName())
                 .toList();
         }
```
**server/src/main/java/io/crate/replication/logical/metadata/Publication.java** [replace]
```diff
diff --git a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
index 9e87dcd277..305db8f5e7 100644
--- a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
+++ b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
@@ -27,7 +27,12 @@ import java.util.HashSet;
 import java.util.List;
 import java.util.Map;
 import java.util.Objects;
-import java.util.function.Predicate;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+
+import java.util.function.Function;
+import org.elasticsearch.cluster.metadata.IndexMetadata;
+import org.elasticsearch.common.settings.Settings;
+import org.jetbrains.annotations.VisibleForTesting;
 import java.util.stream.Collectors;
 
 import org.apache.logging.log4j.LogManager;
@@ -169,12 +174,25 @@ public class Publication implements Writeable {
         }
 
         return relations.stream()
-            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))
+            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))
             .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))
             .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))
-            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))
             .collect(Collectors.toMap(RelationMetadata::name, x -> x));
+    }
 
+    @VisibleForTesting
+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {
+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned
+        return im -> {
+            var routingTable = state.routingTable().index(im.getIndex());
+            assert routingTable != null : "routingTable must not be null";
+            boolean isActive = routingTable.allPrimaryShardsActive();
+            IndexMetadata.Builder builder = IndexMetadata.builder(im);
+            return builder.settings(Settings.builder()
+                    .put(im.getSettings())
+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))
+                .build();
+        };
     }
 
     private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {
```
**server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java b/server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java
index e26916a648..fd912fdb71 100644
--- a/server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java
+++ b/server/src/main/java/io/crate/replication/logical/metadata/RelationMetadata.java
@@ -24,7 +24,7 @@ package io.crate.replication.logical.metadata;
 import java.io.IOException;
 import java.util.ArrayList;
 import java.util.List;
-import java.util.function.Predicate;
+import java.util.function.Function;
 
 import org.elasticsearch.action.support.IndicesOptions;
 import org.elasticsearch.cluster.metadata.IndexMetadata;
@@ -58,7 +58,9 @@ public record RelationMetadata(RelationName name,
         out.writeOptionalWriteable(template);
     }
 
-    public static RelationMetadata fromMetadata(RelationName table, Metadata metadata, Predicate<String> filter) {
+    public static RelationMetadata fromMetadata(RelationName table,
+                                                Metadata metadata,
+                                                Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings) {
         String indexNameOrAlias = table.indexNameOrAlias();
         var indexMetadata = metadata.index(indexNameOrAlias);
         if (indexMetadata == null) {
@@ -71,12 +73,14 @@ public record RelationMetadata(RelationName name,
             );
             ArrayList<IndexMetadata> indicesMetadata = new ArrayList<>(concreteIndices.length);
             for (String concreteIndex : concreteIndices) {
-                if (filter.test(concreteIndex)) {
-                    indicesMetadata.add(metadata.index(concreteIndex));
+                IndexMetadata concreteIndexMetadata = metadata.index(concreteIndex);
+                if (concreteIndexMetadata == null) {
+                    continue;
                 }
+                indicesMetadata.add(applyCustomIndexSettings.apply(concreteIndexMetadata));
             }
             return new RelationMetadata(table, indicesMetadata, templateMetadata);
         }
-        return new RelationMetadata(table, List.of(indexMetadata), null);
+        return new RelationMetadata(table, List.of(applyCustomIndexSettings.apply(indexMetadata)), null);
     }
 }
```
**server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
index 40c6e8cfd0..ba72c31f98 100644
--- a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
+++ b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
@@ -22,6 +22,7 @@
 package io.crate.replication.logical.repository;
 
 import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
 import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_SUBSCRIPTION_NAME;
 
 import java.io.IOException;
@@ -149,7 +150,14 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
         assert SNAPSHOT_ID.equals(snapshotId) : "SubscriptionRepository only supports " + SNAPSHOT_ID + " as the SnapshotId";
         return getPublicationsState()
             .thenApply(stateResponse ->
-                new SnapshotInfo(snapshotId, stateResponse.concreteIndices(), SnapshotState.SUCCESS, Version.CURRENT));
+                new SnapshotInfo(
+                    snapshotId,
+                    stateResponse.concreteIndices().stream()
+                        .filter(im -> REPLICATION_INDEX_ROUTING_ACTIVE.get(im.getSettings()))
+                        .map(im -> im.getIndex().getName()).toList(),
+                    SnapshotState.SUCCESS,
+                    Version.CURRENT
+                ));
     }
 
     @Override
@@ -194,9 +202,11 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
                 builder.put(REPLICATION_SUBSCRIPTION_NAME.getKey(), subscriptionName);
                 // Store publishers original index UUID to be able to resolve the original index later on
                 builder.put(PUBLISHER_INDEX_UUID.getKey(), indexMetadata.getIndexUUID());
+                // Remove source routing active setting, it is only used as a marker to not restore these indices (yet)
+                builder.remove(REPLICATION_INDEX_ROUTING_ACTIVE.getKey());
 
                 var indexMdBuilder = IndexMetadata.builder(indexMetadata).settings(builder);
-                indexMetadata.getAliases().valuesIt().forEachRemaining(a -> indexMdBuilder.putAlias(a));
+                indexMetadata.getAliases().valuesIt().forEachRemaining(indexMdBuilder::putAlias);
                 result.add(indexMdBuilder.build());
             }
             return result;
```

## Attempt #2

### ReAct Agent Actions
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.io.Closeable;",
  "resolved_new_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\nimport java.io.Closeable;"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndex",
  "resolved_new_preview": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationNa"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "            } else if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "        for (var templateName : stateResponse.concreteTemplates()) {",
  "resolved_new_preview": "\n        for (var templateName : stateResponse.concreteTemplates()) {"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "import java.io.Closeable;",
  "new_string": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\nimport java.io.Closeable;"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndexName(index))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)",
  "new_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "            if (!subscriberMetadata.hasIndex(indexName)) {",
  "new_string": "            if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);\n            }\n            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n                // If the index is not active, we cannot restore it\n                if (LOGGER.isDebugEnabled()) {\n                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n                }\n                continue;\n            }\n            if (!subscriberMetadata.hasIndex(indexName)) {"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "            } else if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);",
  "new_string": ""
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 400,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndexName(index))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)",
  "new_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 405,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndexName(index))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)",
  "new_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 405,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)\n            .collect(Collectors.toCollection(() -> new HashSet<>()));",
  "new_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)\n            .collect(Collectors.toCollection(HashSet::new));"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 460,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        var toRestoreTemplates = new ArrayList<String>();\n\n        for (var indexName : stateResponse.concreteIndices()) {\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n\n            }\n        }",
  "new_string": "        var toRestoreTemplates = new ArrayList<String>();\n\n        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {\n            String indexName = indexMetadata.getIndex().getName();\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);\n            }\n            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n                // If the index is not active, we cannot restore it\n                if (LOGGER.isDebugEnabled()) {\n                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n                }\n                continue;\n            }\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n            }\n        }"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "            } else if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);",
  "new_string": ""
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `git_diff_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `verify_guidelines`
```json
{
  "diff_text": "diff --git a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\nindex f39e910cfc..b589dd7181 100644\n--- a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\n+++ b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\n@@ -24,6 +24,8 @@ package io.crate.replication.logical;\n import static io.crate.replication.logical.LogicalReplicationSettings.NON_REPLICATED_SETTINGS;\n import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;\n \n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n import java.io.Closeable;\n import java.util.ArrayList;\n import java.util.Collection;\n@@ -402,10 +404,10 @@ public final class MetadataTracker implements Closeable {\n         Set<RelationName> currentlyReplicatedTables = subscription.relations().keySet();\n \n         Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n-            .filter(index -> metadata.hasIndex(index))\n-            .map(index -> RelationName.fromIndexName(index))\n+            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n+            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n             .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)\n-            .collect(Collectors.toCollection(() -> new HashSet<>()));\n+            .collect(Collectors.toCollection(HashSet::new));\n \n         for (String t: publisherStateResponse.concreteTemplates()) {\n             if (metadata.templates().containsKey(t)) {\n@@ -437,15 +439,25 @@ public final class MetadataTracker implements Closeable {\n         var toRestoreIndices = new ArrayList<String>();\n         var toRestoreTemplates = new ArrayList<String>();\n \n-        for (var indexName : stateResponse.concreteIndices()) {\n+        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {\n+            String indexName = indexMetadata.getIndex().getName();\n             var relationName = RelationName.fromIndexName(indexName);\n+            if (subscribedRelations.get(relationName) == null) {\n+                relationNamesForStateUpdate.add(relationName);\n+            }\n+            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n+                // If the index is not active, we cannot restore it\n+                if (LOGGER.isDebugEnabled()) {\n+                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n+                }\n+                continue;\n+            }\n             if (subscriberState.metadata().hasIndex(indexName) == false) {\n                 toRestoreIndices.add(indexName);\n                 relationNamesForStateUpdate.add(relationName);\n-            } else if (subscribedRelations.get(relationName) == null) {\n-                relationNamesForStateUpdate.add(relationName);\n             }\n         }\n+\n         for (var templateName : stateResponse.concreteTemplates()) {\n             var indexParts = IndexName.decode(templateName);\n             if (indexParts.isPartitioned()) {\n"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.io.IOException;",
  "resolved_new_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n\nimport java.io.IOException;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Predicate;\nimport java.util.stream.Collectors;",
  "resolved_new_preview": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Function;\nimport java.util.stream.Collectors;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.elasticsearch.cluster.metadata.Metadata;",
  "resolved_new_preview": "import org.elasticsearch.cluster.metadata.IndexMetadata;\nimport org.elasticsearch.cluster.metadata.Metadata;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import io.crate.metadata.IndexName;",
  "resolved_new_preview": "import org.elasticsearch.common.settings.Settings;\nimport org.jetbrains.annotations.VisibleForTesting;\nimport io.crate.metadata.IndexName;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publi",
  "resolved_new_preview": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publi"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {",
  "resolved_new_preview": "    @VisibleForTesting\n    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n        // mark indices where not all shards are active yet, restore will"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 20,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 120,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 160,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 200,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import java.io.IOException;",
  "new_string": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n\nimport java.io.IOException;",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Predicate;\nimport java.util.stream.Collectors;",
  "new_string": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Function;\nimport java.util.stream.Collectors;",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 30,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Predicate;\nimport java.util.stream.Collectors;",
  "new_string": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Function;\nimport java.util.stream.Collectors;",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 32,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import java.util.function.Predicate;",
  "new_string": "",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n\nimport java.io.IOException;",
  "new_string": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\nimport org.elasticsearch.common.settings.Settings;\nimport org.jetbrains.annotations.VisibleForTesting;\n\nimport java.io.IOException;",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "    // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n    Predicate<String> indexFilter = indexName -> {\n        var indexMetadata = state.metadata().index(indexName);\n        if (indexMetadata != null) {\n            boolean softDeletes = IndexSettings.INDEX_SOFT_DELETES_SETTING.get(indexMetadata.getSettings());\n            if (softDeletes == false) {\n                LOGGER.warn(\n                    \"Table '{}' won't be replicated as the required table setting \" +\n                        \"'soft_deletes.enabled' is set to: {}\",\n                    RelationName.fromIndexName(indexName),\n                    softDeletes\n                );\n                return false;\n            }\n            var routingTable = state.routingTable().index(indexName);\n            assert routingTable != null : \"routingTable must not be null\";\n            return routingTable.allPrimaryShardsActive();\n\n        }\n        // Partitioned table case (template, no index).\n        return true;\n    };",
  "new_string": "    var relations = new HashSet<RelationName>();\n\n    if (isForAllTables()) {\n        Metadata metadata = state.metadata();\n        for (var table : metadata.relations(org.elasticsearch.cluster.metadata.RelationMetadata.Table.class)) {\n            relations.add(table.ident());\n        }\n    } else {\n        relations.addAll(tables);\n    }\n\n    return relations.stream()",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));\n\n    }",
  "new_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));\n    }",
  "replace_all": false
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {\n        boolean canRead = roles.hasPrivilege(subscriber, Permission.DQL, Securable.TABLE, relationName.fqn());\n        if (canRead == false) {\n            if (LOGGER.isInfoEnabled()) {\n                LOGGER.info(\"User {} subscribed to the publication {} doesn't have DQL privilege on the table {}, this table will not be replicated.\",\n                    subscriber.name(), publicationName, relationName.fqn());\n            }\n        }\n        return canRead;\n    }",
  "new_string": "    @VisibleForTesting\n    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        return im -> {\n            var routingTable = state.routingTable().index(im.getIndex());\n            assert routingTable != null : \"routingTable must not be null\";\n            boolean isActive = routingTable.allPrimaryShardsActive();\n            IndexMetadata.Builder builder = IndexMetadata.builder(im);\n            return builder.settings(Settings.builder()\n                    .put(im.getSettings())\n                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))\n                .build();\n        };\n    }\n\n    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {\n        boolean canRead = roles.hasPrivilege(subscriber, Permission.DQL, Securable.TABLE, relationName.fqn());\n        if (canRead == false) {\n            if (LOGGER.isInfoEnabled()) {\n                LOGGER.info(\"User {} subscribed to the publication {} doesn't have DQL privilege on the table {}, this table will not be replicated.\",\n                    subscriber.name(), publicationName, relationName.fqn());\n            }\n        }\n        return canRead;\n    }"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `git_diff_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `verify_guidelines`
```json
{
  "diff_text": "diff --git a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java\nindex 9e87dcd277..e84690d35d 100644\n--- a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java\n+++ b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java\n@@ -21,24 +21,33 @@\n \n package io.crate.replication.logical.metadata;\n \n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n+\n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n+import org.elasticsearch.common.settings.Settings;\n+import org.jetbrains.annotations.VisibleForTesting;\n+\n import java.io.IOException;\n import java.util.ArrayList;\n import java.util.HashSet;\n import java.util.List;\n import java.util.Map;\n import java.util.Objects;\n-import java.util.function.Predicate;\n+import java.util.function.Function;\n import java.util.stream.Collectors;\n \n import org.apache.logging.log4j.LogManager;\n import org.apache.logging.log4j.Logger;\n import org.elasticsearch.cluster.ClusterState;\n+import org.elasticsearch.cluster.metadata.IndexMetadata;\n import org.elasticsearch.cluster.metadata.Metadata;\n import org.elasticsearch.common.io.stream.StreamInput;\n import org.elasticsearch.common.io.stream.StreamOutput;\n import org.elasticsearch.common.io.stream.Writeable;\n import org.elasticsearch.index.IndexSettings;\n \n+import org.elasticsearch.common.settings.Settings;\n+import org.jetbrains.annotations.VisibleForTesting;\n import io.crate.metadata.IndexName;\n import io.crate.metadata.IndexParts;\n import io.crate.metadata.RelationName;\n@@ -169,12 +178,41 @@ public class Publication implements Writeable {\n         }\n \n         return relations.stream()\n-            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias())\n+\n             .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n             .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n-            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))\n+            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n             .collect(Collectors.toMap(RelationMetadata::name, x -> x));\n+    }\n \n+    @VisibleForTesting\n+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n+        return im -> {\n+            var routingTable = state.routingTable().index(im.getIndex());\n+            assert routingTable != null : \"routingTable must not be null\";\n+            boolean isActive = routingTable.allPrimaryShardsActive();\n+            IndexMetadata.Builder builder = IndexMetadata.builder(im);\n+            return builder.settings(Settings.builder()\n+                    .put(im.getSettings())\n+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))\n+                .build();\n+        };\n+    }\n+\n+    @VisibleForTesting\n+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n+        return im -> {\n+            var routingTable = state.routingTable().index(im.getIndex());\n+            assert routingTable != null : \"routingTable must not be null\";\n+            boolean isActive = routingTable.allPrimaryShardsActive();\n+            IndexMetadata.Builder builder = IndexMetadata.builder(im);\n+            return builder.settings(Settings.builder()\n+                    .put(im.getSettings())\n+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))\n+                .build();\n+        };\n+    }\n \n-    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {\n-        boolean canRead = roles.hasPrivilege(subscriber, Permission.DQL, Securable.TABLE, relationName.fqn());\n-        if (canRead == false) {\n-            if (LOGGER.isInfoEnabled()) {\n-                LOGGER.info(\"User {} subscribed to the publication {} doesn't have DQL privilege on the table {}, this table will not be replicated.\",\n-                    subscriber.name(), publicationName, relationName.fqn());\n-            }\n-        }\n-        return canRead;\n-    }\n+    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {\n+        boolean canRead = roles.hasPrivilege(subscriber, Permission.DQL, Securable.TABLE, relationName.fqn());\n+        if (canRead == false) {\n+            if (LOGGER.isInfoEnabled()) {\n+                LOGGER.info(\"User {} subscribed to the publication {} doesn't have DQL privilege on the table {}, this table will not be replicated.\",\n+                    subscriber.name(), publicationName, relationName.fqn());\n+            }\n+        }\n+        return canRead;\n+    }\n"
}
```

### Final Output Diff
**server/src/main/java/io/crate/replication/logical/MetadataTracker.java** [replace]
```diff
diff --git a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
index f39e910cfc..b589dd7181 100644
--- a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
+++ b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
@@ -24,6 +24,8 @@ package io.crate.replication.logical;
 import static io.crate.replication.logical.LogicalReplicationSettings.NON_REPLICATED_SETTINGS;
 import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;
 
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
 import java.io.Closeable;
 import java.util.ArrayList;
 import java.util.Collection;
@@ -402,10 +404,10 @@ public final class MetadataTracker implements Closeable {
         Set<RelationName> currentlyReplicatedTables = subscription.relations().keySet();
 
         Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()
-            .filter(index -> metadata.hasIndex(index))
-            .map(index -> RelationName.fromIndexName(index))
+            .filter(im -> metadata.hasIndex(im.getIndex().getName()))
+            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))
             .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)
-            .collect(Collectors.toCollection(() -> new HashSet<>()));
+            .collect(Collectors.toCollection(HashSet::new));
 
         for (String t: publisherStateResponse.concreteTemplates()) {
             if (metadata.templates().containsKey(t)) {
@@ -437,15 +439,25 @@ public final class MetadataTracker implements Closeable {
         var toRestoreIndices = new ArrayList<String>();
         var toRestoreTemplates = new ArrayList<String>();
 
-        for (var indexName : stateResponse.concreteIndices()) {
+        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {
+            String indexName = indexMetadata.getIndex().getName();
             var relationName = RelationName.fromIndexName(indexName);
+            if (subscribedRelations.get(relationName) == null) {
+                relationNamesForStateUpdate.add(relationName);
+            }
+            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {
+                // If the index is not active, we cannot restore it
+                if (LOGGER.isDebugEnabled()) {
+                    LOGGER.debug("Skipping index {} for subscription {} as it is not active", indexName, subscription);
+                }
+                continue;
+            }
             if (subscriberState.metadata().hasIndex(indexName) == false) {
                 toRestoreIndices.add(indexName);
                 relationNamesForStateUpdate.add(relationName);
-            } else if (subscribedRelations.get(relationName) == null) {
-                relationNamesForStateUpdate.add(relationName);
             }
         }
+
         for (var templateName : stateResponse.concreteTemplates()) {
             var indexParts = IndexName.decode(templateName);
             if (indexParts.isPartitioned()) {
```
**server/src/main/java/io/crate/replication/logical/metadata/Publication.java** [replace]
```diff
diff --git a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
index 9e87dcd277..e84690d35d 100644
--- a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
+++ b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
@@ -21,24 +21,33 @@
 
 package io.crate.replication.logical.metadata;
 
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+import org.elasticsearch.common.settings.Settings;
+import org.jetbrains.annotations.VisibleForTesting;
+
 import java.io.IOException;
 import java.util.ArrayList;
 import java.util.HashSet;
 import java.util.List;
 import java.util.Map;
 import java.util.Objects;
-import java.util.function.Predicate;
+import java.util.function.Function;
 import java.util.stream.Collectors;
 
 import org.apache.logging.log4j.LogManager;
 import org.apache.logging.log4j.Logger;
 import org.elasticsearch.cluster.ClusterState;
+import org.elasticsearch.cluster.metadata.IndexMetadata;
 import org.elasticsearch.cluster.metadata.Metadata;
 import org.elasticsearch.common.io.stream.StreamInput;
 import org.elasticsearch.common.io.stream.StreamOutput;
 import org.elasticsearch.common.io.stream.Writeable;
 import org.elasticsearch.index.IndexSettings;
 
+import org.elasticsearch.common.settings.Settings;
+import org.jetbrains.annotations.VisibleForTesting;
 import io.crate.metadata.IndexName;
 import io.crate.metadata.IndexParts;
 import io.crate.metadata.RelationName;
@@ -169,12 +178,41 @@ public class Publication implements Writeable {
         }
 
         return relations.stream()
-            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))
+
             .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))
             .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))
-            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))
+            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))
             .collect(Collectors.toMap(RelationMetadata::name, x -> x));
+    }
 
+    @VisibleForTesting
+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {
+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned
+        return im -> {
+            var routingTable = state.routingTable().index(im.getIndex());
+            assert routingTable != null : "routingTable must not be null";
+            boolean isActive = routingTable.allPrimaryShardsActive();
+            IndexMetadata.Builder builder = IndexMetadata.builder(im);
+            return builder.settings(Settings.builder()
+                    .put(im.getSettings())
+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))
+                .build();
+        };
+    }
+
+    @VisibleForTesting
+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {
+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned
+        return im -> {
+            var routingTable = state.routingTable().index(im.getIndex());
+            assert routingTable != null : "routingTable must not be null";
+            boolean isActive = routingTable.allPrimaryShardsActive();
+            IndexMetadata.Builder builder = IndexMetadata.builder(im);
+            return builder.settings(Settings.builder()
+                    .put(im.getSettings())
+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))
+                .build();
+        };
     }
 
     private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {
```
**server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
index 40c6e8cfd0..ba72c31f98 100644
--- a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
+++ b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
@@ -22,6 +22,7 @@
 package io.crate.replication.logical.repository;
 
 import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
 import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_SUBSCRIPTION_NAME;
 
 import java.io.IOException;
@@ -149,7 +150,14 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
         assert SNAPSHOT_ID.equals(snapshotId) : "SubscriptionRepository only supports " + SNAPSHOT_ID + " as the SnapshotId";
         return getPublicationsState()
             .thenApply(stateResponse ->
-                new SnapshotInfo(snapshotId, stateResponse.concreteIndices(), SnapshotState.SUCCESS, Version.CURRENT));
+                new SnapshotInfo(
+                    snapshotId,
+                    stateResponse.concreteIndices().stream()
+                        .filter(im -> REPLICATION_INDEX_ROUTING_ACTIVE.get(im.getSettings()))
+                        .map(im -> im.getIndex().getName()).toList(),
+                    SnapshotState.SUCCESS,
+                    Version.CURRENT
+                ));
     }
 
     @Override
@@ -194,9 +202,11 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
                 builder.put(REPLICATION_SUBSCRIPTION_NAME.getKey(), subscriptionName);
                 // Store publishers original index UUID to be able to resolve the original index later on
                 builder.put(PUBLISHER_INDEX_UUID.getKey(), indexMetadata.getIndexUUID());
+                // Remove source routing active setting, it is only used as a marker to not restore these indices (yet)
+                builder.remove(REPLICATION_INDEX_ROUTING_ACTIVE.getKey());
 
                 var indexMdBuilder = IndexMetadata.builder(indexMetadata).settings(builder);
-                indexMetadata.getAliases().valuesIt().forEachRemaining(a -> indexMdBuilder.putAlias(a));
+                indexMetadata.getAliases().valuesIt().forEachRemaining(indexMdBuilder::putAlias);
                 result.add(indexMdBuilder.build());
             }
             return result;
```

## Attempt #3

### ReAct Agent Actions
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.io.Closeable;",
  "resolved_new_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\nimport java.io.Closeable;"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndex",
  "resolved_new_preview": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationNa"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "            } else if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "        for (var templateName : stateResponse.concreteTemplates()) {",
  "resolved_new_preview": "\n        for (var templateName : stateResponse.concreteTemplates()) {"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "import java.io.Closeable;",
  "new_string": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\nimport java.io.Closeable;"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(index -> metadata.hasIndex(index))\n            .map(index -> RelationName.fromIndexName(index))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)",
  "new_string": "\n        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        ArrayList<TableOrPartition> toRestore = new ArrayList<>();\n        Metadata subscriberMetadata = subscriberState.metadata();\n        for (var indexName : stateResponse.concreteIndices()) {\n            IndexParts indexParts = IndexName.decode(indexName);",
  "new_string": "        var subscribedRelations = subscription.relations();\n        var relationNamesForStateUpdate = new HashSet<RelationName>();\n        var toRestoreIndices = new ArrayList<String>();\n        var toRestoreTemplates = new ArrayList<String>();\n\n        for (var indexMetadata : stateResponse.concreteIndices()) {\n            String indexName = indexMetadata.getIndex().getName();\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n            }\n            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n                // If the index is not active, we cannot restore it\n                if (LOGGER.isDebugEnabled()) {\n                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n                }\n                continue;\n            }\n            if (!subscriberMetadata.hasIndex(indexName)) {\n                String partitionIdent = indexParts.isPartitioned() ? indexParts.partitionIdent() : null;\n                toRestore.add(new TableOrPartition(relationName, partitionIdent));\n            }\n        }"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "            } else if (subscribedRelations.get(relationName) == null) {\n                relationNamesForStateUpdate.add(relationName);",
  "new_string": ""
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "\n        for (var templateName : stateResponse.concreteTemplates()) {",
  "new_string": "\n        for (var templateName : stateResponse.concreteTemplates()) {"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 400,
  "radius": 15
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)",
  "new_string": "        Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n            .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 440,
  "radius": 15
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 445,
  "radius": 15
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        ArrayList<TableOrPartition> toRestore = new ArrayList<>();\n        Metadata subscriberMetadata = subscriberState.metadata();\n        for (var indexName : stateResponse.concreteIndices()) {\n            IndexParts indexParts = IndexName.decode(indexName);",
  "new_string": "        var subscribedRelations = subscription.relations();\n        var relationNamesForStateUpdate = new HashSet<RelationName>();\n        var toRestoreIndices = new ArrayList<String>();\n        var toRestoreTemplates = new ArrayList<String>();\n\n        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {\n            String indexName = indexMetadata.getIndex().getName();\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n            }\n            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n                // If the index is not active, we cannot restore it\n                if (LOGGER.isDebugEnabled()) {\n                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n                }\n                continue;\n            }\n            if (!subscriberMetadata.hasIndex(indexName)) {\n                String partitionIdent = indexParts.isPartitioned() ? indexParts.partitionIdent() : null;\n                toRestore.add(new TableOrPartition(relationName, partitionIdent));\n            }\n        }"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "search_text": "toRestore = new ArrayList<>();"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "search_text": "RestoreDiff getRestoreDiff"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "center_line": 433,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java",
  "old_string": "        for (var indexName : stateResponse.concreteIndices()) {\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n\n            }\n        }",
  "new_string": "        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {\n            String indexName = indexMetadata.getIndex().getName();\n            var relationName = RelationName.fromIndexName(indexName);\n            if (subscriberState.metadata().hasIndex(indexName) == false) {\n                toRestoreIndices.add(indexName);\n                relationNamesForStateUpdate.add(relationName);\n            }\n            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n                // If the index is not active, we cannot restore it\n                if (LOGGER.isDebugEnabled()) {\n                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n                }\n                continue;\n            }\n        }"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `check_java_syntax`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `git_diff_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/MetadataTracker.java"
}
```
- **server/src/main/java/io/crate/replication/logical/MetadataTracker.java**: Called `verify_guidelines`
```json
{
  "diff_text": "diff --git a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\nindex f39e910cfc..f6558ddeeb 100644\n--- a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\n+++ b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java\n@@ -24,6 +24,8 @@ package io.crate.replication.logical;\n import static io.crate.replication.logical.LogicalReplicationSettings.NON_REPLICATED_SETTINGS;\n import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;\n \n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n import java.io.Closeable;\n import java.util.ArrayList;\n import java.util.Collection;\n@@ -402,8 +404,8 @@ public final class MetadataTracker implements Closeable {\n         Set<RelationName> currentlyReplicatedTables = subscription.relations().keySet();\n \n         Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()\n-            .filter(index -> metadata.hasIndex(index))\n-            .map(index -> RelationName.fromIndexName(index))\n+            .filter(im -> metadata.hasIndex(im.getIndex().getName()))\n+            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))\n             .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)\n             .collect(Collectors.toCollection(() -> new HashSet<>()));\n \n@@ -437,15 +439,22 @@ public final class MetadataTracker implements Closeable {\n         var toRestoreIndices = new ArrayList<String>();\n         var toRestoreTemplates = new ArrayList<String>();\n \n-        for (var indexName : stateResponse.concreteIndices()) {\n+        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {\n+            String indexName = indexMetadata.getIndex().getName();\n             var relationName = RelationName.fromIndexName(indexName);\n             if (subscriberState.metadata().hasIndex(indexName) == false) {\n                 toRestoreIndices.add(indexName);\n                 relationNamesForStateUpdate.add(relationName);\n-            } else if (subscribedRelations.get(relationName) == null) {\n-                relationNamesForStateUpdate.add(relationName);\n+            }\n+            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {\n+                // If the index is not active, we cannot restore it\n+                if (LOGGER.isDebugEnabled()) {\n+                    LOGGER.debug(\"Skipping index {} for subscription {} as it is not active\", indexName, subscription);\n+                }\n+                continue;\n             }\n         }\n+\n         for (var templateName : stateResponse.concreteTemplates()) {\n             var indexParts = IndexName.decode(templateName);\n             if (indexParts.isPartitioned()) {\n                 var relationName = indexParts.toRelationName();\n                 if (subscriberState.metadata().templates().get(templateName) == null) {"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.io.IOException;",
  "resolved_new_preview": "import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;\n\nimport java.io.IOException;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Predicate;\nimport java.util.stream.Collectors;",
  "resolved_new_preview": "import java.util.Map;\nimport java.util.Objects;\nimport java.util.function.Function;\nimport java.util.stream.Collectors;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.elasticsearch.cluster.metadata.Metadata;",
  "resolved_new_preview": "import org.elasticsearch.cluster.metadata.IndexMetadata;\nimport org.elasticsearch.cluster.metadata.Metadata;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import io.crate.metadata.IndexName;",
  "resolved_new_preview": "import org.elasticsearch.common.settings.Settings;\nimport org.jetbrains.annotations.VisibleForTesting;\nimport io.crate.metadata.IndexName;"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publi",
  "resolved_new_preview": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publi"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "    private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {",
  "resolved_new_preview": "    @VisibleForTesting\n    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {\n        // mark indices where not all shards are active yet, restore will"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 120,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 160,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 200,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "applyCustomIndexSettings",
  "max_results": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "Predicate<String> indexFilter",
  "max_results": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "applyCustomIndexSettings(ClusterState)",
  "max_results": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "applyCustomIndexSettings(ClusterState state)",
  "max_results": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `grep_in_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "search_text": "Predicate<String> indexFilter = indexName -> {",
  "max_results": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 130,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 150,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        Predicate<String> indexFilter = indexName -> {\n            var indexMetadata = state.metadata().index(indexName);\n            if (indexMetadata != null) {\n                var routingTable = state.routingTable().index(indexName);\n                assert routingTable != null : \"routingTable must not be null\";\n                return routingTable.allPrimaryShardsActive();\n\n            }\n            // Partitioned table case (template, no index).\n            return true;\n        };",
  "new_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        // Removed indexFilter predicate, replaced by applyCustomIndexSettings usage in stream mapping\n        "
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 120,
  "radius": 30
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        Predicate<String> indexFilter = indexName -> {\n            var indexMetadata = state.metadata().index(indexName);\n            if (indexMetadata != null) {\n                boolean softDeletes = IndexSettings.INDEX_SOFT_DELETES_SETTING.get(indexMetadata.getSettings());\n                if (softDeletes == false) {\n                    LOGGER.warn(\n                        \"Table '{}' won't be replicated as the required table setting \" +\n                            \"'soft_deletes.enabled' is set to: {}\",\n                        RelationName.fromIndexName(indexName),\n                        softDeletes\n                    );\n                    return false;\n                }\n                var routingTable = state.routingTable().index(indexName);\n                assert routingTable != null : \"routingTable must not be null\";\n                return routingTable.allPrimaryShardsActive();\n\n            }\n            // Partitioned table case (template, no index).\n            return true;\n        };",
  "new_string": "        // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned\n        // Removed indexFilter predicate, replaced by applyCustomIndexSettings usage in stream mapping\n        "
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));",
  "new_string": "            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 180,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 170,
  "radius": 20
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));",
  "new_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));"
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `read_file_window`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "center_line": 157,
  "radius": 10
}
```
- **server/src/main/java/io/crate/replication/logical/metadata/Publication.java**: Called `edit_file`
```json
{
  "file_path": "server/src/main/java/io/crate/replication/logical/metadata/Publication.java",
  "old_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));",
  "new_string": "        return relations.stream()\n\n            .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))\n            .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))\n            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))\n            .collect(Collectors.toMap(RelationMetadata::name, x -> x));"
}
```

### Final Output Diff
**server/src/main/java/io/crate/replication/logical/MetadataTracker.java** [replace]
```diff
diff --git a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
index f39e910cfc..f6558ddeeb 100644
--- a/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
+++ b/server/src/main/java/io/crate/replication/logical/MetadataTracker.java
@@ -24,6 +24,8 @@ package io.crate.replication.logical;
 import static io.crate.replication.logical.LogicalReplicationSettings.NON_REPLICATED_SETTINGS;
 import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;
 
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
 import java.io.Closeable;
 import java.util.ArrayList;
 import java.util.Collection;
@@ -402,8 +404,8 @@ public final class MetadataTracker implements Closeable {
         Set<RelationName> currentlyReplicatedTables = subscription.relations().keySet();
 
         Set<RelationName> existingRelations = publisherStateResponse.concreteIndices().stream()
-            .filter(index -> metadata.hasIndex(index))
-            .map(index -> RelationName.fromIndexName(index))
+            .filter(im -> metadata.hasIndex(im.getIndex().getName()))
+            .map(im -> RelationName.fromIndexName(im.getIndex().getName()))
             .filter(relationName -> currentlyReplicatedTables.contains(relationName) == false)
             .collect(Collectors.toCollection(() -> new HashSet<>()));
 
@@ -437,15 +439,22 @@ public final class MetadataTracker implements Closeable {
         var toRestoreIndices = new ArrayList<String>();
         var toRestoreTemplates = new ArrayList<String>();
 
-        for (var indexName : stateResponse.concreteIndices()) {
+        for (IndexMetadata indexMetadata : stateResponse.concreteIndices()) {
+            String indexName = indexMetadata.getIndex().getName();
             var relationName = RelationName.fromIndexName(indexName);
             if (subscriberState.metadata().hasIndex(indexName) == false) {
                 toRestoreIndices.add(indexName);
                 relationNamesForStateUpdate.add(relationName);
-            } else if (subscribedRelations.get(relationName) == null) {
-                relationNamesForStateUpdate.add(relationName);
+            }
+            if (REPLICATION_INDEX_ROUTING_ACTIVE.get(indexMetadata.getSettings()) == false) {
+                // If the index is not active, we cannot restore it
+                if (LOGGER.isDebugEnabled()) {
+                    LOGGER.debug("Skipping index {} for subscription {} as it is not active", indexName, subscription);
+                }
+                continue;
             }
         }
+
         for (var templateName : stateResponse.concreteTemplates()) {
             var indexParts = IndexName.decode(templateName);
             if (indexParts.isPartitioned()) {
```
**server/src/main/java/io/crate/replication/logical/metadata/Publication.java** [replace]
```diff
diff --git a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
index 9e87dcd277..0ad2f0afce 100644
--- a/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
+++ b/server/src/main/java/io/crate/replication/logical/metadata/Publication.java
@@ -21,24 +21,29 @@
 
 package io.crate.replication.logical.metadata;
 
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
+
 import java.io.IOException;
 import java.util.ArrayList;
 import java.util.HashSet;
 import java.util.List;
 import java.util.Map;
 import java.util.Objects;
-import java.util.function.Predicate;
+import java.util.function.Function;
 import java.util.stream.Collectors;
 
 import org.apache.logging.log4j.LogManager;
 import org.apache.logging.log4j.Logger;
 import org.elasticsearch.cluster.ClusterState;
+import org.elasticsearch.cluster.metadata.IndexMetadata;
 import org.elasticsearch.cluster.metadata.Metadata;
 import org.elasticsearch.common.io.stream.StreamInput;
 import org.elasticsearch.common.io.stream.StreamOutput;
 import org.elasticsearch.common.io.stream.Writeable;
 import org.elasticsearch.index.IndexSettings;
 
+import org.elasticsearch.common.settings.Settings;
+import org.jetbrains.annotations.VisibleForTesting;
 import io.crate.metadata.IndexName;
 import io.crate.metadata.IndexParts;
 import io.crate.metadata.RelationName;
@@ -122,27 +127,8 @@ public class Publication implements Writeable {
                                                                        Role subscriber,
                                                                        String publicationName) {
         // skip indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned
-        Predicate<String> indexFilter = indexName -> {
-            var indexMetadata = state.metadata().index(indexName);
-            if (indexMetadata != null) {
-                boolean softDeletes = IndexSettings.INDEX_SOFT_DELETES_SETTING.get(indexMetadata.getSettings());
-                if (softDeletes == false) {
-                    LOGGER.warn(
-                        "Table '{}' won't be replicated as the required table setting " +
-                            "'soft_deletes.enabled' is set to: {}",
-                        RelationName.fromIndexName(indexName),
-                        softDeletes
-                    );
-                    return false;
-                }
-                var routingTable = state.routingTable().index(indexName);
-                assert routingTable != null : "routingTable must not be null";
-                return routingTable.allPrimaryShardsActive();
-
-            }
-            // Partitioned table case (template, no index).
-            return true;
-        };
+        // Removed indexFilter predicate, replaced by applyCustomIndexSettings usage in stream mapping
+        
 
         var relations = new HashSet<RelationName>();
 
@@ -169,14 +155,29 @@ public class Publication implements Writeable {
         }
 
         return relations.stream()
-            .filter(relationName -> indexFilter.test(relationName.indexNameOrAlias()))
+
             .filter(relationName -> userCanPublish(roles, relationName, publicationOwner, publicationName))
             .filter(relationName -> subscriberCanRead(roles, relationName, subscriber, publicationName))
-            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), indexFilter))
+            .map(relationName -> RelationMetadata.fromMetadata(relationName, state.metadata(), applyCustomIndexSettings(state)))
             .collect(Collectors.toMap(RelationMetadata::name, x -> x));
 
     }
 
+    @VisibleForTesting
+    public static Function<IndexMetadata, IndexMetadata> applyCustomIndexSettings(ClusterState state) {
+        // mark indices where not all shards are active yet, restore will fail if primaries are not (yet) assigned
+        return im -> {
+            var routingTable = state.routingTable().index(im.getIndex());
+            assert routingTable != null : "routingTable must not be null";
+            boolean isActive = routingTable.allPrimaryShardsActive();
+            IndexMetadata.Builder builder = IndexMetadata.builder(im);
+            return builder.settings(Settings.builder()
+                    .put(im.getSettings())
+                    .put(REPLICATION_INDEX_ROUTING_ACTIVE.getKey(), isActive))
+                .build();
+        };
+    }
+
     private static boolean subscriberCanRead(Roles roles, RelationName relationName, Role subscriber, String publicationName) {
         boolean canRead = roles.hasPrivilege(subscriber, Permission.DQL, Securable.TABLE, relationName.fqn());
         if (canRead == false) {
```
**server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java** [replace]
```java
// --- OLD ---
<mainline patch fast path>
// --- NEW ---
diff --git a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
index 40c6e8cfd0..ba72c31f98 100644
--- a/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
+++ b/server/src/main/java/io/crate/replication/logical/repository/LogicalReplicationRepository.java
@@ -22,6 +22,7 @@
 package io.crate.replication.logical.repository;
 
 import static io.crate.replication.logical.LogicalReplicationSettings.PUBLISHER_INDEX_UUID;
+import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_INDEX_ROUTING_ACTIVE;
 import static io.crate.replication.logical.LogicalReplicationSettings.REPLICATION_SUBSCRIPTION_NAME;
 
 import java.io.IOException;
@@ -149,7 +150,14 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
         assert SNAPSHOT_ID.equals(snapshotId) : "SubscriptionRepository only supports " + SNAPSHOT_ID + " as the SnapshotId";
         return getPublicationsState()
             .thenApply(stateResponse ->
-                new SnapshotInfo(snapshotId, stateResponse.concreteIndices(), SnapshotState.SUCCESS, Version.CURRENT));
+                new SnapshotInfo(
+                    snapshotId,
+                    stateResponse.concreteIndices().stream()
+                        .filter(im -> REPLICATION_INDEX_ROUTING_ACTIVE.get(im.getSettings()))
+                        .map(im -> im.getIndex().getName()).toList(),
+                    SnapshotState.SUCCESS,
+                    Version.CURRENT
+                ));
     }
 
     @Override
@@ -194,9 +202,11 @@ public class LogicalReplicationRepository extends AbstractLifecycleComponent imp
                 builder.put(REPLICATION_SUBSCRIPTION_NAME.getKey(), subscriptionName);
                 // Store publishers original index UUID to be able to resolve the original index later on
                 builder.put(PUBLISHER_INDEX_UUID.getKey(), indexMetadata.getIndexUUID());
+                // Remove source routing active setting, it is only used as a marker to not restore these indices (yet)
+                builder.remove(REPLICATION_INDEX_ROUTING_ACTIVE.getKey());
 
                 var indexMdBuilder = IndexMetadata.builder(indexMetadata).settings(builder);
-                indexMetadata.getAliases().valuesIt().forEachRemaining(a -> indexMdBuilder.putAlias(a));
+                indexMetadata.getAliases().valuesIt().forEachRemaining(indexMdBuilder::putAlias);
                 result.add(indexMdBuilder.build());
             }
             return result;
```