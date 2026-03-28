# Structural Locator Trace

## Blueprint Summary
- **Root Cause**: The method `serverToPreservationBoundaryTs` previously returned a map of server addresses to their preservation boundary timestamps, which was not compatible with the new `BackupBoundaries` structure. | The absence of a class to manage time boundaries for WAL file cleanup during backup operations, which could lead to improper deletion of WAL files and compromise backup integrity.

## Hunk Segregation
- Code files: 2
- Test files: 0

## Code File Mappings

### `hbase-backup/src/main/java/org/apache/hadoop/hbase/backup/master/BackupLogCleaner.java`

**Hunks in this file**: 9

**Git Resolution**: Found `hbase-backup/src/main/java/org/apache/hadoop/hbase/backup/master/BackupLogCleaner.java`

**Fallback Mode**: direct no-tool LLM mapping used after recursion limit.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | declaration | `BackupLogCleaner` | `<import>` | 18–19 |
| 2 | declaration | `BackupLogCleaner` | `<import>` | 32–34 |
| 3 | cleanup | `BackupLogCleaner` | `<import>` | 41–41 |
| 4 | declaration | `BackupLogCleaner` | `None` | 56–58 |
| 5 | core_fix | `serverToPreservationBoundaryTs` | `serverToPreservationBoundaryTs` | 86–87 |
| 6 | core_fix | `serverToPreservationBoundaryTs` | `serverToPreservationBoundaryTs` | 112–112 |
| 7 | propagation | `BackupLogCleaner` | `serverToPreservationBoundaryTs` | 153–154 |
| 8 | propagation | `BackupLogCleaner` | `canDeleteFile` | 165–166 |
| 9 | core_fix | `canDeleteFile` | `canDeleteFile` | 200–201 |
### `hbase-backup/src/main/java/org/apache/hadoop/hbase/backup/util/BackupBoundaries.java`

**Hunks in this file**: 1

**Fallback Mode**: direct no-tool LLM mapping used after recursion limit.

| Hunk Idx | Role | Mainline Method | Target Method | Lines |
|---|---|---|---|---|
| 1 | core_fix | `BackupBoundaries` | `None` | 1–149 |
## Test File Mappings


## Consistency Map

_No renames detected — identity mapping assumed._
