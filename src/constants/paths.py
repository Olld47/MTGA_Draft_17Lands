"""Filesystem paths, platform ids, and log-file locations.

BASE_DIR resolution must stay at import time: a source checkout derives the
data folders from the cwd, a frozen app from the bundle.
"""

import getpass
import os
import sys

from src.app_paths import resolve_base_dir


def get_base_dir():
    return resolve_base_dir()


def get_resource_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.getcwd())
    return os.getcwd()


BASE_DIR = get_base_dir()
RESOURCE_DIR = get_resource_dir()

DRAFT_LOG_FOLDER = os.path.join(BASE_DIR, "Logs")

LOCAL_DATA_FOLDER_PATH_WINDOWS = os.path.join(
    "Wizards of the Coast", "MTGA", "MTGA_Data"
)
LOCAL_DATA_FOLDER_PATH_WINDOWS_STEAM = os.path.join(
    "Steam", "steamapps", "common", "MTGA", "MTGA_Data"
)
LOCAL_DATA_FOLDER_PATH_OSX = os.path.join(
    "Library", "Application Support", "com.wizards.mtga"
)
LOCAL_DATA_FOLDER_PATH_OSX_STEAM = os.path.join(
    "Library",
    "Application Support",
    "Steam",
    "steamapps",
    "common",
    "MTGA",
    "MTGA_Data",
)
LOCAL_DATA_FOLDER_PATH_LINUX = next(
    filter(
        os.path.exists,
        [
            # Steam
            os.path.join(
                os.path.expanduser("~"),
                ".local",
                "share",
                "Steam",
                "steamapps",
                "common",
                "MTGA",
                "MTGA_Data",
            ),
            # Steam (debian)
            os.path.join(
                os.path.expanduser("~"),
                ".steam",
                "debian-installation",
                "steamapps",
                "common",
                "MTGA",
                "MTGA_Data",
            ),
            # Lutris
            os.path.join(
                os.path.expanduser("~"),
                "Games",
                "magic-the-gathering-arena",
                "drive_c",
                "Program Files",
                "Wizards of the Coast",
                "MTGA",
                "MTGA_Data",
            ),
            # Bottles
            os.path.join(
                os.path.expanduser("~"),
                ".var",
                "app",
                "com.usebottles.bottles",
                "data",
                "bottles",
                "bottles",
                "MTG-Arena",
                "drive_c",
                "Program Files",
                "Wizards of the Coast",
                "MTGA",
                "MTGA_Data",
            ),
        ],
    ),
    None,
)

LOCAL_DOWNLOADS_DATA = os.path.join("Downloads", "Raw")

SETS_FOLDER = os.path.join(BASE_DIR, "Sets")

TEMP_FOLDER = os.path.join(BASE_DIR, "Temp")
TEMP_LOCALIZATION_FILE = os.path.join(TEMP_FOLDER, "temp_localization.json")
TEMP_CARD_DATA_FILE = os.path.join(TEMP_FOLDER, "temp_card_data.json")

PLATFORM_ID_OSX = "darwin"
PLATFORM_ID_WINDOWS = "win32"
PLATFORM_ID_LINUX = "linux"

LOG_NAME = "Player.log"

LOG_LOCATION_WINDOWS = os.path.join(
    "Users",
    getpass.getuser(),
    "AppData",
    "LocalLow",
    "Wizards Of The Coast",
    "MTGA",
    LOG_NAME,
)
LOG_LOCATION_OSX = os.path.join(
    "Library", "Logs", "Wizards of the Coast", "MTGA", LOG_NAME
)
LOG_LOCATION_LINUX = os.path.join(
    ".local",
    "share",
    "Steam",
    "steamapps",
    "compatdata",
    "2141910",
    "pfx",
    "drive_c",
    "users",
    "steamuser",
    "AppData",
    "LocalLow",
    "Wizards Of The Coast",
    "MTGA",
    LOG_NAME,
)

WINDOWS_DRIVES = ["C:/", "D:/", "E:/", "F:/"]
WINDOWS_PROGRAM_FILES = ["Program Files", "Program Files (x86)"]

PLATFORM_LOG_DICT = {
    PLATFORM_ID_OSX: LOG_LOCATION_OSX,
    PLATFORM_ID_WINDOWS: LOG_LOCATION_WINDOWS,
}

__all__ = [
    "get_base_dir",
    "get_resource_dir",
    "BASE_DIR",
    "RESOURCE_DIR",
    "DRAFT_LOG_FOLDER",
    "LOCAL_DATA_FOLDER_PATH_WINDOWS",
    "LOCAL_DATA_FOLDER_PATH_WINDOWS_STEAM",
    "LOCAL_DATA_FOLDER_PATH_OSX",
    "LOCAL_DATA_FOLDER_PATH_OSX_STEAM",
    "LOCAL_DATA_FOLDER_PATH_LINUX",
    "LOCAL_DOWNLOADS_DATA",
    "SETS_FOLDER",
    "TEMP_FOLDER",
    "TEMP_LOCALIZATION_FILE",
    "TEMP_CARD_DATA_FILE",
    "PLATFORM_ID_OSX",
    "PLATFORM_ID_WINDOWS",
    "PLATFORM_ID_LINUX",
    "LOG_NAME",
    "LOG_LOCATION_WINDOWS",
    "LOG_LOCATION_OSX",
    "LOG_LOCATION_LINUX",
    "WINDOWS_DRIVES",
    "WINDOWS_PROGRAM_FILES",
    "PLATFORM_LOG_DICT",
]
