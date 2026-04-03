# Detailed Line-by-Line Comparison

## The Critical Divergence Point

### Mainline Patch (main branch): Import section
```
@@ -17,6 +17,7 @@ import org.elasticsearch.action.search.SearchShardsRequest;
 import org.elasticsearch.action.search.SearchShardsResponse;
 import org.elasticsearch.action.support.TransportActions;
 import org.elasticsearch.cluster.node.DiscoveryNode;
+import org.elasticsearch.cluster.node.DiscoveryNodeRole;      ← NEW (line 20)
 import org.elasticsearch.common.breaker.CircuitBreakingException;
```

### Target Patch (8.19 branch): Import section
```
@@ -18,6 +18,7 @@ import org.elasticsearch.action.search.SearchShardsResponse;
 import org.elasticsearch.action.search.ShardSearchFailure;    ← ALREADY EXISTS in target
 import org.elasticsearch.action.support.TransportActions;
 import org.elasticsearch.cluster.node.DiscoveryNode;
+import org.elasticsearch.cluster.node.DiscoveryNodeRole;      ← NEW (line 21, not 20!)
 import org.elasticsearch.cluster.service.ClusterService;      ← DIFFERENT in target
```

## The Line Offset Problem

### What Phase 2 Claims (from JSON):
- DiscoveryNodeRole import should be at line **17**
- Comparator import should be at line **36**
- NODE_QUERY_ORDER should be at lines **54-57**
- order() method should be at lines **106-123**
- nodeToShardIds should be at line **279**

### Reality in Target File:
Let me count the actual lines in target...
