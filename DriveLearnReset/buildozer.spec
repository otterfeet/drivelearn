[app]
title = DL Reset
package.name = dlreset
package.domain = org.drivelearn
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,android
orientation = portrait
fullscreen = 1
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.private_storage = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
