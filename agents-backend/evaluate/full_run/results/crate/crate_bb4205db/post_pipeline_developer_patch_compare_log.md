# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: True

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java']
- Developer Java files: ['extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java']
- Overlap Java files: ['extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java']

## File State Comparison
- Compared files: ['extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java', 'server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java']
- Mismatched files: []
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java

- Developer hunks: 7
- Generated hunks: 7

#### Hunk 1

Developer
```diff
@@ -186,9 +186,12 @@
             Literal<?> value = optionalParams.getLast();
             precision = value == null ? HyperLogLogPlusPlus.DEFAULT_PRECISION : (int) value.value();
         }
-        Reference reference = aggregationReferences.get(0);
-        var dataType = reference.valueType();
-        switch (dataType.id()) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
+            return null;
+        }
+        DataType<?> valueType = reference.valueType();
+        switch (valueType.id()) {
             case ByteType.ID:
             case ShortType.ID:
             case IntegerType.ID:

```

Generated
```diff
@@ -186,9 +186,12 @@
             Literal<?> value = optionalParams.getLast();
             precision = value == null ? HyperLogLogPlusPlus.DEFAULT_PRECISION : (int) value.value();
         }
-        Reference reference = aggregationReferences.get(0);
-        var dataType = reference.valueType();
-        switch (dataType.id()) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
+            return null;
+        }
+        DataType<?> valueType = reference.valueType();
+        switch (valueType.id()) {
             case ByteType.ID:
             case ShortType.ID:
             case IntegerType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -197,8 +200,8 @@
             case TimestampType.ID_WITHOUT_TZ:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Generated
```diff
@@ -197,8 +200,8 @@
             case TimestampType.ID_WITHOUT_TZ:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 3

Developer
```diff
@@ -209,8 +212,8 @@
             case DoubleType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Generated
```diff
@@ -209,8 +212,8 @@
             case DoubleType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 4

Developer
```diff
@@ -227,8 +230,8 @@
             case FloatType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Generated
```diff
@@ -227,8 +230,8 @@
             case FloatType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 5

Developer
```diff
@@ -243,7 +246,7 @@
                 );
             case StringType.ID:
             case CharacterType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {

```

Generated
```diff
@@ -243,7 +246,7 @@
                 );
             case StringType.ID:
             case CharacterType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 6

Developer
```diff
@@ -257,7 +260,7 @@
                     }
                 };
             case IpType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {

```

Generated
```diff
@@ -257,7 +260,7 @@
                     }
                 };
             case IpType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 7

Developer
```diff
@@ -301,9 +304,6 @@
             values = DocValues.getSortedSet(reader.reader(), columnName);
         }
 
-        @Override
-        public abstract void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException;
-
         @Override
         public Object partialResult(RamAccounting ramAccounting, HllState state) {
             return state;

```

Generated
```diff
@@ -301,9 +304,6 @@
             values = DocValues.getSortedSet(reader.reader(), columnName);
         }
 
-        @Override
-        public abstract void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException;
-
         @Override
         public Object partialResult(RamAccounting ramAccounting, HllState state) {
             return state;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java

- Developer hunks: 2
- Generated hunks: 2

#### Hunk 1

Developer
```diff
@@ -34,6 +34,7 @@
 import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionImplementation;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.types.DataType;
 

```

Generated
```diff
@@ -34,6 +34,7 @@
 import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionImplementation;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.types.DataType;
 

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -136,4 +137,18 @@
                                                        List<Literal<?>> optionalParams) {
         return null;
     }
+
+    protected Reference getAggReference(List<Reference> aggregationReferences) {
+        if (aggregationReferences.isEmpty()) {
+            return null;
+        }
+        Reference reference = aggregationReferences.getFirst();
+        if (reference == null) {
+            return null;
+        }
+        if (!reference.hasDocValues() || reference.granularity() != RowGranularity.DOC) {
+            return null;
+        }
+        return reference;
+    }
 }

```

Generated
```diff
@@ -136,4 +137,18 @@
                                                        List<Literal<?>> optionalParams) {
         return null;
     }
+
+    protected Reference getAggReference(List<Reference> aggregationReferences) {
+        if (aggregationReferences.isEmpty()) {
+            return null;
+        }
+        Reference reference = aggregationReferences.getFirst();
+        if (reference == null) {
+            return null;
+        }
+        if (!reference.hasDocValues() || reference.granularity() != RowGranularity.DOC) {
+            return null;
+        }
+        return reference;
+    }
 }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java

- Developer hunks: 2
- Generated hunks: 2

#### Hunk 1

Developer
```diff
@@ -161,14 +161,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference arg = aggregationReferences.get(0);
-        if (arg == null) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
             return null;
         }
-        if (!arg.hasDocValues()) {
-            return null;
-        }
-        var dataType = arg.valueType();
+        var dataType = reference.valueType();
         switch (dataType.id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Generated
```diff
@@ -161,14 +161,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference arg = aggregationReferences.get(0);
-        if (arg == null) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
             return null;
         }
-        if (!arg.hasDocValues()) {
-            return null;
-        }
-        var dataType = arg.valueType();
+        var dataType = reference.valueType();
         switch (dataType.id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -177,18 +174,18 @@
             case TimestampType.ID_WITH_TZ:
             case TimestampType.ID_WITHOUT_TZ:
                 return new LongArbitraryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             case FloatType.ID:
-                return new FloatArbitraryDocValueAggregator(arg.storageIdent());
+                return new FloatArbitraryDocValueAggregator(reference.storageIdent());
             case DoubleType.ID:
-                return new DoubleArbitraryDocValueAggregator(arg.storageIdent());
+                return new DoubleArbitraryDocValueAggregator(reference.storageIdent());
             case IpType.ID:
-                return new ArbitraryIPDocValueAggregator(arg.storageIdent());
+                return new ArbitraryIPDocValueAggregator(reference.storageIdent());
             case StringType.ID:
                 return new ArbitraryBinaryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             default:

```

Generated
```diff
@@ -177,18 +174,18 @@
             case TimestampType.ID_WITH_TZ:
             case TimestampType.ID_WITHOUT_TZ:
                 return new LongArbitraryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             case FloatType.ID:
-                return new FloatArbitraryDocValueAggregator(arg.storageIdent());
+                return new FloatArbitraryDocValueAggregator(reference.storageIdent());
             case DoubleType.ID:
-                return new DoubleArbitraryDocValueAggregator(arg.storageIdent());
+                return new DoubleArbitraryDocValueAggregator(reference.storageIdent());
             case IpType.ID:
-                return new ArbitraryIPDocValueAggregator(arg.storageIdent());
+                return new ArbitraryIPDocValueAggregator(reference.storageIdent());
             case StringType.ID:
                 return new ArbitraryBinaryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             default:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java

- Developer hunks: 2
- Generated hunks: 2

#### Hunk 1

Developer
```diff
@@ -48,6 +48,7 @@
 import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.metadata.functions.BoundSignature;

```

Generated
```diff
@@ -48,6 +48,7 @@
 import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.metadata.functions.BoundSignature;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -165,7 +166,7 @@
         if (searchField == null) {
             return null;
         }
-        if (!searchField.hasDocValues()) {
+        if (!searchField.hasDocValues() || searchField.granularity() != RowGranularity.DOC) {
             return null;
         }
 

```

Generated
```diff
@@ -165,7 +166,7 @@
         if (searchField == null) {
             return null;
         }
-        if (!searchField.hasDocValues()) {
+        if (!searchField.hasDocValues() || searchField.granularity() != RowGranularity.DOC) {
             return null;
         }
 

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java

- Developer hunks: 4
- Generated hunks: 4

#### Hunk 1

Developer
```diff
@@ -48,6 +48,7 @@
 import io.crate.metadata.Functions;
 import io.crate.metadata.NodeContext;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.TransactionContext;
 import io.crate.metadata.doc.DocTableInfo;

```

Generated
```diff
@@ -48,6 +48,7 @@
 import io.crate.metadata.Functions;
 import io.crate.metadata.NodeContext;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.TransactionContext;
 import io.crate.metadata.doc.DocTableInfo;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -257,7 +258,7 @@
     }
 
     private DocValueAggregator<?> getDocValueAggregator(Reference ref) {
-        if (!ref.hasDocValues()) {
+        if (!ref.hasDocValues() || ref.granularity() != RowGranularity.DOC) {
             return null;
         }
         switch (ref.valueType().id()) {

```

Generated
```diff
@@ -257,7 +258,7 @@
     }
 
     private DocValueAggregator<?> getDocValueAggregator(Reference ref) {
-        if (!ref.hasDocValues()) {
+        if (!ref.hasDocValues() || ref.granularity() != RowGranularity.DOC) {
             return null;
         }
         switch (ref.valueType().id()) {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 3

Developer
```diff
@@ -304,17 +305,16 @@
         if (aggregationReferences.size() != 1) {
             return null;
         }
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = aggregationReferences.getFirst();
         if (reference == null) {
             return null;
         }
         if (reference.valueType().id() == ObjectType.ID) {
             // Count on object would require loading the source just to check if there is a value.
             // Try to count on a non-null sub-column to be able to utilize doc-values.
-            var aggregationRef = (Reference) aggregationReferences.get(0);
             for (var notNullCol : table.notNullColumns()) {
                 // the first seen not-null sub-column will be used
-                if (notNullCol.isChildOf(aggregationRef.column())) {
+                if (notNullCol.isChildOf(reference.column())) {
                     var notNullColRef = table.getReference(notNullCol);
                     if (notNullColRef == null) {
                         continue;

```

Generated
```diff
@@ -304,17 +305,16 @@
         if (aggregationReferences.size() != 1) {
             return null;
         }
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = aggregationReferences.getFirst();
         if (reference == null) {
             return null;
         }
         if (reference.valueType().id() == ObjectType.ID) {
             // Count on object would require loading the source just to check if there is a value.
             // Try to count on a non-null sub-column to be able to utilize doc-values.
-            var aggregationRef = (Reference) aggregationReferences.get(0);
             for (var notNullCol : table.notNullColumns()) {
                 // the first seen not-null sub-column will be used
-                if (notNullCol.isChildOf(aggregationRef.column())) {
+                if (notNullCol.isChildOf(reference.column())) {
                     var notNullColRef = table.getReference(notNullCol);
                     if (notNullColRef == null) {
                         continue;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 4

Developer
```diff
@@ -326,9 +326,6 @@
                 }
             }
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return getDocValueAggregator(reference);
     }
 }

```

Generated
```diff
@@ -326,9 +326,6 @@
                 }
             }
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return getDocValueAggregator(reference);
     }
 }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -308,7 +308,7 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }

```

Generated
```diff
@@ -308,7 +308,7 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -222,24 +222,19 @@
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
-
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMax(reference.storageIdent(), arg);
+                    return new LongMax(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMax(reference.storageIdent());

```

Generated
```diff
@@ -222,24 +222,19 @@
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
-
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMax(reference.storageIdent(), arg);
+                    return new LongMax(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMax(reference.storageIdent());

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -256,22 +256,19 @@
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMin(reference.storageIdent(), arg);
+                    return new LongMin(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMin(reference.storageIdent());

```

Generated
```diff
@@ -256,22 +256,19 @@
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMin(reference.storageIdent(), arg);
+                    return new LongMin(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMin(reference.storageIdent());

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -183,13 +183,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return switch (reference.valueType().id()) {
             case ByteType.ID, ShortType.ID, IntegerType.ID, LongType.ID ->
                 new SumLong(returnType, reference.storageIdent());

```

Generated
```diff
@@ -183,13 +183,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return switch (reference.valueType().id()) {
             case ByteType.ID, ShortType.ID, IntegerType.ID, LongType.ID ->
                 new SumLong(returnType, reference.storageIdent());

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -231,13 +231,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Generated
```diff
@@ -231,13 +231,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -196,16 +196,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
-
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Generated
```diff
@@ -196,16 +196,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
-
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -222,19 +222,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        if (aggregationReferences.isEmpty()) {
-            return null;
-        }
-
-        Reference reference = aggregationReferences.getFirst();
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         if (optionalParams.isEmpty()) {
             return getDocValueAggregator(reference, DEFAULT_LIMIT, DEFAULT_MAX_CAPACITY);
         }

```

Generated
```diff
@@ -222,19 +222,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        if (aggregationReferences.isEmpty()) {
-            return null;
-        }
-
-        Reference reference = aggregationReferences.getFirst();
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         if (optionalParams.isEmpty()) {
             return getDocValueAggregator(reference, DEFAULT_LIMIT, DEFAULT_MAX_CAPACITY);
         }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -230,13 +230,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
+
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Generated
```diff
@@ -230,13 +230,11 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
+
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java

- Developer hunks: 1
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -312,13 +312,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Generated
```diff
@@ -312,13 +312,10 @@
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```



## Full Generated Patch (Agent-Only, code-only)
```diff
diff --git a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
index 6a27301930..e2fe7d18ba 100644
--- a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
+++ b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
@@ -186,9 +186,12 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             Literal<?> value = optionalParams.getLast();
             precision = value == null ? HyperLogLogPlusPlus.DEFAULT_PRECISION : (int) value.value();
         }
-        Reference reference = aggregationReferences.get(0);
-        var dataType = reference.valueType();
-        switch (dataType.id()) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
+            return null;
+        }
+        DataType<?> valueType = reference.valueType();
+        switch (valueType.id()) {
             case ByteType.ID:
             case ShortType.ID:
             case IntegerType.ID:
@@ -197,8 +200,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case TimestampType.ID_WITHOUT_TZ:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -209,8 +212,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case DoubleType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -227,8 +230,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case FloatType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -243,7 +246,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                 );
             case StringType.ID:
             case CharacterType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -257,7 +260,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                     }
                 };
             case IpType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -301,9 +304,6 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             values = DocValues.getSortedSet(reader.reader(), columnName);
         }
 
-        @Override
-        public abstract void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException;
-
         @Override
         public Object partialResult(RamAccounting ramAccounting, HllState state) {
             return state;
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
index 47249d1a75..0edc7cf864 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
@@ -34,6 +34,7 @@ import io.crate.expression.symbol.Literal;
 import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionImplementation;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.types.DataType;
 
@@ -136,4 +137,18 @@ public abstract class AggregationFunction<TPartial, TFinal> implements FunctionI
                                                        List<Literal<?>> optionalParams) {
         return null;
     }
+
+    protected Reference getAggReference(List<Reference> aggregationReferences) {
+        if (aggregationReferences.isEmpty()) {
+            return null;
+        }
+        Reference reference = aggregationReferences.getFirst();
+        if (reference == null) {
+            return null;
+        }
+        if (!reference.hasDocValues() || reference.granularity() != RowGranularity.DOC) {
+            return null;
+        }
+        return reference;
+    }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
index 70f165c7de..7f37728760 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
@@ -161,14 +161,11 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference arg = aggregationReferences.get(0);
-        if (arg == null) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
             return null;
         }
-        if (!arg.hasDocValues()) {
-            return null;
-        }
-        var dataType = arg.valueType();
+        var dataType = reference.valueType();
         switch (dataType.id()) {
             case ByteType.ID:
             case ShortType.ID:
@@ -177,18 +174,18 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
             case TimestampType.ID_WITH_TZ:
             case TimestampType.ID_WITHOUT_TZ:
                 return new LongArbitraryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             case FloatType.ID:
-                return new FloatArbitraryDocValueAggregator(arg.storageIdent());
+                return new FloatArbitraryDocValueAggregator(reference.storageIdent());
             case DoubleType.ID:
-                return new DoubleArbitraryDocValueAggregator(arg.storageIdent());
+                return new DoubleArbitraryDocValueAggregator(reference.storageIdent());
             case IpType.ID:
-                return new ArbitraryIPDocValueAggregator(arg.storageIdent());
+                return new ArbitraryIPDocValueAggregator(reference.storageIdent());
             case StringType.ID:
                 return new ArbitraryBinaryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             default:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
index 1c9f1ca0f9..a72fa17b43 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
@@ -48,6 +48,7 @@ import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.metadata.functions.BoundSignature;
@@ -165,7 +166,7 @@ public final class CmpByAggregation extends AggregationFunction<CmpByAggregation
         if (searchField == null) {
             return null;
         }
-        if (!searchField.hasDocValues()) {
+        if (!searchField.hasDocValues() || searchField.granularity() != RowGranularity.DOC) {
             return null;
         }
 
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
index 0aceb0857a..a4e268d1bb 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
@@ -48,6 +48,7 @@ import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.NodeContext;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.TransactionContext;
 import io.crate.metadata.doc.DocTableInfo;
@@ -257,7 +258,7 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
     }
 
     private DocValueAggregator<?> getDocValueAggregator(Reference ref) {
-        if (!ref.hasDocValues()) {
+        if (!ref.hasDocValues() || ref.granularity() != RowGranularity.DOC) {
             return null;
         }
         switch (ref.valueType().id()) {
@@ -304,17 +305,16 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
         if (aggregationReferences.size() != 1) {
             return null;
         }
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = aggregationReferences.getFirst();
         if (reference == null) {
             return null;
         }
         if (reference.valueType().id() == ObjectType.ID) {
             // Count on object would require loading the source just to check if there is a value.
             // Try to count on a non-null sub-column to be able to utilize doc-values.
-            var aggregationRef = (Reference) aggregationReferences.get(0);
             for (var notNullCol : table.notNullColumns()) {
                 // the first seen not-null sub-column will be used
-                if (notNullCol.isChildOf(aggregationRef.column())) {
+                if (notNullCol.isChildOf(reference.column())) {
                     var notNullColRef = table.getReference(notNullCol);
                     if (notNullColRef == null) {
                         continue;
@@ -326,9 +326,6 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
                 }
             }
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return getDocValueAggregator(reference);
     }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
index d5f0458081..ef013bd391 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
@@ -308,7 +308,7 @@ public class GeometricMeanAggregation extends AggregationFunction<GeometricMeanA
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
index fc8721670a..4527427109 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
@@ -222,24 +222,19 @@ public abstract class MaximumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
-
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMax(reference.storageIdent(), arg);
+                    return new LongMax(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMax(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
index 65f1a4c44e..06a08968a5 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
@@ -256,22 +256,19 @@ public abstract class MinimumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMin(reference.storageIdent(), arg);
+                    return new LongMin(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMin(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
index 792f9d0ce6..12a05e277b 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
@@ -183,13 +183,10 @@ public class NumericSumAggregation extends AggregationFunction<BigDecimal, BigDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return switch (reference.valueType().id()) {
             case ByteType.ID, ShortType.ID, IntegerType.ID, LongType.ID ->
                 new SumLong(returnType, reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
index 526d8d0fe6..813cf993ae 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
@@ -231,13 +231,10 @@ public class StandardDeviationAggregation extends AggregationFunction<StandardDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
index 295126949b..76d032768d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
@@ -196,16 +196,11 @@ public class SumAggregation<T extends Number> extends AggregationFunction<T, T>
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
-
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
index 4e10644e1c..77da28207d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
@@ -222,19 +222,11 @@ public class TopKAggregation extends AggregationFunction<TopKAggregation.State,
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        if (aggregationReferences.isEmpty()) {
-            return null;
-        }
-
-        Reference reference = aggregationReferences.getFirst();
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         if (optionalParams.isEmpty()) {
             return getDocValueAggregator(reference, DEFAULT_LIMIT, DEFAULT_MAX_CAPACITY);
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
index d9d492afbc..67428d32c0 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
@@ -230,13 +230,11 @@ public class VarianceAggregation extends AggregationFunction<Variance, Double> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
+
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
index a374fd69c9..00175dccc2 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
@@ -312,13 +312,10 @@ public class AverageAggregation extends AggregationFunction<AverageAggregation.A
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```

## Full Generated Patch (Final Effective, code-only)
```diff
diff --git a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
index 6a27301930..e2fe7d18ba 100644
--- a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
+++ b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
@@ -186,9 +186,12 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             Literal<?> value = optionalParams.getLast();
             precision = value == null ? HyperLogLogPlusPlus.DEFAULT_PRECISION : (int) value.value();
         }
-        Reference reference = aggregationReferences.get(0);
-        var dataType = reference.valueType();
-        switch (dataType.id()) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
+            return null;
+        }
+        DataType<?> valueType = reference.valueType();
+        switch (valueType.id()) {
             case ByteType.ID:
             case ShortType.ID:
             case IntegerType.ID:
@@ -197,8 +200,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case TimestampType.ID_WITHOUT_TZ:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -209,8 +212,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case DoubleType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -227,8 +230,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case FloatType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -243,7 +246,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                 );
             case StringType.ID:
             case CharacterType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -257,7 +260,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                     }
                 };
             case IpType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -301,9 +304,6 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             values = DocValues.getSortedSet(reader.reader(), columnName);
         }
 
-        @Override
-        public abstract void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException;
-
         @Override
         public Object partialResult(RamAccounting ramAccounting, HllState state) {
             return state;
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
index 47249d1a75..0edc7cf864 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
@@ -34,6 +34,7 @@ import io.crate.expression.symbol.Literal;
 import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionImplementation;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.types.DataType;
 
@@ -136,4 +137,18 @@ public abstract class AggregationFunction<TPartial, TFinal> implements FunctionI
                                                        List<Literal<?>> optionalParams) {
         return null;
     }
+
+    protected Reference getAggReference(List<Reference> aggregationReferences) {
+        if (aggregationReferences.isEmpty()) {
+            return null;
+        }
+        Reference reference = aggregationReferences.getFirst();
+        if (reference == null) {
+            return null;
+        }
+        if (!reference.hasDocValues() || reference.granularity() != RowGranularity.DOC) {
+            return null;
+        }
+        return reference;
+    }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
index 70f165c7de..7f37728760 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
@@ -161,14 +161,11 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference arg = aggregationReferences.get(0);
-        if (arg == null) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
             return null;
         }
-        if (!arg.hasDocValues()) {
-            return null;
-        }
-        var dataType = arg.valueType();
+        var dataType = reference.valueType();
         switch (dataType.id()) {
             case ByteType.ID:
             case ShortType.ID:
@@ -177,18 +174,18 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
             case TimestampType.ID_WITH_TZ:
             case TimestampType.ID_WITHOUT_TZ:
                 return new LongArbitraryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             case FloatType.ID:
-                return new FloatArbitraryDocValueAggregator(arg.storageIdent());
+                return new FloatArbitraryDocValueAggregator(reference.storageIdent());
             case DoubleType.ID:
-                return new DoubleArbitraryDocValueAggregator(arg.storageIdent());
+                return new DoubleArbitraryDocValueAggregator(reference.storageIdent());
             case IpType.ID:
-                return new ArbitraryIPDocValueAggregator(arg.storageIdent());
+                return new ArbitraryIPDocValueAggregator(reference.storageIdent());
             case StringType.ID:
                 return new ArbitraryBinaryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             default:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
index 1c9f1ca0f9..a72fa17b43 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
@@ -48,6 +48,7 @@ import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.metadata.functions.BoundSignature;
@@ -165,7 +166,7 @@ public final class CmpByAggregation extends AggregationFunction<CmpByAggregation
         if (searchField == null) {
             return null;
         }
-        if (!searchField.hasDocValues()) {
+        if (!searchField.hasDocValues() || searchField.granularity() != RowGranularity.DOC) {
             return null;
         }
 
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
index 0aceb0857a..a4e268d1bb 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
@@ -48,6 +48,7 @@ import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.NodeContext;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.TransactionContext;
 import io.crate.metadata.doc.DocTableInfo;
@@ -257,7 +258,7 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
     }
 
     private DocValueAggregator<?> getDocValueAggregator(Reference ref) {
-        if (!ref.hasDocValues()) {
+        if (!ref.hasDocValues() || ref.granularity() != RowGranularity.DOC) {
             return null;
         }
         switch (ref.valueType().id()) {
@@ -304,17 +305,16 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
         if (aggregationReferences.size() != 1) {
             return null;
         }
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = aggregationReferences.getFirst();
         if (reference == null) {
             return null;
         }
         if (reference.valueType().id() == ObjectType.ID) {
             // Count on object would require loading the source just to check if there is a value.
             // Try to count on a non-null sub-column to be able to utilize doc-values.
-            var aggregationRef = (Reference) aggregationReferences.get(0);
             for (var notNullCol : table.notNullColumns()) {
                 // the first seen not-null sub-column will be used
-                if (notNullCol.isChildOf(aggregationRef.column())) {
+                if (notNullCol.isChildOf(reference.column())) {
                     var notNullColRef = table.getReference(notNullCol);
                     if (notNullColRef == null) {
                         continue;
@@ -326,9 +326,6 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
                 }
             }
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return getDocValueAggregator(reference);
     }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
index d5f0458081..ef013bd391 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
@@ -308,7 +308,7 @@ public class GeometricMeanAggregation extends AggregationFunction<GeometricMeanA
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
index fc8721670a..4527427109 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
@@ -222,24 +222,19 @@ public abstract class MaximumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
-
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMax(reference.storageIdent(), arg);
+                    return new LongMax(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMax(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
index 65f1a4c44e..06a08968a5 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
@@ -256,22 +256,19 @@ public abstract class MinimumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMin(reference.storageIdent(), arg);
+                    return new LongMin(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMin(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
index 792f9d0ce6..12a05e277b 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
@@ -183,13 +183,10 @@ public class NumericSumAggregation extends AggregationFunction<BigDecimal, BigDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return switch (reference.valueType().id()) {
             case ByteType.ID, ShortType.ID, IntegerType.ID, LongType.ID ->
                 new SumLong(returnType, reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
index 526d8d0fe6..813cf993ae 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
@@ -231,13 +231,10 @@ public class StandardDeviationAggregation extends AggregationFunction<StandardDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
index 295126949b..76d032768d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
@@ -196,16 +196,11 @@ public class SumAggregation<T extends Number> extends AggregationFunction<T, T>
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
-
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
index 4e10644e1c..77da28207d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
@@ -222,19 +222,11 @@ public class TopKAggregation extends AggregationFunction<TopKAggregation.State,
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        if (aggregationReferences.isEmpty()) {
-            return null;
-        }
-
-        Reference reference = aggregationReferences.getFirst();
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         if (optionalParams.isEmpty()) {
             return getDocValueAggregator(reference, DEFAULT_LIMIT, DEFAULT_MAX_CAPACITY);
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
index d9d492afbc..67428d32c0 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
@@ -230,13 +230,11 @@ public class VarianceAggregation extends AggregationFunction<Variance, Double> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
+
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
index a374fd69c9..00175dccc2 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
@@ -312,13 +312,10 @@ public class AverageAggregation extends AggregationFunction<AverageAggregation.A
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/docs/appendices/release-notes/5.10.9.rst b/docs/appendices/release-notes/5.10.9.rst
index b153f76c99..045927be63 100644
--- a/docs/appendices/release-notes/5.10.9.rst
+++ b/docs/appendices/release-notes/5.10.9.rst
@@ -62,3 +62,7 @@ Fixes
 - Fixed a regression introduced with :ref:`version_5.10.8` that caused a query
   to keep running even if a ``CircuitBreakerException`` was thrown while
   constructing the result set.
+
+- Fixed an issue that would cause :ref:`aggregation functions <aggregation>` on
+  columns used in the ``PARTITION BY()`` clause of a
+  :ref:`partitioned table <partitioned-tables>` to always return ``NULL``.
diff --git a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
index 6a27301930..e2fe7d18ba 100644
--- a/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
+++ b/extensions/functions/src/main/java/io/crate/operation/aggregation/HyperLogLogDistinctAggregation.java
@@ -186,9 +186,12 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             Literal<?> value = optionalParams.getLast();
             precision = value == null ? HyperLogLogPlusPlus.DEFAULT_PRECISION : (int) value.value();
         }
-        Reference reference = aggregationReferences.get(0);
-        var dataType = reference.valueType();
-        switch (dataType.id()) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
+            return null;
+        }
+        DataType<?> valueType = reference.valueType();
+        switch (valueType.id()) {
             case ByteType.ID:
             case ShortType.ID:
             case IntegerType.ID:
@@ -197,8 +200,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case TimestampType.ID_WITHOUT_TZ:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -209,8 +212,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case DoubleType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -227,8 +230,8 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             case FloatType.ID:
                 return new SortedNumericDocValueAggregator<>(
                     reference.storageIdent(),
-                    (ramAccounting, memoryManager, minNodeVersion) -> {
-                        var state = new HllState(dataType, minNodeVersion.onOrAfter(Version.V_4_1_0));
+                    (_, memoryManager, minNodeVersion) -> {
+                        var state = new HllState(valueType, minNodeVersion.onOrAfter(Version.V_4_1_0));
                         return initIfNeeded(state, memoryManager, precision);
                     },
                     (values, state) -> {
@@ -243,7 +246,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                 );
             case StringType.ID:
             case CharacterType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -257,7 +260,7 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
                     }
                 };
             case IpType.ID:
-                return new HllAggregator(reference.storageIdent(), dataType, precision) {
+                return new HllAggregator(reference.storageIdent(), valueType, precision) {
                     @Override
                     public void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException {
                         if (super.values.advanceExact(doc) && super.values.docValueCount() == 1) {
@@ -301,9 +304,6 @@ public class HyperLogLogDistinctAggregation extends AggregationFunction<HyperLog
             values = DocValues.getSortedSet(reader.reader(), columnName);
         }
 
-        @Override
-        public abstract void apply(RamAccounting ramAccounting, int doc, HllState state) throws IOException;
-
         @Override
         public Object partialResult(RamAccounting ramAccounting, HllState state) {
             return state;
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
index 47249d1a75..0edc7cf864 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/AggregationFunction.java
@@ -34,6 +34,7 @@ import io.crate.expression.symbol.Literal;
 import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionImplementation;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.types.DataType;
 
@@ -136,4 +137,18 @@ public abstract class AggregationFunction<TPartial, TFinal> implements FunctionI
                                                        List<Literal<?>> optionalParams) {
         return null;
     }
+
+    protected Reference getAggReference(List<Reference> aggregationReferences) {
+        if (aggregationReferences.isEmpty()) {
+            return null;
+        }
+        Reference reference = aggregationReferences.getFirst();
+        if (reference == null) {
+            return null;
+        }
+        if (!reference.hasDocValues() || reference.granularity() != RowGranularity.DOC) {
+            return null;
+        }
+        return reference;
+    }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
index 70f165c7de..7f37728760 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/ArbitraryAggregation.java
@@ -161,14 +161,11 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference arg = aggregationReferences.get(0);
-        if (arg == null) {
+        Reference reference = getAggReference(aggregationReferences);
+        if (reference == null) {
             return null;
         }
-        if (!arg.hasDocValues()) {
-            return null;
-        }
-        var dataType = arg.valueType();
+        var dataType = reference.valueType();
         switch (dataType.id()) {
             case ByteType.ID:
             case ShortType.ID:
@@ -177,18 +174,18 @@ public class ArbitraryAggregation extends AggregationFunction<Object, Object> {
             case TimestampType.ID_WITH_TZ:
             case TimestampType.ID_WITHOUT_TZ:
                 return new LongArbitraryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             case FloatType.ID:
-                return new FloatArbitraryDocValueAggregator(arg.storageIdent());
+                return new FloatArbitraryDocValueAggregator(reference.storageIdent());
             case DoubleType.ID:
-                return new DoubleArbitraryDocValueAggregator(arg.storageIdent());
+                return new DoubleArbitraryDocValueAggregator(reference.storageIdent());
             case IpType.ID:
-                return new ArbitraryIPDocValueAggregator(arg.storageIdent());
+                return new ArbitraryIPDocValueAggregator(reference.storageIdent());
             case StringType.ID:
                 return new ArbitraryBinaryDocValueAggregator<>(
-                    arg.storageIdent(),
+                    reference.storageIdent(),
                     dataType
                 );
             default:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
index 1c9f1ca0f9..a72fa17b43 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CmpByAggregation.java
@@ -48,6 +48,7 @@ import io.crate.memory.MemoryManager;
 import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.doc.DocTableInfo;
 import io.crate.metadata.functions.BoundSignature;
@@ -165,7 +166,7 @@ public final class CmpByAggregation extends AggregationFunction<CmpByAggregation
         if (searchField == null) {
             return null;
         }
-        if (!searchField.hasDocValues()) {
+        if (!searchField.hasDocValues() || searchField.granularity() != RowGranularity.DOC) {
             return null;
         }
 
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
index 0aceb0857a..a4e268d1bb 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/CountAggregation.java
@@ -48,6 +48,7 @@ import io.crate.metadata.FunctionType;
 import io.crate.metadata.Functions;
 import io.crate.metadata.NodeContext;
 import io.crate.metadata.Reference;
+import io.crate.metadata.RowGranularity;
 import io.crate.metadata.Scalar;
 import io.crate.metadata.TransactionContext;
 import io.crate.metadata.doc.DocTableInfo;
@@ -257,7 +258,7 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
     }
 
     private DocValueAggregator<?> getDocValueAggregator(Reference ref) {
-        if (!ref.hasDocValues()) {
+        if (!ref.hasDocValues() || ref.granularity() != RowGranularity.DOC) {
             return null;
         }
         switch (ref.valueType().id()) {
@@ -304,17 +305,16 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
         if (aggregationReferences.size() != 1) {
             return null;
         }
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = aggregationReferences.getFirst();
         if (reference == null) {
             return null;
         }
         if (reference.valueType().id() == ObjectType.ID) {
             // Count on object would require loading the source just to check if there is a value.
             // Try to count on a non-null sub-column to be able to utilize doc-values.
-            var aggregationRef = (Reference) aggregationReferences.get(0);
             for (var notNullCol : table.notNullColumns()) {
                 // the first seen not-null sub-column will be used
-                if (notNullCol.isChildOf(aggregationRef.column())) {
+                if (notNullCol.isChildOf(reference.column())) {
                     var notNullColRef = table.getReference(notNullCol);
                     if (notNullColRef == null) {
                         continue;
@@ -326,9 +326,6 @@ public class CountAggregation extends AggregationFunction<MutableLong, Long> {
                 }
             }
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return getDocValueAggregator(reference);
     }
 }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
index d5f0458081..ef013bd391 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/GeometricMeanAggregation.java
@@ -308,7 +308,7 @@ public class GeometricMeanAggregation extends AggregationFunction<GeometricMeanA
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
index fc8721670a..4527427109 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MaximumAggregation.java
@@ -222,24 +222,19 @@ public abstract class MaximumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
-
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMax(reference.storageIdent(), arg);
+                    return new LongMax(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMax(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
index 65f1a4c44e..06a08968a5 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/MinimumAggregation.java
@@ -256,22 +256,19 @@ public abstract class MinimumAggregation extends AggregationFunction<Object, Obj
                                                            DocTableInfo table,
                                                            Version shardCreatedVersion,
                                                            List<Literal<?>> optionalParams) {
-            Reference reference = aggregationReferences.get(0);
+            Reference reference = getAggReference(aggregationReferences);
             if (reference == null) {
                 return null;
             }
-            if (!reference.hasDocValues()) {
-                return null;
-            }
-            DataType<?> arg = reference.valueType();
-            switch (arg.id()) {
+            DataType<?> valueType = reference.valueType();
+            switch (valueType.id()) {
                 case ByteType.ID:
                 case ShortType.ID:
                 case IntegerType.ID:
                 case LongType.ID:
                 case TimestampType.ID_WITH_TZ:
                 case TimestampType.ID_WITHOUT_TZ:
-                    return new LongMin(reference.storageIdent(), arg);
+                    return new LongMin(reference.storageIdent(), valueType);
 
                 case FloatType.ID:
                     return new FloatMin(reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
index 792f9d0ce6..12a05e277b 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/NumericSumAggregation.java
@@ -183,13 +183,10 @@ public class NumericSumAggregation extends AggregationFunction<BigDecimal, BigDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         return switch (reference.valueType().id()) {
             case ByteType.ID, ShortType.ID, IntegerType.ID, LongType.ID ->
                 new SumLong(returnType, reference.storageIdent());
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
index 526d8d0fe6..813cf993ae 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/StandardDeviationAggregation.java
@@ -231,13 +231,10 @@ public class StandardDeviationAggregation extends AggregationFunction<StandardDe
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
index 295126949b..76d032768d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/SumAggregation.java
@@ -196,16 +196,11 @@ public class SumAggregation<T extends Number> extends AggregationFunction<T, T>
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
-
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
index 4e10644e1c..77da28207d 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/TopKAggregation.java
@@ -222,19 +222,11 @@ public class TopKAggregation extends AggregationFunction<TopKAggregation.State,
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        if (aggregationReferences.isEmpty()) {
-            return null;
-        }
-
-        Reference reference = aggregationReferences.getFirst();
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
 
-        if (!reference.hasDocValues()) {
-            return null;
-        }
-
         if (optionalParams.isEmpty()) {
             return getDocValueAggregator(reference, DEFAULT_LIMIT, DEFAULT_MAX_CAPACITY);
         }
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
index d9d492afbc..67428d32c0 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/VarianceAggregation.java
@@ -230,13 +230,11 @@ public class VarianceAggregation extends AggregationFunction<Variance, Double> {
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
+
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
index a374fd69c9..00175dccc2 100644
--- a/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
+++ b/server/src/main/java/io/crate/execution/engine/aggregation/impl/average/AverageAggregation.java
@@ -312,13 +312,10 @@ public class AverageAggregation extends AggregationFunction<AverageAggregation.A
                                                        DocTableInfo table,
                                                        Version shardCreatedVersion,
                                                        List<Literal<?>> optionalParams) {
-        Reference reference = aggregationReferences.get(0);
+        Reference reference = getAggReference(aggregationReferences);
         if (reference == null) {
             return null;
         }
-        if (!reference.hasDocValues()) {
-            return null;
-        }
         switch (reference.valueType().id()) {
             case ByteType.ID:
             case ShortType.ID:
diff --git a/server/src/test/java/io/crate/execution/engine/collect/DocValuesAggregatesTest.java b/server/src/test/java/io/crate/execution/engine/collect/DocValuesAggregatesTest.java
index e48f78a27f..80d09890c5 100644
--- a/server/src/test/java/io/crate/execution/engine/collect/DocValuesAggregatesTest.java
+++ b/server/src/test/java/io/crate/execution/engine/collect/DocValuesAggregatesTest.java
@@ -62,6 +62,7 @@ public class DocValuesAggregatesTest extends CrateDummyClusterServiceUnitTest {
     private Functions functions;
     private SqlExpressions e;
     private DocTableInfo table;
+    private DocTableInfo partedTable;
 
     @Before
     public void setup() {
@@ -76,7 +77,20 @@ public class DocValuesAggregatesTest extends CrateDummyClusterServiceUnitTest {
                 )
                 """,
             clusterService);
-        Map<RelationName, AnalyzedRelation> sources = Map.of(name, new TableRelation(this.table));
+        RelationName partedName = new RelationName(DocSchemaInfo.NAME, "tbl_parted");
+        this.partedTable = SQLExecutor.partitionedTableInfo(
+            partedName,
+            """
+                create table tbl_parted (
+                    x long,
+                    y long,
+                    obj object as (col int not null)
+                ) PARTITIONED BY(y, obj['col'])
+                """,
+            clusterService);
+        Map<RelationName, AnalyzedRelation> sources = Map.of(
+            name, new TableRelation(this.table),
+            partedName, new TableRelation(this.partedTable));
         e = new SqlExpressions(sources);
     }
 
@@ -209,6 +223,22 @@ public class DocValuesAggregatesTest extends CrateDummyClusterServiceUnitTest {
             );
     }
 
+    @Test
+    public void test_create_aggregators_for_partitioned_col_returns_null() {
+        var aggregators = DocValuesAggregates.createAggregators(
+            functions,
+            mock(LuceneReferenceResolver.class),
+            List.of(countAggregation(0),
+                    countAggregation(1),
+                    longSumAggregation(1)
+            ),
+            List.of(e.asSymbol("tbl_parted.y"), e.asSymbol("tbl_parted.obj['col']")),
+            partedTable,
+            Version.CURRENT
+        );
+        assertThat(aggregators).isNull();
+    }
+
     private static Aggregation countAggregation(int inputCol) {
         return new Aggregation(
             CountAggregation.SIGNATURE,

```
