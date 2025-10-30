from typing import TypedDict, Literal, List, Any

PLAYER_COUNT = 5

class GameState(TypedDict, total=False):
    players: List[dict]
    liberal_policies: int
    fascist_policies: int
    policy_deck: List[str]
    discard_pile: List[str]
    current_president_idx: int
    nominated_chancellor_idx: int | None
    previous_president_idx: int | None
    previous_chancellor_idx: int | None
    election_tracker: int
    phase: Literal[
        "nominate",
        "vote",
        "legislate_president",
        "legislate_chancellor",
        "executive",
        "check_win",
        "game_over",
    ]
    votes: dict
    drawn_policies: List[str]
    passed_policies: List[str]
    messages: List[str]
    winner: str | None
    game_over_reason: str | None
    agents: List[Any]