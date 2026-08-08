import json
from typing import Any, TYPE_CHECKING

from deltacards.content.registry import CONTENT
from deltacards.model.artifacts import (
    ARTIFACTS,
    Artifact,
    ArtifactRarity,
    QuestArtifact,
)
from deltacards.model.cards import Card, Monster
from deltacards.model.enchantments import Enchantment
from deltacards.model.enums import (
    CardKeyword,
    CardZone,
    PlayerId,
)
from deltacards.model.player import Player
from deltacards.model.slots import BoardSlot
from deltacards.model.snapshots import (
    ArtifactSnapshot,
    BoardSlotSnapshot,
    CardSnapshot,
    EnchantmentSnapshot,
    MonsterSnapshot,
    PlayerSnapshot,
    SoulSnapshot,
)
from deltacards.model.souls import SOULS, Soul

from .config import (
    AssetConfig,
    DEFAULT_PLAYER_LEVEL,
)

if TYPE_CHECKING:
    from deltacards.engine.game import Game


def json_text(value: Any) -> str:
    return json.dumps(
        value,
        separators=(',', ':'),
        ensure_ascii=False,
    )


def wire_slot_id(controller_id: PlayerId, pos: int) -> int:
    """
    Map stable engine slots to the IDs hardcoded by the frontend.

    P1 occupies 100004..100007.
    P2 occupies 100000..100003.
    """
    if not 0 <= pos <= 3:
        raise ValueError(f"Invalid Board Slot position: {pos}")

    base = 100004 if controller_id is PlayerId.P1 else 100000
    return base + pos


def decode_wire_slot_id(slot_id: int) -> tuple[PlayerId, int] | None:
    if 100000 <= slot_id <= 100003:
        return PlayerId.P2, slot_id - 100000

    if 100004 <= slot_id <= 100007:
        return PlayerId.P1, slot_id - 100004

    return None


class ViewSerializer:
    def __init__(
        self,
        *,
        game: 'Game',
        assets: AssetConfig,
        usernames: dict[PlayerId, str],
    ):
        self.game = game
        self.assets = assets
        self.usernames = usernames

    # --------------------
    # Visibility
    # --------------------

    @staticmethod
    def card_is_visible(
        card: Card | CardSnapshot,
        viewer_id: PlayerId,
    ) -> bool:
        if card.zone in (
            CardZone.BOARD,
            CardZone.DUSTPILE,
            CardZone.ERASED,
            CardZone.STACK,
        ):
            return True

        if card.zone is CardZone.HAND:
            return card.controller_id is viewer_id

        return False

    # --------------------
    # Card views
    # --------------------

    def _creator_info(
        self,
        card: Card | CardSnapshot,
    ) -> dict[str, Any] | None:
        identity = card.creator_base_identity

        if identity is None and card.creator_id is not None:
            try:
                creator = self.game.entity(card.creator_id)
            except KeyError:
                creator = None

            if isinstance(
                creator,
                (
                    Card,
                    Artifact,
                    Soul,
                    Enchantment,
                ),
            ):
                identity = creator.base_identity

        if identity is None:
            return None

        creator_kind, creator_value = identity

        if creator_kind == 'card':
            return {
                'typeCreator': 0,
                'id': creator_value,
            }

        if creator_kind == 'artifact':
            return {
                'typeCreator': 1,
                'id': creator_value,
            }

        if creator_kind == 'soul':
            return {
                'typeCreator': 2,
                'id': 0,
                'name': SOULS[creator_value].__name__,
            }

        if creator_kind == 'enchantment':
            return {
                'typeCreator': 3,
                'id': 0,
                'name': creator_value,
            }

        return None

    def _caught_card_view(
        self,
        card: Card | CardSnapshot,
    ) -> dict[str, Any] | None:
        caught = card.caught_card
        if caught is None:
            return None

        return {
            'fixedId': caught.template_id,
            'owner': {
                'username': self.usernames[caught.controller_id],
                'level': DEFAULT_PLAYER_LEVEL,
            },
        }

    @staticmethod
    def _status_views(
        card: Card | CardSnapshot,
    ) -> list[dict[str, Any]]:
        def _pascal_case(s: str) -> str:
            if s == 'KR':  # TODO
                return s

            return ''.join(word.capitalize() for word in s.split('_'))

        statuses = []

        for keyword in CardKeyword:
            if keyword is CardKeyword.NONE:
                continue

            if keyword in card.keywords:
                statuses.append({
                    'name': _pascal_case(keyword.name),
                    'counter': 0,
                    'displayCounter': False,
                })

        for status_id, counter in card.statuses.items():
            statuses.append({
                'name': _pascal_case(status_id.value),
                'counter': counter,
                'displayCounter': True,
            })

        return statuses

    def card_view(
        self,
        card: Card | CardSnapshot,
    ) -> dict[str, Any]:
        template = card.template

        frontend_image = CONTENT.image(
            'card',
            template.id,
            default_name=template.image,
        )

        result = {
            'id': card.id,
            'fixedId': template.id,
            'name': template.name,

            'image': frontend_image.name,
            'baseImage': frontend_image.name,
            'extension': template.expansion.name,
            'rarity': template.rarity.name,

            'typeCard': card.type.value,
            'typeSkin': 0,
            'shiny': False,

            'cost': card.cost,
            'originalCost': card.base.cost,

            'ownerId': card.controller_id,

            'tribes': [tribe.name for tribe in template.tribes],
            'statuses': self._status_views(card),

            'frameSkinName': self.assets.frame_skin_name,
        }

        if isinstance(card, (Monster, MonsterSnapshot)):
            result.update({
                'attack': card.attack,
                'originalAttack': card.base.attack,
                'hp': card.hp,
                'maxHp': card.max_hp,
                'originalHp': card.base.hp,
            })

            if card.zone is CardZone.BOARD:
                result['boardPosition'] = card.pos

        creator_info = self._creator_info(card)
        if creator_info is not None:
            result['creatorInfo'] = creator_info

        caught_card = self._caught_card_view(card)
        if caught_card is not None:
            result['caughtMonster'] = caught_card

        if template.soul_id is not None:
            result['soul'] = {
                'name': template.soul_id.upper(),
            }

        if frontend_image.url is not None:
            result['imageUrl'] = frontend_image.url
            result['baseImageUrl'] = frontend_image.url

        return result

    # --------------------
    # Other entity views
    # --------------------

    @staticmethod
    def soul_view(
        soul: Soul | SoulSnapshot,
    ) -> dict[str, Any]:
        frontend_image = CONTENT.image(
            'soul',
            soul.definition_id,
            default_name=soul.name,
        )

        return {
            'name': frontend_image.name,
        }

    @staticmethod
    def artifact_view(
        artifact: Artifact | ArtifactSnapshot,
    ) -> dict[str, Any]:
        definition_id = artifact.definition_id
        artifact_type = ARTIFACTS[definition_id]
        is_quest = issubclass(artifact_type, QuestArtifact)

        artifact_images = CONTENT.artifact_images(
            definition_id,
            default_name=artifact.name,
        )
        frontend_image = artifact_images.image

        result = {
            'id': artifact.definition_id,
            'name': artifact.name,
            'image': frontend_image.name,
            'legendary': artifact_type.rarity is ArtifactRarity.LEGENDARY,
            'artifactType': 1 if is_quest else 0,
            'custom': 0 if is_quest else artifact.counter,
            'disabled': not artifact.active,
        }

        if is_quest:
            goal = artifact_type.quest_goal
            if goal is None:
                raise ValueError(
                    f"Quest Artifact {artifact.name!r} has no goal"
                )

            result['progress'] = artifact.counter
            result['goal'] = goal
            result['overlayUrl'] = artifact_images.overlay_url

        if frontend_image.url is not None:
            result['imageUrl'] = frontend_image.url

        return result

    def enchantment_view(
        self,
        enchantment: Enchantment | EnchantmentSnapshot,
    ) -> dict[str, Any]:
        definition_id = enchantment.definition_id
        frontend_name = CONTENT.frontend_name(
            'enchantment',
            definition_id,
            default_name=enchantment.name,
        )

        if CONTENT.is_custom('enchantment', definition_id):
            frontend_images = CONTENT.enchantment_images(
                definition_id,
                default_name=enchantment.name,
            )
            asset_name = frontend_images.asset_name

        else:
            frontend_images = None
            asset_name = CONTENT.image(
                'enchantment',
                definition_id,
                default_name=enchantment.name,
            ).name

        result = {
            'name': frontend_name,
            'assetName': asset_name,
            'custom': enchantment.counter,
        }

        if frontend_images is not None:
            result.update({
                'backgroundUrl': frontend_images.background_url,
                'overlayUrl': frontend_images.overlay_url,
                'logUrl': frontend_images.log_url,
            })

        return result

    def slot_view(
        self,
        slot: BoardSlot,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            'id': wire_slot_id(slot.controller_id, slot.pos),
        }

        enchantment = self.game.enchantment_on_slot(slot)
        if enchantment is not None:
            result['enchant'] = self.enchantment_view(enchantment)

        return result

    def slot_snapshot_view(
        self,
        slot: BoardSlotSnapshot,
        enchantment: EnchantmentSnapshot | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            'id': wire_slot_id(slot.controller_id, slot.pos),
        }

        if enchantment is not None:
            result['enchant'] = self.enchantment_view(enchantment)

        return result

    # --------------------
    # Player views
    # --------------------

    def connection_player_view(
        self,
        player: Player,
    ) -> dict[str, Any]:
        return {
            'id': player.id.value,
            'username': self.usernames[player.id],
            'side': 0 if player.id is PlayerId.P1 else 1,
            'hp': player.hp,
            'maxHp': player.max_hp,
            'soul': self.soul_view(player.soul),
            'contributor': False,
            'level': DEFAULT_PLAYER_LEVEL,
        }

    def avatar_view(self) -> dict[str, Any]:
        return {
            'image': self.assets.avatar_image,
            'rarity': self.assets.avatar_rarity,
        }

    def profile_skin_view(self) -> dict[str, Any]:
        return {
            'name': self.assets.profile_skin_name,
            'image': self.assets.profile_skin_image,
        }

    def emote_view(self) -> dict[str, Any]:
        return {
            'id': self.assets.default_emote_id,
            'image': self.assets.default_emote_image,
        }

    def battle_player_view(
        self,
        player: Player | PlayerSnapshot,
    ) -> dict[str, Any]:
        player_obj = self.game.player(player.id)

        return {
            'id': player.id.value,
            'username': self.usernames[player.id],
            'hp': player.hp,
            'level': DEFAULT_PLAYER_LEVEL,
            'maxHp': player.max_hp,
            'avatar': self.avatar_view(),
            'soul': self.soul_view(player_obj.soul),
        }

    # --------------------
    # Complete state views
    # --------------------

    def hand_view(
        self,
        player: Player,
    ) -> list[dict[str, Any]]:
        return [
            self.card_view(card)
            for card in player.hand.cards
        ]

    def board_view(self) -> list[dict[str, Any]]:
        return [
            self.card_view(monster)
            for player_id in (PlayerId.P1, PlayerId.P2)
            for monster in self.game.player(player_id).board.cards
        ]

    def slots_view(self) -> list[dict[str, Any]]:
        return [
            self.slot_view(slot)
            for player_id in (PlayerId.P1, PlayerId.P2)
            for slot in self.game.player(player_id).board_slots
        ]

    def dustpile_view(self) -> list[dict[str, Any]]:
        return [
            self.card_view(card)
            for player_id in (PlayerId.P1, PlayerId.P2)
            for card in self.game.player(player_id).dustpile.cards
        ]

    def hands_size_view(self) -> dict[int, int]:
        return {
            player_id.value: len(self.game.player(player_id).hand)
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

    def decks_size_view(self) -> dict[int, int]:
        return {
            player_id.value: len(self.game.player(player_id).deck)
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

    def golds_view(self) -> dict[int, int]:
        return {
            player_id.value: self.game.player(player_id).gold
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

    def golds_next_turn_view(self) -> dict[int, int]:
        return {
            player_id.value: self.game.player(player_id).gold_gain(
                self.game.player(player_id).turn + 1
            )
            for player_id in (PlayerId.P1, PlayerId.P2)
        }

    def artifacts_map_view(self) -> dict[int, list[dict[str, Any]]]:
        return {
            player_id.value: [
                self.artifact_view(artifact)
                for artifact in self.game.player(player_id).artifacts
            ]
            for player_id in (PlayerId.P1, PlayerId.P2)
        }
