#!/bin/sh
# Compila "Ingeniero GT7" sin Gradle (Android 4.1+).
# Requiere (Ubuntu): aapt dalvik-exchange apksigner zipalign android-sdk-platform-23
set -e
cd "$(dirname "$0")"
JAR=/usr/lib/android-sdk/platforms/android-23/android.jar
rm -rf build && mkdir -p build/gen build/classes
aapt package -f -m -M AndroidManifest.xml -S res -I "$JAR" -J build/gen -F build/unsigned.apk
javac -encoding UTF-8 -nowarn -source 8 -target 8 -bootclasspath "$JAR" -d build/classes $(find src build/gen -name '*.java') 2>&1 | grep -v 'JAVA_TOOL\|bootstrap\|^warning\|warnings\?$' || true
[ -f build/classes/cl/eleva/gt7/MainActivity.class ]
dalvik-exchange --dex --output=build/classes.dex build/classes
(cd build && aapt add unsigned.apk classes.dex >/dev/null)
zipalign -f 4 build/unsigned.apk build/aligned.apk
[ -f gt7.keystore ] || keytool -genkeypair -keystore gt7.keystore -storepass ingenierogt7 -keypass ingenierogt7 \
  -alias gt7 -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Ingeniero GT7" >/dev/null 2>&1
apksigner sign --ks gt7.keystore --ks-pass pass:ingenierogt7 --ks-key-alias gt7 --v1-signing-enabled true --out ingeniero-gt7.apk build/aligned.apk
apksigner verify --min-sdk-version 16 ingeniero-gt7.apk && ls -la ingeniero-gt7.apk
