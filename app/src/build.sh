#!/bin/bash
# Build the Emergency Food Tracker Android APK without Gradle.
#
# Requirements: JDK 17+, Android build-tools 34 and the android-34
# platform jar. Paths can be overridden via env vars:
#   JAVA_HOME, ANDROID_BT (build-tools dir), ANDROID_JAR (platform jar)
# Defaults fit the dev machine and GitHub Actions runners (which provide
# ANDROID_SDK_ROOT). Output: app/eft-app.apk(.b64) next to this dir's
# parent — the b64 file is committed to the repo so /app.apk serves it.
set -e

if [ -z "$JAVA_HOME" ]; then
  export JAVA_HOME=$(ls -d /opt/android/jdk-17* 2>/dev/null | head -1)
fi
export PATH=$JAVA_HOME/bin:$PATH
if [ -z "$ANDROID_BT" ]; then ANDROID_BT=$(ls -d /opt/android/bt/*/ 2>/dev/null | head -1); fi
if [ -z "$ANDROID_JAR" ]; then ANDROID_JAR=/opt/android/plat/android-34/android.jar; fi

SRC=$(cd "$(dirname "$0")" && pwd)
OUT=$SRC/build
rm -rf "$OUT" && mkdir -p "$OUT/classes" "$OUT/lib"

echo "[1/7] aapt2 compile resources"
"$ANDROID_BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res.zip"

echo "[2/7] aapt2 link"
"$ANDROID_BT/aapt2" link -o "$OUT/base.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$SRC/AndroidManifest.xml" \
  --min-sdk-version 24 --target-sdk-version 34 \
  --version-code 38 --version-name 2.12.6 \
  "$OUT/res.zip"

echo "[3/7] javac"
javac -source 8 -target 8 -nowarn \
  -classpath "$ANDROID_JAR" \
  -d "$OUT/classes" \
  $(find "$SRC/java" -name "*.java")

echo "[4/7] d8 dex"
java -cp "$ANDROID_BT/lib/d8.jar" com.android.tools.r8.D8 \
  --lib "$ANDROID_JAR" --release --output "$OUT/lib" \
  $(find "$OUT/classes" -name "*.class")

echo "[5/7] package"
cp "$OUT/base.apk" "$OUT/app-unsigned.apk"
cd "$OUT/lib" && zip -qj "$OUT/app-unsigned.apk" classes.dex && cd "$SRC"

echo "[6/7] zipalign"
"$ANDROID_BT/zipalign" -f 4 "$OUT/app-unsigned.apk" "$OUT/app-aligned.apk"

echo "[7/7] sign"
if [ ! -f "$SRC/debug.keystore" ]; then
  if [ -f "$SRC/debug.keystore.b64" ]; then
    # restore the committed signing key so updates install over the old app
    base64 -d "$SRC/debug.keystore.b64" > "$SRC/debug.keystore"
  else
    keytool -genkeypair -keystore "$SRC/debug.keystore" \
      -storepass android -keypass android -alias eft \
      -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Emergency Food Tracker,O=Stromming,C=SE"
  fi
fi
"$ANDROID_BT/apksigner" sign --ks "$SRC/debug.keystore" --ks-pass pass:android \
  --key-pass pass:android --out "$OUT/eft-app.apk" "$OUT/app-aligned.apk"
"$ANDROID_BT/apksigner" verify --print-certs "$OUT/eft-app.apk" | head -3

cp "$OUT/eft-app.apk" "$SRC/../eft-app.apk"
base64 -w 76 "$OUT/eft-app.apk" > "$SRC/../eft-app.apk.b64"
ls -la "$SRC/.."
echo BUILD-OK
