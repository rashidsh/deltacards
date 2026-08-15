import argparse
import base64
import binascii
import json
import random
import sys
from typing import Any

import colorama
from readchar import key, readkey
from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.prompt import Prompt
from rich.table import Column, Table
from rich.theme import Theme

from deltacards.ai import AIGameController
from deltacards.ai.simple import SimpleAI
from deltacards.app.action_log import ActionLogFormatter, LogView
from deltacards.content.loader import load
from deltacards.engine.constants import BEGINNER_DECKS
from deltacards.engine.game import Game
from deltacards.engine.runner import GameRunner
from deltacards.model.artifacts import ArtifactRarity
from deltacards.model.cards import Monster, Spell
from deltacards.model.entity import Entity
from deltacards.model.enums import CardKeyword, CardStatusId, PlayerId
from deltacards.model.player import Player
from deltacards.model.requests import (
    Attack,
    ChooseEntityPrompt,
    EndTurn,
    PlayMonster,
    PlaySpell,
    ChoiceResponse,
    MulliganResponse,
    PendingChoiceRequest,
    PendingMulliganRequest,
    PendingPlayerActionRequest,
    PlayerActionResponse,
)


SOUL_NAMES_TEXT = ", ".join([
    f"[soul-{soul_name}]{soul_name}[/soul-{soul_name}]"
    for soul_name in BEGINNER_DECKS.keys()
])
PROMPT_DECK_TEXT = f"""
[bold]Choose your deck:[/bold]
- Leave the input empty and press Enter for a random starter deck;
- or, choose one of the starter decks: {SOUL_NAMES_TEXT};
- or, paste base64/JSON deck code;
- or, configure decks & other details via CLI arguments (look at README.md for more details).
"""

HELP_TEXT = """
[bold]Available commands:[/bold]
  [cyan]help[/cyan] / [cyan]?[/cyan]                        Show this help.
  [cyan]legal[/cyan] / [cyan]l[/cyan]                       Show legal player actions.
  [cyan]dustpile[/cyan] / [cyan]d[/cyan]                    View your dustpile.
  [cyan]play <card_id> \\[slot][/cyan]           Play a card (when playing a monster, you can also specify a slot).
  [cyan]attack <attacker_id> <id|op>[/cyan]    Attack a monster or the opponent.
  [cyan]end[/cyan]                             End the turn.
  [cyan]quit[/cyan] / [cyan]q[/cyan]                        Exit the CLI.
"""

CONSOLE_THEME = Theme({
    'g': 'bold yellow',
    'atk': 'bold red',
    'atk-paralyzed': 'bold',
    'hp': 'bold green',
    'hp-low': 'bold yellow',
    'monster': 'bold bright_magenta',
    'spell': 'bold cyan',
    'warn': 'bold orange3',
    'error': 'bold red',

    'rarity-base': '#808080',
    'rarity-common': '#ffffff',
    'rarity-rare': '#00b8ff',
    'rarity-epic': '#d535d9',
    'rarity-legendary': '#ffd700',
    'rarity-determination': '#ff0000',
    'rarity-token': '#00c800',

    'soul-kindness': '#00c000',
    'soul-determination': '#ff0000',
    'soul-patience': '#41fcff',
    'soul-bravery': '#fca500',
    'soul-integrity': '#0064ff',
    'soul-perseverance': '#d535d9',
    'soul-justice': '#ffff00',
})


class CLIRunner:
    def __init__(self, runner: GameRunner, human_player_ids: set[PlayerId]):
        self.runner = runner
        self.game = self.runner.game
        self.human_player_ids = human_player_ids

        self._console = Console(theme=CONSOLE_THEME, highlight=False)

        self._layout = Layout(name='root')
        self._layout.split_column(
            Layout(name='field', ratio=1, size=20),
            Layout(name='bottom', minimum_size=7),
        )
        self._layout['bottom'].split_column(
            Layout(name='log', ratio=1, minimum_size=3),
            Layout(name='input', size=5),
        )

        self._live: Live | None = None

        self._log_entries: list[str] = []
        self._max_log_entries = 1000
        self._log_scroll = 0

        self._input_prompt = ''
        self._input_text = ''
        self._input_cursor = 0
        self._input_context = ''
        self._input_help = ''
        self._input_history: list[str] = []

        self._active_player_id: PlayerId = PlayerId.P1
        self._current_request: Any | None = None
        self._should_exit = False

    def print(self, *objects):
        if self._live is None:
            self._console.print(*objects)
            return

        for obj in objects:
            self._append_log(str(obj))

        self._refresh_live()

    def _append_log(self, text: str) -> None:
        lines = text.splitlines() or ['']
        self._log_entries.extend(lines)

        overflow = max(len(self._log_entries) - self._max_log_entries, 0)
        if overflow > 0:
            del self._log_entries[:overflow]

        at_bottom = self._log_scroll == 0
        if at_bottom:
            self._log_scroll = 0
        else:
            self._log_scroll += len(lines)

        self._clamp_log_scroll()

    def _refresh_live(self) -> None:
        if self._live is None:
            return

        self._layout['field'].update(self.render_field())
        self._layout['log'].update(self.render_log_panel())
        self._layout['input'].update(self.render_input_panel())

        self._live.refresh()

    def _default_viewer_id(self) -> PlayerId:
        if self._active_player_id in self.human_player_ids:
            return self._active_player_id

        if self.human_player_ids:
            return sorted(self.human_player_ids)[0]

        winner = self.game.winner_id()
        if winner:
            return winner

        return PlayerId.P1

    # --------------------
    # Formatting helpers
    # --------------------

    def _entity_to_str(self, entity: Entity):
        if isinstance(entity, Monster):
            atk_style = 'atk-paralyzed' if entity.get_status(CardStatusId.PARALYZED) else 'atk'
            hp_style = 'hp-low' if entity.hp < entity.max_hp else 'hp'
            return (f"[{entity.id}] [g]{entity.cost}[/g]/"
                    f"[{atk_style}]{entity.attack}[/{atk_style}]/"
                    f"[{hp_style}]{entity.hp}[/{hp_style}] "
                    f"[monster]{entity.template.name}[/monster]")

        elif isinstance(entity, Spell):
            return f"[{entity.id}] [g]{entity.cost}G[/g] [spell]{entity.template.name}[/spell]"

        return str(entity)

    # --------------------
    # Log panel
    # --------------------

    def _visible_log_lines(self) -> int:
        height = self._console.size.height
        field_size = self._layout['field'].size
        input_size = self._layout['input'].size
        misc_elements_size = 3  # panel borders

        return max(height - field_size - input_size - misc_elements_size, 1)

    def _clamp_log_scroll(self) -> None:
        max_scroll = max(len(self._log_entries) - self._visible_log_lines(), 0)
        self._log_scroll = min(max(self._log_scroll, 0), max_scroll)

    def _scroll_log(self, amount: int) -> None:
        self._log_scroll += amount
        self._clamp_log_scroll()

    def render_log_panel(self):
        self._clamp_log_scroll()

        visible = self._visible_log_lines()
        end = len(self._log_entries) - self._log_scroll
        start = max(0, end - visible)

        lines = []

        if start > 0:
            lines.append(f"[bright_black]↑ {start} older line(s) · PgUp[/bright_black]")

        lines.extend(self._log_entries[start:end])

        if end < len(self._log_entries):
            lines.append(f"[bright_black]↓ {len(self._log_entries) - end} newer line(s) · PgDn[/bright_black]")

        return Panel(
            Group(*lines),
            title="Log",
            border_style='bright_black',
        )

    # --------------------
    # Field panel
    # --------------------

    def _render_player_table(self, player):
        def artifact_rarity_style(artifact):
            if artifact.rarity is ArtifactRarity.LEGENDARY:
                return 'rarity-legendary'
            if artifact.rarity is ArtifactRarity.TOKEN:
                return 'rarity-token'

            return 'rarity-common'

        soul_name = player.soul.__class__.__name__.lower()
        artifact_text = " ".join(
            (
                f"[{artifact_rarity_style(artifact)}]" +
                artifact.__class__.__name__ + (("[" + str(artifact.counter) + "]") if artifact.counter > 0 else "") +
                f"[/{artifact_rarity_style(artifact)}]"
            )
            for artifact in player.artifacts
        )

        player_table = Table(
            Column(ratio=3),
            Column(ratio=2),
            Column(ratio=3, justify='right'),
            expand=True,
            show_header=False,
            show_lines=True,
            box=box.HORIZONTALS,
        )
        player_table.add_row(
            f"[soul-{soul_name}]♥ {player}[/soul-{soul_name}] [rarity-base]" + artifact_text,
            Group(
                ProgressBar(completed=player.hp / player.max_hp * 100, width=15),
                f" {player.hp}/{player.max_hp} [hp]HP[/hp]",
            ),
            Group(
                (f"T: {self.game.turn}  " if player.id == self._active_player_id else "") +
                f"D: {len(player.deck)}  "
                f"H: {len(player.hand)}  "
                f"[g]G[/g]: {player.gold}"
            )
        )

        return player_table

    def _render_slot(self, monster: Monster | None):
        if monster is None:
            return Group(*([''] * 3))

        atk_style = 'atk-paralyzed' if monster.get_status(CardStatusId.PARALYZED) else 'atk'
        hp_style = 'hp-low' if monster.hp < monster.max_hp else 'hp'

        extra_symbols = ''
        if monster.keywords & CardKeyword.CHARGE:
            extra_symbols += "[green]↑[/green]"
        if monster.keywords & CardKeyword.HASTE:
            extra_symbols += "[yellow]↑[/yellow]"
        if monster.keywords & CardKeyword.TAUNT:
            extra_symbols += "[bold cyan]\\[T][/bold cyan]"
        if monster.keywords & CardKeyword.KR:
            extra_symbols += "[magenta1]KR[/magenta1]"
        if monster.keywords & CardKeyword.SILENCED:
            extra_symbols += "[bright_red](X)[/bright_red]"

        return Group(
            f"[{monster.id}] [b]{monster.template.name}[/b] {extra_symbols}\n"
            f"[{atk_style}]{monster.attack}[/{atk_style}]/[{hp_style}]{monster.hp}[/{hp_style}]"
        )

    def _render_board_table(self, top_player, bottom_player):
        board_table = Table(
            Column(ratio=1, vertical='middle'),
            Column(ratio=1, vertical='middle'),
            Column(ratio=1, vertical='middle'),
            Column(ratio=1, vertical='middle'),
            expand=True,
            show_header=False,
            show_lines=True,
            box=box.SQUARE,
        )

        board_table.add_row(*(
            self._render_slot(monster)
            for monster in top_player.board._cards
        ))
        board_table.add_row(*(
            self._render_slot(monster)
            for monster in bottom_player.board._cards
        ))

        return board_table

    def _render_hand(self, player):
        return f"Hand: {', '.join(self._entity_to_str(e) for e in player.hand.cards)}"

    def render_field(self):
        bottom_player = self.game.player(self._active_player_id)
        top_player = bottom_player.opponent

        title = f"Turn {self.game.turn}"

        return Panel(
            Group(
                self._render_player_table(top_player),
                self._render_board_table(top_player, bottom_player),
                self._render_player_table(bottom_player),
                self._render_hand(bottom_player),
            ),
            title=title,
            subtitle=f"Player {bottom_player.id.value}",
            border_style='blue',
        )

    # --------------------
    # Input panel
    # --------------------

    def _render_input_text(self) -> str:
        text_before = escape(self._input_text[:self._input_cursor])

        if self._input_cursor < len(self._input_text):
            cursor_char = escape(self._input_text[self._input_cursor])
            text_after = escape(self._input_text[self._input_cursor + 1:])
        else:
            cursor_char = ' '
            text_after = ''

        return f'{text_before}[reverse]{cursor_char}[/reverse]{text_after}'

    def render_input_panel(self):
        lines = []

        if self._input_context:
            lines.append(self._input_context)

        if self._input_prompt:
            lines.append(f"{self._input_prompt} {self._render_input_text()}")
        else:
            lines.append("[bright_black]Waiting for game engine...[/bright_black]")

        if self._input_help:
            lines.append(f"[bright_black]{self._input_help}[/bright_black]")

        return Panel(
            Group(*lines),
            title='Input',
            border_style='cyan',
        )

    def _read_line(
        self,
        prompt: str,
        context: str = '',
        help_text: str = '',
        history: bool = True,
    ) -> str:
        self._input_prompt = prompt
        self._input_context = context
        self._input_help = help_text
        self._input_text = ''
        self._input_cursor = 0

        self._refresh_live()

        history_index = len(self._input_history)
        history_saved = ''

        while True:
            k = readkey()

            if k == key.ENTER:
                line = self._input_text

                if line:
                    self._append_log(f'{prompt} {escape(line)}')

                    if history:
                        if len(self._input_history) == 0 or self._input_history[-1] != line:
                            self._input_history.append(line)
                            del self._input_history[:-100]

                self._input_prompt = ''
                self._input_context = ''
                self._input_help = ''
                self._input_text = ''
                self._input_cursor = 0
                self._refresh_live()

                return line

            elif k == key.PAGE_UP:
                self._scroll_log(self._visible_log_lines())
                self._refresh_live()
                continue

            elif k == key.PAGE_DOWN:
                self._scroll_log(-self._visible_log_lines())
                self._refresh_live()
                continue

            elif k == key.UP and history:
                if self._input_history:
                    if history_index == len(self._input_history):
                        history_saved = self._input_text

                    history_index = max(0, history_index - 1)
                    self._input_text = self._input_history[history_index]
                    self._input_cursor = len(self._input_text)

            elif k == key.DOWN and history:
                if history_index < len(self._input_history):
                    history_index += 1

                    if history_index == len(self._input_history):
                        self._input_text = history_saved
                    else:
                        self._input_text = self._input_history[history_index]

                    self._input_cursor = len(self._input_text)

            elif k == key.LEFT:
                self._input_cursor = max(0, self._input_cursor - 1)

            elif k == key.RIGHT:
                self._input_cursor = min(len(self._input_text), self._input_cursor + 1)

            elif k == key.HOME:
                self._input_cursor = 0

            elif k == key.END:
                self._input_cursor = len(self._input_text)

            elif k == key.BACKSPACE:
                if self._input_cursor > 0:
                    self._input_text = (
                        self._input_text[:self._input_cursor - 1] +
                        self._input_text[self._input_cursor:]
                    )
                    self._input_cursor -= 1

            elif len(k) == 1 and k.isprintable():
                self._input_text = (
                    self._input_text[:self._input_cursor] +
                    k +
                    self._input_text[self._input_cursor:]
                )
                self._input_cursor += 1

            self._refresh_live()

    # --------------------
    # Command handling
    # --------------------

    def handle_command(self, request_id: int, player_id: PlayerId, text: str) -> None:
        sp = text.split()
        if not text:
            return

        cmd, args = sp[0], sp[1:]

        if cmd in ('?', 'h', 'help'):
            self.print(HELP_TEXT)

        elif cmd in ('l', 'legal'):
            options = []
            seen_card_ids = []

            for action in self.runner.legal_player_actions(player_id):
                if isinstance(action, (PlayMonster, PlaySpell)):
                    # Filter duplicate monster play actions (available board slots are ignored here)
                    if action.card_id in seen_card_ids:
                        continue

                    seen_card_ids.append(action.card_id)
                    action_cmd, desc = (
                        f"play {action.card_id}",
                        f"Play {self._entity_to_str(self.game.entity(action.card_id))}"
                    )

                elif isinstance(action, Attack):
                    defender_name = "op" if action.defender_id is self.game.player(player_id).opponent.id else action.defender_id
                    action_cmd, desc = (
                        f"attack {action.attacker_id} {defender_name}",
                        f"Attack {self._entity_to_str(self.game.entity(action.attacker_id))} -> "
                        f"{self._entity_to_str(self.game.entity(action.defender_id))}"
                    )

                elif isinstance(action, EndTurn):
                    action_cmd, desc = "end", "End the turn"

                else:
                    raise RuntimeError(f"Unknown `PlayerAction` type: {type(action).__name__}")

                options.append(action_cmd.ljust(20) + desc)

            self.print(
                f"[P{player_id.value}] Available actions:\n" +
                "\n".join(f"{i + 1}) {option}" for i, option in enumerate(options))
            )

        elif cmd in ('d', 'dustpile'):
            self.print(
                f"Dustpile:\n" +
                "\n".join(("  " + self._entity_to_str(c)) for c in self.game.player(player_id).dustpile.cards)
            )

        elif cmd in ('p', 'play'):
            if len(args) < 1:
                self.print("Usage: play <card_id> [slot]")
                return

            try:
                card_id = int(args[0])
            except ValueError:
                self.print("[warn]Card ID must be a number.[/warn]")
                return

            player = self.game.player(player_id)
            try:
                card = player.hand.get(card_id)
            except StopIteration:
                self.print("[warn]Card not found.[/warn]")
                return

            if isinstance(card, Monster):
                if len(args) < 2:
                    try:
                        slot = player.board.get_empty_slot_index()
                    except StopIteration:
                        self.print("[warn]Board is full.[/warn]")
                        return

                else:
                    try:
                        slot = int(args[1]) - 1
                    except ValueError:
                        self.print("[warn]Slot must be a number from 1 to 4.[/warn]")
                        return

                    if not (0 <= slot <= 3):
                        self.print("[warn]Slot must be a number from 1 to 4.[/warn]")
                        return

                action = PlayMonster(card_id=card.id, board_slot=slot)

            else:
                action = PlaySpell(card_id=card.id)

            response = PlayerActionResponse(request_id=request_id, player_id=player_id, action=action)
            ok, reason = self.runner.provide_input(response)
            if not ok:
                self.print(f"[warn]Rejected: {reason}[/warn]")

        elif cmd in ('a', 'attack'):
            if len(args) < 2:
                self.print("Usage:\n attack <attacker_id> <defender_id>\n attack <attacker_id> op")
                return

            try:
                attacker_id = int(args[0])
            except ValueError:
                self.print("[warn]Attacker ID must be a number.[/warn]")
                return

            if args[1].lower() == 'op':
                defender_id = self.game.player(player_id).opponent.id
            else:
                try:
                    defender_id = int(args[1])
                except ValueError:
                    self.print("[warn]Defender must be a monster ID or \"op\".[/warn]")
                    return

            action = Attack(attacker_id=attacker_id, defender_id=defender_id)
            response = PlayerActionResponse(request_id=request_id, player_id=player_id, action=action)
            ok, reason = self.runner.provide_input(response)
            if not ok:
                self.print(f"[warn]Rejected: {reason}[/warn]")

        elif cmd == 'end':
            resp = PlayerActionResponse(
                request_id=request_id,
                player_id=player_id,
                action=EndTurn(),
            )
            ok, reason = self.runner.provide_input(resp)
            if not ok:
                self.print(f"[warn]Rejected: {reason}[/warn]")

        elif cmd in ('q', 'quit', 'exit'):
            self._should_exit = True

        else:
            self.print("[warn]Unknown command[/warn]")

    # -------------------------
    # Pending request handling
    # -------------------------

    def _log_request(self, req) -> None:
        if isinstance(req, PendingMulliganRequest):
            self.print(f"[P{req.player_id.value}] Mulligan:")
            for i, card_id in enumerate(req.prompt.offered_card_ids):
                self.print(f"  {i + 1}: {self._entity_to_str(self.game.entities[card_id])}")

        elif isinstance(req, PendingPlayerActionRequest):
            self.print(f"[P{req.player_id.value}] Choose an action.")

        elif isinstance(req, PendingChoiceRequest):
            prompt = req.prompt
            assert isinstance(prompt, ChooseEntityPrompt)

            self.print(
                f"[P{req.player_id.value}] Choose a target:\n" +
                "\n".join(f"{i + 1}) {self._entity_to_str(choice)}" for i, choice in enumerate(prompt.options))
            )

    def run(self, controller) -> None:
        last_logged_request_id = None

        with Live(
            self._layout,
            console=self._console,
            screen=True,
            auto_refresh=False,
            vertical_overflow='crop',
        ) as live:
            self._live = live

            while (not self.game.game_over) and (not self._should_exit):
                upd = controller.resolve_until_blocked()

                if upd.pending:
                    viewer_id = upd.pending[0].player_id
                    self._active_player_id = viewer_id
                else:
                    viewer_id = self._active_player_id

                formatter = ActionLogFormatter(
                    LogView(viewer_id=viewer_id),
                )

                if upd.log_records:
                    for line in formatter.format_records(upd.log_records):
                        indent = "  " * line.indent
                        self.print(f"{indent}{line.text}")

                if upd.game_over:
                    viewer_id = self._default_viewer_id()
                    self._active_player_id = viewer_id

                    game_over_text = f"[bold]Game over.[/bold] Winner: Player {self.game.winner_id().value}"
                    self.print(game_over_text)

                    while True:
                        line = self._read_line(
                            ">",
                            context=game_over_text,
                        )
                        self.handle_command(-1, viewer_id, line)

                req = upd.pending[0]
                self._current_request = req

                if req.request_id != last_logged_request_id:
                    last_logged_request_id = req.request_id
                    self._log_request(req)

                self._refresh_live()

                if isinstance(req, PendingMulliganRequest):
                    replace_ids_str = self._read_line(
                        f"P{req.player_id.value}>",
                        context=f"Mulligan: " + ' | '.join([
                            f'{i + 1}: {self._entity_to_str(self.game.entities[card_id])}'
                            for i, card_id in enumerate(req.prompt.offered_card_ids)
                        ]),
                        help_text="Choose cards to mulligan (e.g. '1 3')",
                        history=False,
                    ).strip()

                    try:
                        replace_card_ids = tuple(
                            req.prompt.offered_card_ids[int(i) - 1]
                            for i in replace_ids_str.split()
                        )
                    except (IndexError, ValueError):
                        continue

                    response = MulliganResponse(
                        request_id=req.request_id,
                        player_id=req.player_id,
                        replace_card_ids=replace_card_ids,
                    )
                    ok, reason = self.runner.provide_input(response)
                    if not ok:
                        self.print(f"[warn]Rejected: {reason}[/warn]")

                if isinstance(req, PendingPlayerActionRequest):
                    line = self._read_line(
                        f"P{req.player_id.value}>",
                        context=f"[bold]Choose an action[/bold] · type \"?\" for help",
                    ).strip()
                    self.handle_command(req.request_id, req.player_id, line)

                if isinstance(req, PendingChoiceRequest):
                    prompt = req.prompt
                    assert isinstance(prompt, ChooseEntityPrompt)

                    line = self._read_line(
                        f"P{req.player_id.value}>",
                        context=f"[bold]Choose a target[/bold]",
                        help_text=f"Enter 1-{len(prompt.options)}",
                        history=False,
                    ).strip()

                    try:
                        index = int(line) - 1
                    except ValueError:
                        self.print(f"[warn]Invalid index[/warn]")
                        continue

                    if not 0 <= index < len(prompt.options):
                        self.print(f"[warn]Invalid index[/warn]")
                        continue

                    resp = ChoiceResponse(
                        request_id=req.request_id,
                        player_id=req.player_id,
                        selected_option_ids=(prompt.options[index].id,),
                    )
                    ok, reason = self.runner.provide_input(resp)
                    if not ok:
                        self.print(f"[warn]Rejected: {reason}[/warn]")

                self._current_request = None


def get_random_beginner_deck():
    deck_name = random.choice(tuple(BEGINNER_DECKS.keys()))
    return BEGINNER_DECKS[deck_name]


def deck_from_code(text: str) -> dict:
    text = text.strip()

    if not text:
        raise ValueError("Empty deck code")

    if text.startswith('{'):
        return json.loads(text)

    padded = text + '=' * (-len(text) % 4)

    try:
        return json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("Invalid deck code") from exc


def prompt_deck() -> dict:
    console = Console(theme=CONSOLE_THEME, highlight=False)
    console.print(PROMPT_DECK_TEXT)

    while True:
        text = Prompt.ask(f"P1 deck", default="")

        if text == "":
            return get_random_beginner_deck()

        elif text.lower() in BEGINNER_DECKS:
            return BEGINNER_DECKS[text.lower()]

        try:
            return deck_from_code(text)
        except ValueError as exc:
            console.print(f"[error]Invalid deck:[/error] {exc}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--p1', choices=['human', 'ai'], default='human')
    p.add_argument('--p2', choices=['human', 'ai'], default='ai')
    p.add_argument('--p1-deck')
    p.add_argument('--p2-deck')
    p.add_argument('--non-interactive', action='store_true')
    return p.parse_args()


def main() -> None:
    colorama.just_fix_windows_console()

    args = parse_args()

    decks: dict[PlayerId, dict | None] = {PlayerId.P1: None, PlayerId.P2: None}

    # Check if user provided no CLI arguments
    if len(sys.argv) == 1:
        decks[PlayerId.P1] = prompt_deck()

    else:
        if args.p1_deck:
            decks[PlayerId.P1] = deck_from_code(args.p1_deck)
        if args.p2_deck:
            decks[PlayerId.P2] = deck_from_code(args.p2_deck)

    players = []
    for player_id in (PlayerId.P1, PlayerId.P2):
        deck = decks[player_id]
        if deck is None:
            deck = get_random_beginner_deck()

        players.append(
            Player(
                player_id,
                deck=deck['cardIds'],
                soul_id=deck['soul'],
                artifact_ids=deck['artifactIds'],
            )
        )

    ai_agents = {}
    if args.p1 == 'ai':
        ai_agents[PlayerId.P1] = SimpleAI()
    if args.p2 == 'ai':
        ai_agents[PlayerId.P2] = SimpleAI()

    load()

    game = Game(tuple(players))
    runner = GameRunner(game)
    controller = AIGameController(
        runner=runner,
        agents=ai_agents,
    )

    if args.non_interactive:
        upd = controller.resolve_until_blocked()
        print(f"Game over: {upd.game_over}\nLog record count: {len(upd.log_records)}")
        return

    human_player_ids = {
        player_id for player_id in (PlayerId.P1, PlayerId.P2)
        if player_id not in ai_agents
    }

    try:
        CLIRunner(runner, human_player_ids=human_player_ids).run(controller)
    except KeyboardInterrupt:
        pass
