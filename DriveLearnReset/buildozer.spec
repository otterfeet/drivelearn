[app]
title = DriveLearn
package.name = drivelearn
package.domain = org.drivelearn
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav
version = 1.0
requirements = python3,kivy,android
orientation = portrait
fullscreen = 1

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 34
android.minapi = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license = True
android.private_storage = True

[buildozer]
log_level = 2
warn_on_root = 1
