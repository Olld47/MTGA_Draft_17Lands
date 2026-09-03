"""mtga_bridge.version

The desktop app's own version. The bundle ships neither package.json nor
tauri.conf.json, and pytauri exposes no app version, so this literal is the
value the update check compares against. Version consistency is checked against
the desktop manifests and `tauri.conf.json`; release notes live in the tracked
root `release_notes.txt` file.
"""

DESKTOP_VERSION = "1.0.6"
