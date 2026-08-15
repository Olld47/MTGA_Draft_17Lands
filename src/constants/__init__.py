"""src.constants — domain-split constants package (ticket 07).

Each domain lives in one module (versions, paths, colors, ...); this
aggregator re-exports every public name so the 79 historical callers of
`from src.constants import X` keep working unchanged.

Editing a constant should touch only its domain module — never this file.
Desktop version single source: `desktop/src-tauri/tauri.conf.json`, rewritten
by `bump_desktop_version.py`; `versions.py` holds only the config migration
marker. `.coveragerc` measures the package.
"""

from src.constants.cards import *
from src.constants.colors import *
from src.constants.data_fields import *
from src.constants.database import *
from src.constants.datasets import *
from src.constants.event_strings import *
from src.constants.fixing import *
from src.constants.limited import *
from src.constants.paths import *
from src.constants.sets import *
from src.constants.ui import *
from src.constants.versions import *
from src.constants.wheel import *
