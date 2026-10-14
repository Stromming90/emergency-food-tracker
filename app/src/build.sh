#!/bin/bash
# Build the Emergency Food Tracker Android APK without Gradle.
# Requirements: JDK 17 (in /opt/android/jdk-17*), Android build-tools 34,
# android.jar (platform 34). Produces /home/user/eft/app/eft-app.apk(.b64).
set -e
export JAVA_HOME=$(ls -d /opt/android/jdk-17* | head -1)
export PATH=$JAVA_HOME/bin:$PATH
BT=$(ls -d /opt/android/bt/*/ | head -1)
JAR=/opt/android/plat/android-34/android.jar
SRC=/home/user/eft/app/src
OUT=$SRC/build
rm -rf $OUT && mkdir -p $OUT/classes $OUT/lib

echo "[1/7] aapt2 compile resources"
$BT/aapt2 compile --dir $SRC/res -o $OUT/res.zip

echo "[2/7] aapt2 link"
$BT/aapt2 link -o $OUT/base.apk \
  -I "$JAR" \
  --manifest $SRC/AndroidManifest.xml \
  --min-sdk-version 24 --target-sdk-version 34 \
  --version-code 29 --version-name 2.7.2 \
  $OUT/res.zip

echo "[3/7] javac"
$JAVA_HOME/bin/javac -source 8 -target 8 -nowarn \
  -classpath "$JAR" \
  -d $OUT/classes \
  $(find $SRC/java -name "*.java")

echo "[4/7] d8 dex"
$JAVA_HOME/bin/java -cp $BT/lib/d8.jar com.android.tools.r8.D8 \
  --lib "$JAR" --release --output $OUT/lib \
  $(find $OUT/classes -name "*.class")

echo "[5/7] package"
cp $OUT/base.apk $OUT/app-unsigned.apk
cd $OUT/lib && zip -qj $OUT/app-unsigned.apk classes.dex && cd /

echo "[6/7] zipalign"
$BT/zipalign -f 4 $OUT/app-unsigned.apk $OUT/app-aligned.apk

echo "[7/7] sign"
if [ ! -f $SRC/debug.keystore ]; then
  if [ -f $SRC/debug.keystore.b64 ]; then
    # restore the committed signing key so updates install over the old app
    base64 -d $SRC/debug.keystore.b64 > $SRC/debug.keystore
  else
    $JAVA_HOME/bin/keytool -genkeypair -keystore $SRC/debug.keystore \
      -storepass android -keypass android -alias eft \
      -keyalg RSA -keysize 2048 -validity 10000 \
      -dname "CN=Emergency Food Tracker,O=Stromming,C=SE"
  fi
fi
$BT/apksigner sign --ks $SRC/debug.keystore --ks-pass pass:android \
  --key-pass pass:android --out $OUT/eft-app.apk $OUT/app-aligned.apk
$BT/apksigner verify --print-certs $OUT/eft-app.apk | head -3

mkdir -p /home/user/eft/app
cp $OUT/eft-app.apk /home/user/eft/app/eft-app.apk
base64 -w 76 $OUT/eft-app.apk > /home/user/eft/app/eft-app.apk.b64
ls -la /home/user/eft/app/
echo BUILD-OK
