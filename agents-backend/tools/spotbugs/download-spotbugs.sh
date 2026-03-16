#!/bin/bash
# Download SpotBugs 4.9.3 and required dependencies
# Run this script to set up SpotBugs for validation

set -e

SPOTBUGS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOTBUGS_VERSION="4.9.3"
MAVEN_CENTRAL="https://repo1.maven.org/maven2"

echo "Downloading SpotBugs $SPOTBUGS_VERSION and dependencies to $SPOTBUGS_DIR..."

# Function to download if not exists
download_if_missing() {
    local file="$1"
    local url="$2"
    if [ ! -f "$file" ]; then
        echo "  Downloading $(basename "$file")..."
        curl -sL -o "$file" "$url"
    else
        echo "  $(basename "$file") already exists, skipping..."
    fi
}

# SpotBugs core
download_if_missing \
    "$SPOTBUGS_DIR/spotbugs-$SPOTBUGS_VERSION.jar" \
    "$MAVEN_CENTRAL/com/github/spotbugs/spotbugs/$SPOTBUGS_VERSION/spotbugs-$SPOTBUGS_VERSION.jar"

# SpotBugs annotations
download_if_missing \
    "$SPOTBUGS_DIR/spotbugs-annotations-$SPOTBUGS_VERSION.jar" \
    "$MAVEN_CENTRAL/com/github/spotbugs/spotbugs-annotations/$SPOTBUGS_VERSION/spotbugs-annotations-$SPOTBUGS_VERSION.jar"

# ASM (bytecode analysis)
ASM_VERSION="9.7"
download_if_missing \
    "$SPOTBUGS_DIR/asm-$ASM_VERSION.jar" \
    "$MAVEN_CENTRAL/org/ow2/asm/asm/$ASM_VERSION/asm-$ASM_VERSION.jar"
download_if_missing \
    "$SPOTBUGS_DIR/asm-tree-$ASM_VERSION.jar" \
    "$MAVEN_CENTRAL/org/ow2/asm/asm-tree/$ASM_VERSION/asm-tree-$ASM_VERSION.jar"
download_if_missing \
    "$SPOTBUGS_DIR/asm-analysis-$ASM_VERSION.jar" \
    "$MAVEN_CENTRAL/org/ow2/asm/asm-analysis/$ASM_VERSION/asm-analysis-$ASM_VERSION.jar"
download_if_missing \
    "$SPOTBUGS_DIR/asm-commons-$ASM_VERSION.jar" \
    "$MAVEN_CENTRAL/org/ow2/asm/asm-commons/$ASM_VERSION/asm-commons-$ASM_VERSION.jar"
download_if_missing \
    "$SPOTBUGS_DIR/asm-util-$ASM_VERSION.jar" \
    "$MAVEN_CENTRAL/org/ow2/asm/asm-util/$ASM_VERSION/asm-util-$ASM_VERSION.jar"

# BCEL (bytecode engineering)
download_if_missing \
    "$SPOTBUGS_DIR/bcel-6.9.0.jar" \
    "$MAVEN_CENTRAL/org/apache/bcel/bcel/6.9.0/bcel-6.9.0.jar"

# Logging
download_if_missing \
    "$SPOTBUGS_DIR/slf4j-api-2.0.16.jar" \
    "$MAVEN_CENTRAL/org/slf4j/slf4j-api/2.0.16/slf4j-api-2.0.16.jar"
download_if_missing \
    "$SPOTBUGS_DIR/log4j-api-2.24.3.jar" \
    "$MAVEN_CENTRAL/org/apache/logging/log4j/log4j-api/2.24.3/log4j-api-2.24.3.jar"
download_if_missing \
    "$SPOTBUGS_DIR/log4j-core-2.24.3.jar" \
    "$MAVEN_CENTRAL/org/apache/logging/log4j/log4j-core/2.24.3/log4j-core-2.24.3.jar"
download_if_missing \
    "$SPOTBUGS_DIR/log4j-slf4j2-impl-2.24.3.jar" \
    "$MAVEN_CENTRAL/org/apache/logging/log4j/log4j-slf4j2-impl/2.24.3/log4j-slf4j2-impl-2.24.3.jar"

# XML processing
download_if_missing \
    "$SPOTBUGS_DIR/dom4j-2.1.4.jar" \
    "$MAVEN_CENTRAL/org/dom4j/dom4j/2.1.4/dom4j-2.1.4.jar"
download_if_missing \
    "$SPOTBUGS_DIR/jaxen-2.0.0.jar" \
    "$MAVEN_CENTRAL/jaxen/jaxen/2.0.0/jaxen-2.0.0.jar"

# Apache Commons
download_if_missing \
    "$SPOTBUGS_DIR/commons-lang3-3.17.0.jar" \
    "$MAVEN_CENTRAL/org/apache/commons/commons-lang3/3.17.0/commons-lang3-3.17.0.jar"
download_if_missing \
    "$SPOTBUGS_DIR/commons-text-1.10.0.jar" \
    "$MAVEN_CENTRAL/org/apache/commons/commons-text/1.10.0/commons-text-1.10.0.jar"
download_if_missing \
    "$SPOTBUGS_DIR/commons-codec-1.15.jar" \
    "$MAVEN_CENTRAL/commons-codec/commons-codec/1.15/commons-codec-1.15.jar"

# Other dependencies
download_if_missing \
    "$SPOTBUGS_DIR/gson-2.11.0.jar" \
    "$MAVEN_CENTRAL/com/google/code/gson/gson/2.11.0/gson-2.11.0.jar"
download_if_missing \
    "$SPOTBUGS_DIR/jsr305-3.0.2.jar" \
    "$MAVEN_CENTRAL/com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar"
download_if_missing \
    "$SPOTBUGS_DIR/jcip-annotations-1.0-1.jar" \
    "$MAVEN_CENTRAL/com/github/stephenc/jcip/jcip-annotations/1.0-1/jcip-annotations-1.0-1.jar"
download_if_missing \
    "$SPOTBUGS_DIR/error_prone_annotations-2.27.0.jar" \
    "$MAVEN_CENTRAL/com/google/errorprone/error_prone_annotations/2.27.0/error_prone_annotations-2.27.0.jar"

# HTTP client (for some detectors)
download_if_missing \
    "$SPOTBUGS_DIR/httpcore5-5.1.3.jar" \
    "$MAVEN_CENTRAL/org/apache/httpcomponents/core5/httpcore5/5.1.3/httpcore5-5.1.3.jar"
download_if_missing \
    "$SPOTBUGS_DIR/httpcore5-h2-5.1.3.jar" \
    "$MAVEN_CENTRAL/org/apache/httpcomponents/core5/httpcore5-h2/5.1.3/httpcore5-h2-5.1.3.jar"
download_if_missing \
    "$SPOTBUGS_DIR/httpclient5-5.1.3.jar" \
    "$MAVEN_CENTRAL/org/apache/httpcomponents/client5/httpclient5/5.1.3/httpclient5-5.1.3.jar"

echo ""
echo "✓ SpotBugs setup complete!"
echo ""
echo "JAR files in $SPOTBUGS_DIR:"
ls -1 "$SPOTBUGS_DIR"/*.jar 2>/dev/null | wc -l | xargs echo "  Total:"
echo ""
echo "To verify installation:"
echo "  java -cp \"$SPOTBUGS_DIR/*\" edu.umd.cs.findbugs.LaunchAppropriateUI -textui -version"
