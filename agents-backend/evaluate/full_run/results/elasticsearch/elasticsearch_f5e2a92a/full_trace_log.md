# Full Trace of Agentic File Edits

## Attempt #1

### ReAct Agent Actions
- **server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "    private enum VectorIndexType {",
  "resolved_new_preview": "    public enum VectorIndexType {"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.apache.lucene.search.ScoreMode;",
  "resolved_new_preview": "import org.apache.lucene.search.ScoreDoc;\nimport org.apache.lucene.search.ScoreMode;"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Objects;",
  "resolved_new_preview": "import java.util.Comparator;\nimport java.util.Objects;"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": " * Note: this query was adapted from Lucene's DocAndScoreQuery from the class",
  "resolved_new_preview": " * Note: this query was originally adapted from Lucene's DocAndScoreQuery from the class"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": " * There are no changes to the behavior, just some renames.",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "     * @param docs the global doc IDs of documents that match, in ascending order\n     * @param scores the scores of the matching documents",
  "resolved_new_preview": "     * @param scoreDocs an array of ScoreDocs to use for the query"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "    KnnScoreDocQuery(int[] docs, float[] scores, IndexReader reader) {\n        this.docs = docs;\n        this.scores = scores;",
  "resolved_new_preview": "    KnnScoreDocQuery(ScoreDoc[] scoreDocs, IndexReader reader) {\n        // Ensure that the docs are sorted by docId, as they are later searched using binary search\n        Arrays.sort(scoreDocs, Comp"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "        int numDocs = scoreDocs.length;\n        int[] docs = new int[numDocs];\n        float[] scores = new float[numDocs];\n        for (int i = 0; i < numDocs; i++) {\n            docs[i] = scoreDocs[",
  "resolved_new_preview": "        return new KnnScoreDocQuery(scoreDocs, context.getIndexReader());"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.apache.lucene.search.ScoreDoc;",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Comparator;",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "        ScoreDoc[] scoreDocs = topDocs.scoreDocs;\n        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));\n        int[] docIds = new int[scoreDocs.length];\n        float[] s",
  "resolved_new_preview": "        return new KnnScoreDocQuery(topDocs.scoreDocs, searcher.getIndexReader());"
}
```

### Final Output Diff
**server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java b/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
index ae6140a1caf..4a44ad2f360 100644
--- a/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
+++ b/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
@@ -1228,7 +1228,7 @@ public class DenseVectorFieldMapper extends FieldMapper {
         }
     }
 
-    private enum VectorIndexType {
+    public enum VectorIndexType {
         HNSW("hnsw", false) {
             @Override
             public IndexOptions parseIndexOptions(String fieldName, Map<String, ?> indexOptionsMap) {
```
**server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
index 2855fe8bcf0..37708be09e1 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
@@ -17,12 +17,14 @@ import org.apache.lucene.search.IndexSearcher;
 import org.apache.lucene.search.MatchNoDocsQuery;
 import org.apache.lucene.search.Query;
 import org.apache.lucene.search.QueryVisitor;
+import org.apache.lucene.search.ScoreDoc;
 import org.apache.lucene.search.ScoreMode;
 import org.apache.lucene.search.Scorer;
 import org.apache.lucene.search.Weight;
 
 import java.io.IOException;
 import java.util.Arrays;
+import java.util.Comparator;
 import java.util.Objects;
 
 import static org.apache.lucene.search.DocIdSetIterator.NO_MORE_DOCS;
@@ -30,9 +32,9 @@ import static org.apache.lucene.search.DocIdSetIterator.NO_MORE_DOCS;
 /**
  * A query that matches the provided docs with their scores.
  *
- * Note: this query was adapted from Lucene's DocAndScoreQuery from the class
+ * Note: this query was originally adapted from Lucene's DocAndScoreQuery from the class
  * {@link org.apache.lucene.search.KnnFloatVectorQuery}, which is package-private.
- * There are no changes to the behavior, just some renames.
+
  */
 public class KnnScoreDocQuery extends Query {
     private final int[] docs;
@@ -49,13 +51,18 @@ public class KnnScoreDocQuery extends Query {
     /**
      * Creates a query.
      *
-     * @param docs the global doc IDs of documents that match, in ascending order
-     * @param scores the scores of the matching documents
+     * @param scoreDocs an array of ScoreDocs to use for the query
      * @param reader IndexReader
      */
-    KnnScoreDocQuery(int[] docs, float[] scores, IndexReader reader) {
-        this.docs = docs;
-        this.scores = scores;
+    KnnScoreDocQuery(ScoreDoc[] scoreDocs, IndexReader reader) {
+        // Ensure that the docs are sorted by docId, as they are later searched using binary search
+        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));
+        this.docs = new int[scoreDocs.length];
+        this.scores = new float[scoreDocs.length];
+        for (int i = 0; i < scoreDocs.length; i++) {
+            docs[i] = scoreDocs[i].doc;
+            scores[i] = scoreDocs[i].score;
+        }
         this.segmentStarts = findSegmentStarts(reader, docs);
         this.contextIdentity = reader.getContext().id();
     }
```
**server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
index 6fa83ccfb6a..1a81f4b984e 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
@@ -141,15 +141,7 @@ public class KnnScoreDocQueryBuilder extends AbstractQueryBuilder<KnnScoreDocQue
 
     @Override
     protected Query doToQuery(SearchExecutionContext context) throws IOException {
-        int numDocs = scoreDocs.length;
-        int[] docs = new int[numDocs];
-        float[] scores = new float[numDocs];
-        for (int i = 0; i < numDocs; i++) {
-            docs[i] = scoreDocs[i].doc;
-            scores[i] = scoreDocs[i].score;
-        }
-
-        return new KnnScoreDocQuery(docs, scores, context.getIndexReader());
+        return new KnnScoreDocQuery(scoreDocs, context.getIndexReader());
     }
 
     @Override
```
**server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java b/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
index 967f310f935..c08b531a3b0 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
@@ -16,14 +16,14 @@ import org.apache.lucene.search.DoubleValuesSource;
 import org.apache.lucene.search.IndexSearcher;
 import org.apache.lucene.search.Query;
 import org.apache.lucene.search.QueryVisitor;
-import org.apache.lucene.search.ScoreDoc;
+
 import org.apache.lucene.search.TopDocs;
 import org.elasticsearch.index.mapper.vectors.VectorSimilarityFloatValueSource;
 import org.elasticsearch.search.profile.query.QueryProfiler;
 
 import java.io.IOException;
 import java.util.Arrays;
-import java.util.Comparator;
+
 import java.util.Objects;
 
 /**
@@ -60,16 +60,7 @@ public class RescoreKnnVectorQuery extends Query implements QueryProfilerProvide
         // Retrieve top k documents from the rescored query
         TopDocs topDocs = searcher.search(query, k);
         vectorOperations = topDocs.totalHits.value;
-        ScoreDoc[] scoreDocs = topDocs.scoreDocs;
-        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));
-        int[] docIds = new int[scoreDocs.length];
-        float[] scores = new float[scoreDocs.length];
-        for (int i = 0; i < scoreDocs.length; i++) {
-            docIds[i] = scoreDocs[i].doc;
-            scores[i] = scoreDocs[i].score;
-        }
-
-        return new KnnScoreDocQuery(docIds, scores, searcher.getIndexReader());
+        return new KnnScoreDocQuery(topDocs.scoreDocs, searcher.getIndexReader());
     }
 
     public Query innerQuery() {
```

## Attempt #2

### Final Output Diff

## Attempt #3

### ReAct Agent Actions
- **server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "    private enum VectorIndexType {",
  "resolved_new_preview": "    public enum VectorIndexType {"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.apache.lucene.search.ScoreMode;",
  "resolved_new_preview": "import org.apache.lucene.search.ScoreDoc;\nimport org.apache.lucene.search.ScoreMode;"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "insert_before",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Objects;",
  "resolved_new_preview": "import java.util.Comparator;\nimport java.util.Objects;"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": " * Note: this query was adapted from Lucene's DocAndScoreQuery from the class",
  "resolved_new_preview": " * Note: this query was originally adapted from Lucene's DocAndScoreQuery from the class"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": " * There are no changes to the behavior, just some renames.",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "     * @param docs the global doc IDs of documents that match, in ascending order\n     * @param scores the scores of the matching documents",
  "resolved_new_preview": "     * @param scoreDocs an array of ScoreDocs to use for the query"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "    KnnScoreDocQuery(int[] docs, float[] scores, IndexReader reader) {\n        this.docs = docs;\n        this.scores = scores;",
  "resolved_new_preview": "    KnnScoreDocQuery(ScoreDoc[] scoreDocs, IndexReader reader) {\n        // Ensure that the docs are sorted by docId, as they are later searched using binary search\n        Arrays.sort(scoreDocs, Comp"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "        int numDocs = scoreDocs.length;\n        int[] docs = new int[numDocs];\n        float[] scores = new float[numDocs];\n        for (int i = 0; i < numDocs; i++) {\n            docs[i] = scoreDocs[",
  "resolved_new_preview": "        return new KnnScoreDocQuery(scoreDocs, context.getIndexReader());"
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "import org.apache.lucene.search.ScoreDoc;",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "delete",
  "resolution_reason": "exact",
  "resolved_old_preview": "import java.util.Comparator;",
  "resolved_new_preview": ""
}
```
- **server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java**: Called `str_replace_in_file`
```json
{
  "file_path": "server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java",
  "edit_type": "replace",
  "resolution_reason": "exact",
  "resolved_old_preview": "        ScoreDoc[] scoreDocs = topDocs.scoreDocs;\n        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));\n        int[] docIds = new int[scoreDocs.length];\n        float[] s",
  "resolved_new_preview": "        return new KnnScoreDocQuery(topDocs.scoreDocs, searcher.getIndexReader());"
}
```

### Final Output Diff
**server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java b/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
index ae6140a1caf..4a44ad2f360 100644
--- a/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
+++ b/server/src/main/java/org/elasticsearch/index/mapper/vectors/DenseVectorFieldMapper.java
@@ -1228,7 +1228,7 @@ public class DenseVectorFieldMapper extends FieldMapper {
         }
     }
 
-    private enum VectorIndexType {
+    public enum VectorIndexType {
         HNSW("hnsw", false) {
             @Override
             public IndexOptions parseIndexOptions(String fieldName, Map<String, ?> indexOptionsMap) {
```
**server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
index 2855fe8bcf0..37708be09e1 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQuery.java
@@ -17,12 +17,14 @@ import org.apache.lucene.search.IndexSearcher;
 import org.apache.lucene.search.MatchNoDocsQuery;
 import org.apache.lucene.search.Query;
 import org.apache.lucene.search.QueryVisitor;
+import org.apache.lucene.search.ScoreDoc;
 import org.apache.lucene.search.ScoreMode;
 import org.apache.lucene.search.Scorer;
 import org.apache.lucene.search.Weight;
 
 import java.io.IOException;
 import java.util.Arrays;
+import java.util.Comparator;
 import java.util.Objects;
 
 import static org.apache.lucene.search.DocIdSetIterator.NO_MORE_DOCS;
@@ -30,9 +32,9 @@ import static org.apache.lucene.search.DocIdSetIterator.NO_MORE_DOCS;
 /**
  * A query that matches the provided docs with their scores.
  *
- * Note: this query was adapted from Lucene's DocAndScoreQuery from the class
+ * Note: this query was originally adapted from Lucene's DocAndScoreQuery from the class
  * {@link org.apache.lucene.search.KnnFloatVectorQuery}, which is package-private.
- * There are no changes to the behavior, just some renames.
+
  */
 public class KnnScoreDocQuery extends Query {
     private final int[] docs;
@@ -49,13 +51,18 @@ public class KnnScoreDocQuery extends Query {
     /**
      * Creates a query.
      *
-     * @param docs the global doc IDs of documents that match, in ascending order
-     * @param scores the scores of the matching documents
+     * @param scoreDocs an array of ScoreDocs to use for the query
      * @param reader IndexReader
      */
-    KnnScoreDocQuery(int[] docs, float[] scores, IndexReader reader) {
-        this.docs = docs;
-        this.scores = scores;
+    KnnScoreDocQuery(ScoreDoc[] scoreDocs, IndexReader reader) {
+        // Ensure that the docs are sorted by docId, as they are later searched using binary search
+        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));
+        this.docs = new int[scoreDocs.length];
+        this.scores = new float[scoreDocs.length];
+        for (int i = 0; i < scoreDocs.length; i++) {
+            docs[i] = scoreDocs[i].doc;
+            scores[i] = scoreDocs[i].score;
+        }
         this.segmentStarts = findSegmentStarts(reader, docs);
         this.contextIdentity = reader.getContext().id();
     }
```
**server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
index 6fa83ccfb6a..1a81f4b984e 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/KnnScoreDocQueryBuilder.java
@@ -141,15 +141,7 @@ public class KnnScoreDocQueryBuilder extends AbstractQueryBuilder<KnnScoreDocQue
 
     @Override
     protected Query doToQuery(SearchExecutionContext context) throws IOException {
-        int numDocs = scoreDocs.length;
-        int[] docs = new int[numDocs];
-        float[] scores = new float[numDocs];
-        for (int i = 0; i < numDocs; i++) {
-            docs[i] = scoreDocs[i].doc;
-            scores[i] = scoreDocs[i].score;
-        }
-
-        return new KnnScoreDocQuery(docs, scores, context.getIndexReader());
+        return new KnnScoreDocQuery(scoreDocs, context.getIndexReader());
     }
 
     @Override
```
**server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java** [replace]
```java
// --- OLD ---
<deterministic file-editor diff>
// --- NEW ---
diff --git a/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java b/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
index 967f310f935..c08b531a3b0 100644
--- a/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
+++ b/server/src/main/java/org/elasticsearch/search/vectors/RescoreKnnVectorQuery.java
@@ -16,14 +16,14 @@ import org.apache.lucene.search.DoubleValuesSource;
 import org.apache.lucene.search.IndexSearcher;
 import org.apache.lucene.search.Query;
 import org.apache.lucene.search.QueryVisitor;
-import org.apache.lucene.search.ScoreDoc;
+
 import org.apache.lucene.search.TopDocs;
 import org.elasticsearch.index.mapper.vectors.VectorSimilarityFloatValueSource;
 import org.elasticsearch.search.profile.query.QueryProfiler;
 
 import java.io.IOException;
 import java.util.Arrays;
-import java.util.Comparator;
+
 import java.util.Objects;
 
 /**
@@ -60,16 +60,7 @@ public class RescoreKnnVectorQuery extends Query implements QueryProfilerProvide
         // Retrieve top k documents from the rescored query
         TopDocs topDocs = searcher.search(query, k);
         vectorOperations = topDocs.totalHits.value;
-        ScoreDoc[] scoreDocs = topDocs.scoreDocs;
-        Arrays.sort(scoreDocs, Comparator.comparingInt(scoreDoc -> scoreDoc.doc));
-        int[] docIds = new int[scoreDocs.length];
-        float[] scores = new float[scoreDocs.length];
-        for (int i = 0; i < scoreDocs.length; i++) {
-            docIds[i] = scoreDocs[i].doc;
-            scores[i] = scoreDocs[i].score;
-        }
-
-        return new KnnScoreDocQuery(docIds, scores, searcher.getIndexReader());
+        return new KnnScoreDocQuery(topDocs.scoreDocs, searcher.getIndexReader());
     }
 
     public Query innerQuery() {
```