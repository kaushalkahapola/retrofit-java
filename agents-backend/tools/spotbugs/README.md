# SpotBugs Dependencies

This directory contains SpotBugs 4.9.3 and its dependencies for static analysis validation.

## Setup

Run the download script to fetch all required JARs:

```bash
cd agents-backend/tools/spotbugs
chmod +x download-spotbugs.sh
./download-spotbugs.sh
```

## Verify Installation

```bash
java -cp "spotbugs-4.9.3.jar:*" edu.umd.cs.findbugs.LaunchAppropriateUI -textui -version
```

## Files

- `spotbugs-4.9.3.jar` - Main SpotBugs engine
- `spotbugs-annotations-4.9.3.jar` - SpotBugs annotations
- `*.jar` - Runtime dependencies (ASM, BCEL, Log4j, etc.)
- `download-spotbugs.sh` - Script to download all dependencies

## Notes

- JAR files are **not** committed to Git (see root `.gitignore`)
- Always run `download-spotbugs.sh` after cloning the repository
- Requires Java 21 or later to run SpotBugs

## Manual Download (if script fails)

If the download script fails, manually download from Maven Central:
- https://repo1.maven.org/maven2/com/github/spotbugs/spotbugs/4.9.3/
