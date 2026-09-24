"""Load the turn plugins enabled for one tenant."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from helpmate.config import Settings
    from helpmate.plugins import TurnPlugin


def load_plugins(settings: "Settings", tenant_id: str) -> tuple["TurnPlugin", ...]:
    if not settings.return_saver_url:
        return ()
    if not settings.return_saver_key_for(tenant_id):
        return ()
    from helpmate.plugins.return_saver import build_plugin
    return (build_plugin(settings, tenant_id),)
