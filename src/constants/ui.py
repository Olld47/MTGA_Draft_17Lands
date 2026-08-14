"""UI presentation constants: fonts, themes, defaults, tables, grades.

Shared by the frozen tkinter UI and the desktop frontend defaults.
"""

FONT_SANS_SERIF = "Arial"
FONT_MONO_SPACE = "Courier"

UI_SIZE_DEFAULT = "100%"

UI_SIZE_DICT = {
    "40%": 0.4,
    "50%": 0.5,
    "60%": 0.6,
    "70%": 0.7,
    "80%": 0.8,
    "90%": 0.9,
    "100%": 1.0,
    "110%": 1.1,
    "120%": 1.2,
    "130%": 1.3,
    "140%": 1.4,
    "150%": 1.5,
    "160%": 1.6,
    "170%": 1.7,
    "180%": 1.8,
    "190%": 1.9,
    "200%": 2.0,
    "210%": 2.1,
    "220%": 2.2,
    "230%": 2.3,
    "240%": 2.4,
    "250%": 2.5,
}

# Appearance of the pytauri desktop UI. Kept separate from `Settings.theme`,
# which is the tkinter app's ttkbootstrap palette name and has 10 legal values.
DESKTOP_THEME_SYSTEM = "System"
DESKTOP_THEME_DARK = "Dark"
DESKTOP_THEME_LIGHT = "Light"

DESKTOP_THEME_LIST = [DESKTOP_THEME_SYSTEM, DESKTOP_THEME_DARK, DESKTOP_THEME_LIGHT]
DESKTOP_THEME_DEFAULT = DESKTOP_THEME_SYSTEM

# UI language for the pytauri desktop UI. Only the frontend reads this (it picks
# the locale dictionary); the tkinter app has no localization.
LANGUAGE_DEFAULT = "en"
LANGUAGE_LIST = ["en", "zh"]

# Which UI the default entry point (`main.py`) dispatches to. "desktop" is the
# pytauri app; "tkinter" is the legacy fallback, reachable via `--ui tkinter`
# or by setting `default_ui` to "tkinter".
DEFAULT_UI_DESKTOP = "desktop"
DEFAULT_UI_TKINTER = "tkinter"
DEFAULT_UI_LIST = [DEFAULT_UI_DESKTOP, DEFAULT_UI_TKINTER]
DEFAULT_UI_DEFAULT = DEFAULT_UI_DESKTOP

DECK_FILTER_FORMAT_NAMES = "Names"
DECK_FILTER_FORMAT_COLORS = "Colors"
DECK_FILTER_FORMAT_SET_NAMES = "Set Names"

DECK_FILTER_FORMAT_LIST = [DECK_FILTER_FORMAT_COLORS, DECK_FILTER_FORMAT_NAMES]

RESULT_FORMAT_WIN_RATE = "Percentage"
RESULT_FORMAT_RATING = "Rating"
RESULT_FORMAT_GRADE = "Grade"

RESULT_FORMAT_LIST = [RESULT_FORMAT_WIN_RATE, RESULT_FORMAT_RATING, RESULT_FORMAT_GRADE]

RESULT_UNKNOWN_STRING = " "
RESULT_UNKNOWN_VALUE = 0.0

TABLE_STYLE = "Treeview"

TABLE_MISSING = "missing"
TABLE_PACK = "pack"
TABLE_COMPARE = "compare"
TABLE_TAKEN = "taken"
TABLE_SUGGEST = "suggest"
TABLE_STATS = "stats"
TABLE_SETS = "sets"

TABLE_PROPORTIONS = [(1,), (0.75, 0.25), (0.60, 0.20, 0.20), (0.46, 0.18, 0.18, 0.18)]

STATS_HEADER_CONFIG = {
    "Colors": {"width": 0.19, "anchor": "w"},
    "1": {"width": 0.11, "anchor": "c"},
    "2": {"width": 0.11, "anchor": "c"},
    "3": {"width": 0.11, "anchor": "c"},
    "4": {"width": 0.11, "anchor": "c"},
    "5": {"width": 0.11, "anchor": "c"},
    "6+": {"width": 0.11, "anchor": "c"},
    "Total": {"width": 0.15, "anchor": "c"},
}

LETTER_GRADE_A_PLUS = "A+"
LETTER_GRADE_A = "A "
LETTER_GRADE_A_MINUS = "A-"
LETTER_GRADE_B_PLUS = "B+"
LETTER_GRADE_B = "B "
LETTER_GRADE_B_MINUS = "B-"
LETTER_GRADE_C_PLUS = "C+"
LETTER_GRADE_C = "C "
LETTER_GRADE_C_MINUS = "C-"
LETTER_GRADE_D_PLUS = "D+"
LETTER_GRADE_D = "D "
LETTER_GRADE_D_MINUS = "D-"
LETTER_GRADE_F = "F "
LETTER_GRADE_NA = " "
LETTER_GRADE_SB = "SB"

GRADE_ORDER_DICT = {
    LETTER_GRADE_A_PLUS: 14,
    LETTER_GRADE_A: 13,
    LETTER_GRADE_A_MINUS: 12,
    LETTER_GRADE_B_PLUS: 11,
    LETTER_GRADE_B: 10,
    LETTER_GRADE_B_MINUS: 9,
    LETTER_GRADE_C_PLUS: 8,
    LETTER_GRADE_C: 7,
    LETTER_GRADE_C_MINUS: 6,
    LETTER_GRADE_D_PLUS: 5,
    LETTER_GRADE_D: 4,
    LETTER_GRADE_D_MINUS: 3,
    LETTER_GRADE_F: 2,
    LETTER_GRADE_SB: 1,
    LETTER_GRADE_NA: 0,
}

TIER_CONVERSION_RATINGS_GRADES_DICT = {
    LETTER_GRADE_A_PLUS: 5.0,
    LETTER_GRADE_A: 4.6,
    LETTER_GRADE_A_MINUS: 4.2,
    LETTER_GRADE_B_PLUS: 3.8,
    LETTER_GRADE_B: 3.5,
    LETTER_GRADE_B_MINUS: 3.1,
    LETTER_GRADE_C_PLUS: 2.7,
    LETTER_GRADE_C: 2.3,
    LETTER_GRADE_C_MINUS: 1.9,
    LETTER_GRADE_D_PLUS: 1.5,
    LETTER_GRADE_D: 1.2,
    LETTER_GRADE_D_MINUS: 0.8,
    LETTER_GRADE_F: 0.4,
}

GRADE_DEVIATION_DICT = {
    LETTER_GRADE_A_PLUS: 2.00,
    LETTER_GRADE_A: 1.67,
    LETTER_GRADE_A_MINUS: 1.33,
    LETTER_GRADE_B_PLUS: 1,
    LETTER_GRADE_B: 0.67,
    LETTER_GRADE_B_MINUS: 0.33,
    LETTER_GRADE_C_PLUS: 0,
    LETTER_GRADE_C: -0.33,
    LETTER_GRADE_C_MINUS: -0.67,
    LETTER_GRADE_D_PLUS: -1.00,
    LETTER_GRADE_D: -1.33,
    LETTER_GRADE_D_MINUS: -1.67,
}

__all__ = [
    "FONT_SANS_SERIF",
    "FONT_MONO_SPACE",
    "UI_SIZE_DEFAULT",
    "UI_SIZE_DICT",
    "DESKTOP_THEME_SYSTEM",
    "DESKTOP_THEME_DARK",
    "DESKTOP_THEME_LIGHT",
    "DESKTOP_THEME_LIST",
    "DESKTOP_THEME_DEFAULT",
    "LANGUAGE_DEFAULT",
    "LANGUAGE_LIST",
    "DEFAULT_UI_DESKTOP",
    "DEFAULT_UI_TKINTER",
    "DEFAULT_UI_LIST",
    "DEFAULT_UI_DEFAULT",
    "DECK_FILTER_FORMAT_NAMES",
    "DECK_FILTER_FORMAT_COLORS",
    "DECK_FILTER_FORMAT_SET_NAMES",
    "DECK_FILTER_FORMAT_LIST",
    "RESULT_FORMAT_WIN_RATE",
    "RESULT_FORMAT_RATING",
    "RESULT_FORMAT_GRADE",
    "RESULT_FORMAT_LIST",
    "RESULT_UNKNOWN_STRING",
    "RESULT_UNKNOWN_VALUE",
    "TABLE_STYLE",
    "TABLE_MISSING",
    "TABLE_PACK",
    "TABLE_COMPARE",
    "TABLE_TAKEN",
    "TABLE_SUGGEST",
    "TABLE_STATS",
    "TABLE_SETS",
    "TABLE_PROPORTIONS",
    "STATS_HEADER_CONFIG",
    "LETTER_GRADE_A_PLUS",
    "LETTER_GRADE_A",
    "LETTER_GRADE_A_MINUS",
    "LETTER_GRADE_B_PLUS",
    "LETTER_GRADE_B",
    "LETTER_GRADE_B_MINUS",
    "LETTER_GRADE_C_PLUS",
    "LETTER_GRADE_C",
    "LETTER_GRADE_C_MINUS",
    "LETTER_GRADE_D_PLUS",
    "LETTER_GRADE_D",
    "LETTER_GRADE_D_MINUS",
    "LETTER_GRADE_F",
    "LETTER_GRADE_NA",
    "LETTER_GRADE_SB",
    "GRADE_ORDER_DICT",
    "TIER_CONVERSION_RATINGS_GRADES_DICT",
    "GRADE_DEVIATION_DICT",
]
