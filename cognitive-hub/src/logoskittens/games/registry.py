"""One registry. A new game adds one class to builtin()."""

from logoskittens.games.models import GamePlugin

_plugins: dict[str, GamePlugin] = {}
_loaded = False


def register(plugin, manifest_id: str | None = None) -> None:
    """Store the plugin by manifest id (H11). A class may be registered under a second manifest id.

    The instance then reads config/games/{manifest_id}.json and stamps that id on its decks.
    """
    if isinstance(plugin, type):
        plugin = plugin(manifest_id) if manifest_id else plugin()
    elif manifest_id and manifest_id != plugin.id:
        raise ValueError("Register the class to use a second manifest id.")
    _plugins[plugin.id] = plugin


def builtin() -> list:
    """The classes that ship, or (class, manifest id) for a variant. A later game adds one entry here."""
    from logoskittens.games.echo_chamber import EchoPlugin
    from logoskittens.games.fill_blank import FillInPlugin
    from logoskittens.games.interviewer import InterviewerPlugin
    from logoskittens.games.overhear import OverhearPlugin
    from logoskittens.games.ask_back import AskBackPlugin
    from logoskittens.games.cue_card import CueCardPlugin
    from logoskittens.games.paraphrase import ParaphrasePlugin
    from logoskittens.games.play_dumb import PlayDumbPlugin
    from logoskittens.games.probe import ProbePlugin
    from logoskittens.games.react import ReactPlugin
    from logoskittens.games.review import ReviewPlugin
    from logoskittens.games.roleplay import RoleplayPlugin
    from logoskittens.games.taboo import TabooPlugin
    from logoskittens.games.word_order import WordOrderPlugin

    return [
        ProbePlugin,
        EchoPlugin,
        InterviewerPlugin,
        FillInPlugin,
        (EchoPlugin, "listen"),
        WordOrderPlugin,
        CueCardPlugin,
        TabooPlugin,
        ParaphrasePlugin,
        PlayDumbPlugin,
        AskBackPlugin,
        ReactPlugin,
        OverhearPlugin,
        ReviewPlugin,
        RoleplayPlugin,
    ]


def load_builtin() -> None:
    global _loaded
    for entry in builtin():
        if isinstance(entry, tuple):
            register(entry[0], entry[1])
        else:
            register(entry)
    _loaded = True


def ensure_loaded() -> None:
    if not _loaded:
        load_builtin()


def get_plugin(game_id: str) -> GamePlugin | None:
    ensure_loaded()
    return _plugins.get(game_id)


def all_plugins() -> list[GamePlugin]:
    ensure_loaded()
    return list(_plugins.values())
