# ruff: noqa: F401
"""Lock plugin for Gaphor.

This plugin provides main menu access to lock/unlock functionality
for diagram items. It creates a LockService that integrates with
the Tools menu, allowing users to:

- Lock/Unlock selected items
- Toggle lock state
- Lock/Unlock all items in a diagram

The plugin also contains the core lockable functionality including:
- Lockable mixin class for diagram items
- draw_lock_icon function for rendering lock icons
- is_item_locked utility function
"""

from gaphor.plugins.lock.lockable import (
    LOCK_ICON_MARGIN,
    LOCK_ICON_SIZE,
    Lockable,
    draw_lock_icon,
    is_item_locked,
)
from gaphor.plugins.lock.lockservice import LockService
