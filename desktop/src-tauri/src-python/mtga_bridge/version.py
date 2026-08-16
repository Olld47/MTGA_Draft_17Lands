"""mtga_bridge.version

The desktop app's own version. The bundle ships neither package.json nor
tauri.conf.json, and pytauri exposes no app version, so this literal is the
value the update check compares against. Pinned to the topmost CHANGELOG
heading by test_desktop_version_is_consistent_across_manifests.
"""

DESKTOP_VERSION = "1.0.3"
