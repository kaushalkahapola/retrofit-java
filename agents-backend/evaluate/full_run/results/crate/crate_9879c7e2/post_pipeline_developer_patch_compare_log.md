# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']
- Developer Java files: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']
- Overlap Java files: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']

## File State Comparison
- Compared files: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']
- Mismatched files: ['server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java']
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java

- Developer hunks: 5
- Generated hunks: 0

#### Hunk 1

Developer
```diff
@@ -454,6 +454,11 @@
         return Builder.fromXContent(parser, false);
     }
 
+    private static boolean hasGlobalColumnOID(Version version) {
+        return version.onOrAfter(Version.V_5_5_0) &&
+            (version.onOrBefore(Version.V_6_0_3) || version.equals(Version.V_6_1_0));
+    }
+
     private static class MetadataDiff implements Diff<Metadata> {
 
         private final long version;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,12 +1 @@-@@ -454,6 +454,11 @@
-         return Builder.fromXContent(parser, false);
-     }
- 
-+    private static boolean hasGlobalColumnOID(Version version) {
-+        return version.onOrAfter(Version.V_5_5_0) &&
-+            (version.onOrBefore(Version.V_6_0_3) || version.equals(Version.V_6_1_0));
-+    }
-+
-     private static class MetadataDiff implements Diff<Metadata> {
- 
-         private final long version;
+*No hunk*
```

#### Hunk 2

Developer
```diff
@@ -494,7 +499,7 @@
             clusterUUID = in.readString();
             clusterUUIDCommitted = in.readBoolean();
             version = in.readLong();
-            if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
+            if (hasGlobalColumnOID(in.getVersion())) {
                 columnOID = in.readLong();
             } else {
                 columnOID = COLUMN_OID_UNASSIGNED;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -494,7 +499,7 @@
-             clusterUUID = in.readString();
-             clusterUUIDCommitted = in.readBoolean();
-             version = in.readLong();
--            if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
-+            if (hasGlobalColumnOID(in.getVersion())) {
-                 columnOID = in.readLong();
-             } else {
-                 columnOID = COLUMN_OID_UNASSIGNED;
+*No hunk*
```

#### Hunk 3

Developer
```diff
@@ -521,7 +526,7 @@
             out.writeString(clusterUUID);
             out.writeBoolean(clusterUUIDCommitted);
             out.writeLong(version);
-            if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
+            if (hasGlobalColumnOID(out.getVersion())) {
                 out.writeLong(columnOID);
             }
             coordinationMetadata.writeTo(out);

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -521,7 +526,7 @@
-             out.writeString(clusterUUID);
-             out.writeBoolean(clusterUUIDCommitted);
-             out.writeLong(version);
--            if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
-+            if (hasGlobalColumnOID(out.getVersion())) {
-                 out.writeLong(columnOID);
-             }
-             coordinationMetadata.writeTo(out);
+*No hunk*
```

#### Hunk 4

Developer
```diff
@@ -556,7 +561,7 @@
     public static Metadata readFrom(StreamInput in) throws IOException {
         Builder builder = new Builder();
         builder.version = in.readLong();
-        if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
+        if (hasGlobalColumnOID(in.getVersion())) {
             builder.columnOID(in.readLong());
         }
         builder.clusterUUID = in.readString();

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -556,7 +561,7 @@
-     public static Metadata readFrom(StreamInput in) throws IOException {
-         Builder builder = new Builder();
-         builder.version = in.readLong();
--        if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
-+        if (hasGlobalColumnOID(in.getVersion())) {
-             builder.columnOID(in.readLong());
-         }
-         builder.clusterUUID = in.readString();
+*No hunk*
```

#### Hunk 5

Developer
```diff
@@ -597,7 +602,7 @@
     @Override
     public void writeTo(StreamOutput out) throws IOException {
         out.writeLong(version);
-        if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
+        if (hasGlobalColumnOID(out.getVersion())) {
             out.writeLong(columnOID);
         }
         out.writeString(clusterUUID);

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -597,7 +602,7 @@
-     @Override
-     public void writeTo(StreamOutput out) throws IOException {
-         out.writeLong(version);
--        if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
-+        if (hasGlobalColumnOID(out.getVersion())) {
-             out.writeLong(columnOID);
-         }
-         out.writeString(clusterUUID);
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
diff --git a/server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java b/server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java
index dc46e47046..ead62b5a59 100644
--- a/server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java
+++ b/server/src/main/java/org/elasticsearch/cluster/metadata/Metadata.java
@@ -454,6 +454,11 @@ public class Metadata implements Iterable<IndexMetadata>, Diffable<Metadata> {
         return Builder.fromXContent(parser, false);
     }
 
+    private static boolean hasGlobalColumnOID(Version version) {
+        return version.onOrAfter(Version.V_5_5_0) &&
+            (version.onOrBefore(Version.V_6_0_3) || version.equals(Version.V_6_1_0));
+    }
+
     private static class MetadataDiff implements Diff<Metadata> {
 
         private final long version;
@@ -494,7 +499,7 @@ public class Metadata implements Iterable<IndexMetadata>, Diffable<Metadata> {
             clusterUUID = in.readString();
             clusterUUIDCommitted = in.readBoolean();
             version = in.readLong();
-            if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
+            if (hasGlobalColumnOID(in.getVersion())) {
                 columnOID = in.readLong();
             } else {
                 columnOID = COLUMN_OID_UNASSIGNED;
@@ -521,7 +526,7 @@ public class Metadata implements Iterable<IndexMetadata>, Diffable<Metadata> {
             out.writeString(clusterUUID);
             out.writeBoolean(clusterUUIDCommitted);
             out.writeLong(version);
-            if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
+            if (hasGlobalColumnOID(out.getVersion())) {
                 out.writeLong(columnOID);
             }
             coordinationMetadata.writeTo(out);
@@ -556,7 +561,7 @@ public class Metadata implements Iterable<IndexMetadata>, Diffable<Metadata> {
     public static Metadata readFrom(StreamInput in) throws IOException {
         Builder builder = new Builder();
         builder.version = in.readLong();
-        if (in.getVersion().onOrAfter(Version.V_5_5_0) && in.getVersion().onOrBefore(Version.V_6_0_3)) {
+        if (hasGlobalColumnOID(in.getVersion())) {
             builder.columnOID(in.readLong());
         }
         builder.clusterUUID = in.readString();
@@ -597,7 +602,7 @@ public class Metadata implements Iterable<IndexMetadata>, Diffable<Metadata> {
     @Override
     public void writeTo(StreamOutput out) throws IOException {
         out.writeLong(version);
-        if (out.getVersion().onOrAfter(Version.V_5_5_0) && out.getVersion().onOrBefore(Version.V_6_0_3)) {
+        if (hasGlobalColumnOID(out.getVersion())) {
             out.writeLong(columnOID);
         }
         out.writeString(clusterUUID);
diff --git a/server/src/test/java/org/elasticsearch/cluster/metadata/MetadataTest.java b/server/src/test/java/org/elasticsearch/cluster/metadata/MetadataTest.java
new file mode 100644
index 0000000000..c748613110
--- /dev/null
+++ b/server/src/test/java/org/elasticsearch/cluster/metadata/MetadataTest.java
@@ -0,0 +1,50 @@
+/*
+ * Licensed to Crate.io GmbH ("Crate") under one or more contributor
+ * license agreements.  See the NOTICE file distributed with this work for
+ * additional information regarding copyright ownership.  Crate licenses
+ * this file to you under the Apache License, Version 2.0 (the "License");
+ * you may not use this file except in compliance with the License.  You may
+ * obtain a copy of the License at
+ *
+ *     http://www.apache.org/licenses/LICENSE-2.0
+ *
+ * Unless required by applicable law or agreed to in writing, software
+ * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
+ * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
+ * License for the specific language governing permissions and limitations
+ * under the License.
+ *
+ * However, if you have executed another commercial license agreement
+ * with Crate these terms will supersede the license and you may use the
+ * software solely pursuant to the terms of the relevant commercial agreement.
+ */
+
+package org.elasticsearch.cluster.metadata;
+
+import static org.assertj.core.api.Assertions.assertThat;
+
+import org.elasticsearch.Version;
+import org.elasticsearch.common.io.stream.BytesStreamOutput;
+import org.junit.Test;
+
+public class MetadataTest {
+
+    @Test
+    public void test_bwc_read_writes_with_6_1_0() throws Exception {
+        Metadata metadata = Metadata.builder()
+                .columnOID(123L)
+                // builder() adds IndexGraveyard custom, which causes "can't read named writeable from StreamInput" error on reads.
+                // In production NamedWriteableAwareStreamInput is used.
+                // Resetting it here for simplicity as it's irrelevant for the test.
+                .removeCustom(IndexGraveyard.TYPE)
+                .build();
+
+        BytesStreamOutput out = new BytesStreamOutput();
+        out.setVersion(Version.fromString("6.1.0"));
+        metadata.writeTo(out); // OID should be written, 6.1.0 expects it.
+        var in = out.bytes().streamInput();
+        in.setVersion(Version.fromString("6.1.0"));
+        Metadata recievedMetadata = Metadata.readFrom(in); // We are reading from 6.1.0, which sends out OID.
+        assertThat(recievedMetadata.columnOID()).isEqualTo(123L);
+    }
+}

```
