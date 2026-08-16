"""Remote repository endpoints.

Single source for the GitHub repo / GitHub Pages base URLs that the client,
bridge and ETL reference. On a namespace or project move, change the three
values here — the static site templates receive the same values at deploy
time via sentinel injection (server/load.py reads them from server.config,
which mirrors these). Kept URL-only: 17Lands/Scryfall endpoints stay in their
own domain modules.
"""

GITHUB_REPO_URL = "https://github.com/Olld47/MTGA_Draft_17Lands"
GITHUB_API_REPO_URL = "https://api.github.com/repos/Olld47/MTGA_Draft_17Lands"
GITHUB_PAGES_URL = "https://olld47.github.io/MTGA_Draft_17Lands"

__all__ = ["GITHUB_REPO_URL", "GITHUB_API_REPO_URL", "GITHUB_PAGES_URL"]
