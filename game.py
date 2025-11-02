from typing import List
import random
from game_types import GameState, PLAYER_COUNT
from log import log as logger

def create_initial_state() -> GameState:
    roles = ["liberal", "liberal", "liberal", "fascist", "hitler"]
    random.shuffle(roles)
    players = []
    for i, r in enumerate(roles):
        team = "liberal" if r == "liberal" else "fascist"
        players.append({"id": i, "role": r, "team": team, "alive": True, "investigated": False})
    deck = ["liberal"] * 6 + ["fascist"] * 11
    random.shuffle(deck)
    start = random.randint(0, PLAYER_COUNT - 1)
    logger("=" * 60)
    logger("SECRET HITLER - 5 PLAYER GAME")
    logger("=" * 60)
    logger("\n[SETUP] Roles assigned (SECRET):")
    for p in players:
        logger(f"  Player {p['id']}: {p['role'].upper()} ({p['team']})")
    logger(f"\n[SETUP] Starting President: Player {start}")
    logger(f"[SETUP] Policy deck created: {deck.count('liberal')} Liberal, {deck.count('fascist')} Fascist\n")
    return GameState(
        players=players,
        liberal_policies=0,
        fascist_policies=0,
        policy_deck=deck,
        discard_pile=[],
        current_president_idx=start,
        nominated_chancellor_idx=None,
        previous_president_idx=None,
        previous_chancellor_idx=None,
        election_tracker=0,
        phase="nominate",
        votes={},
        drawn_policies=[],
        passed_policies=[],
        messages=[f"Game started. Player {start} is the first President."],
        winner=None,
        game_over_reason=None,
    )

def _print_round_summary(state: GameState, note: str = "") -> None:
    """Print a concise spectator-facing summary of the board and deck."""
    lib = state.get("liberal_policies", 0)
    fas = state.get("fascist_policies", 0)
    deck = state.get("policy_deck", [])
    discard = state.get("discard_pile", [])
    deck_lib = deck.count("liberal")
    deck_fas = deck.count("fascist")
    logger(f"[ROUND SUMMARY]{(' ' + note) if note else ''} Board: {lib} Liberal, {fas} Fascist — Deck: {deck_lib}L/{deck_fas}F  Discard: {len(discard)}")

def nomination_node(state: GameState, runtime) -> GameState:
    logger(f"\n--- ROUND: President Player {state['current_president_idx']} ---")
    _print_round_summary(state)
    agents = runtime.context.get("agents") if getattr(runtime, "context", None) else runtime.get("context", {})
    president = agents[state["current_president_idx"]]
    chancellor_id = president.nominate(state)
    msg = f"Player {state['current_president_idx']} nominated Player {chancellor_id} as Chancellor."
    return {"nominated_chancellor_idx": chancellor_id, "phase": "vote", "messages": state["messages"] + [msg]}

def voting_node(state: GameState, runtime) -> GameState:
    logger(f"\n[VOTING] On government: President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}")
    votes = {}
    agents = runtime.context.get("agents") if getattr(runtime, "context", None) else runtime.get("context", {})
    for agent in agents:
        if state["players"][agent.agent_id]["alive"]:
            vote = agent.vote(state)
            votes[str(agent.agent_id)] = vote
            role = state["players"][agent.agent_id].get("role", "unknown")
            role_display = role.capitalize()
            logger(f"  Player {agent.agent_id} ({role_display}): {'JA' if vote else 'NEIN'}")
    ja_votes = sum(1 for v in votes.values() if v)
    total_votes = len(votes)
    elected = ja_votes > total_votes / 2
    if elected:
        msg = f"Government ELECTED ({ja_votes}/{total_votes} Ja). President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}."
        logger(f"\n[RESULT] {msg}")
        logger(f"[ROUND SUMMARY] Board: {state.get('liberal_policies',0)} Liberal, {state.get('fascist_policies',0)} Fascist — Deck: {state.get('policy_deck',[]).count('liberal')}L/{state.get('policy_deck',[]).count('fascist')}F  Discard: {len(state.get('discard_pile',[]))}")
        if state["fascist_policies"] >= 3:
            chancellor = state["players"][state["nominated_chancellor_idx"]]
            if chancellor["role"] == "hitler":
                return {
                    "votes": votes,
                    "phase": "game_over",
                    "winner": "fascists",
                    "game_over_reason": "Hitler elected as Chancellor after 3 fascist policies!",
                    "messages": state["messages"] + [msg, "GAME OVER: Hitler elected in Hitler Zone!"],
                }
        return {"votes": votes, "phase": "legislate_president", "election_tracker": 0, "messages": state["messages"] + [msg]}
    else:
        msg = f"Government REJECTED ({ja_votes}/{total_votes} Ja). Election tracker: {state['election_tracker'] + 1}/3"
        logger(f"\n[RESULT] {msg}")
        new_tracker = state["election_tracker"] + 1
        if new_tracker >= 3:
            policy = state["policy_deck"][0]
            new_deck = state["policy_deck"][1:]
            chaos_msg = f"CHAOS! Top policy enacted: {policy.upper()}"
            logger(f"\n[CHAOS] {chaos_msg}")
            new_liberal = state["liberal_policies"] + (1 if policy == "liberal" else 0)
            new_fascist = state["fascist_policies"] + (1 if policy == "fascist" else 0)
            if len(new_deck) < 3:
                new_deck = new_deck + state["discard_pile"]
                random.shuffle(new_deck)
                new_discard = []
            else:
                new_discard = state["discard_pile"]
            logger(f"[ROUND SUMMARY] Board: {new_liberal} Liberal, {new_fascist} Fascist — Deck: {new_deck.count('liberal')}L/{new_deck.count('fascist')}F  Discard: {len(new_discard)}")
            next_pres = (state["current_president_idx"] + 1) % PLAYER_COUNT
            return {
                "votes": votes,
                "phase": "check_win",
                "election_tracker": 0,
                "liberal_policies": new_liberal,
                "fascist_policies": new_fascist,
                "policy_deck": new_deck,
                "discard_pile": new_discard,
                "current_president_idx": next_pres,
                "nominated_chancellor_idx": None,
                "messages": state["messages"] + [msg, chaos_msg],
            }
        else:
            next_pres = (state["current_president_idx"] + 1) % PLAYER_COUNT
            logger(f"[ROUND SUMMARY] Board: {state.get('liberal_policies',0)} Liberal, {state.get('fascist_policies',0)} Fascist — Deck: {state.get('policy_deck',[]).count('liberal')}L/{state.get('policy_deck',[]).count('fascist')}F  Discard: {len(state.get('discard_pile',[]))}")
            return {
                "votes": votes,
                "phase": "nominate",
                "election_tracker": new_tracker,
                "current_president_idx": next_pres,
                "nominated_chancellor_idx": None,
                "messages": state["messages"] + [msg],
            }

def president_legislative_node(state: GameState, runtime) -> GameState:
    logger(f"\n[LEGISLATIVE SESSION] President draws 3 policies...")
    drawn = state["policy_deck"][:3]
    remaining_deck = state["policy_deck"][3:]
    if len(remaining_deck) < 3:
        remaining_deck = remaining_deck + state["discard_pile"]
        random.shuffle(remaining_deck)
        new_discard = []
    else:
        new_discard = state["discard_pile"]
    logger(f"  (President sees: {drawn.count('liberal')} Liberal, {drawn.count('fascist')} Fascist)")
    interim_state = {**state, "policy_deck": remaining_deck, "discard_pile": new_discard}
    _print_round_summary(interim_state, note="(after President draw)")
    agents = runtime.context.get("agents") if getattr(runtime, "context", None) else runtime.get("context", {})
    president = agents[state["current_president_idx"]]
    passed = president.president_legislate({**state, "drawn_policies": drawn})
    rem = drawn.copy()
    for p in passed:
        if p in rem:
            rem.remove(p)
    discarded = rem[0] if rem else None
    updated_discard = new_discard + ([discarded] if discarded else [])
    logger(f"[PRESIDENT ACTION] Passed to Chancellor: {passed.count('liberal')} Liberal, {passed.count('fascist')} Fascist")
    _print_round_summary({**state, "policy_deck": remaining_deck, "discard_pile": updated_discard}, note="(after President action)")
    return {
        "drawn_policies": drawn,
        "passed_policies": passed,
        "policy_deck": remaining_deck,
        "discard_pile": updated_discard,
        "phase": "legislate_chancellor",
        "messages": state["messages"] + ["President drew 3 policies and passed 2 to Chancellor."],
    }

def chancellor_legislative_node(state: GameState, runtime) -> GameState:
    logger(f"\n[LEGISLATIVE SESSION] Chancellor receives 2 policies...")
    passed = state["passed_policies"]
    logger(f"  (Chancellor sees: {passed.count('liberal')} Liberal, {passed.count('fascist')} Fascist)")
    agents = runtime.context.get("agents") if getattr(runtime, "context", None) else runtime.get("context", {})
    chancellor = agents[state["nominated_chancellor_idx"]]
    enacted = chancellor.chancellor_legislate({**state, "passed_policies": passed})
    remaining = passed.copy()
    remaining.remove(enacted)
    discarded = remaining[0] if remaining else None
    logger(f"\n[POLICY ENACTED] {enacted.upper()} policy enacted!")
    new_liberal = state["liberal_policies"] + (1 if enacted == "liberal" else 0)
    new_fascist = state["fascist_policies"] + (1 if enacted == "fascist" else 0)
    msg = f"{enacted.upper()} policy enacted. Board: {new_liberal} Liberal, {new_fascist} Fascist."
    deck_len = len(state.get("policy_deck", []))
    discard_len = len(state.get("discard_pile", [])) + (1 if discarded else 0)
    logger(f"[ROUND SUMMARY] Board: {new_liberal} Liberal, {new_fascist} Fascist — Deck size: {deck_len}  Discard size: {discard_len}")
    return {
        "liberal_policies": new_liberal,
        "fascist_policies": new_fascist,
        "discard_pile": state["discard_pile"] + ([discarded] if discarded else []),
        "previous_president_idx": state["current_president_idx"],
        "previous_chancellor_idx": state["nominated_chancellor_idx"],
        "drawn_policies": [],
        "passed_policies": [],
        "phase": "check_win",
        "messages": state["messages"] + [msg],
    }

def check_win_node(state: GameState) -> GameState:
    if state["liberal_policies"] >= 5:
        return {
            "phase": "game_over",
            "winner": "liberals",
            "game_over_reason": "5 Liberal policies enacted!",
            "messages": state["messages"] + ["GAME OVER: Liberals win with 5 policies!"],
        }
    if state["fascist_policies"] >= 6:
        return {
            "phase": "game_over",
            "winner": "fascists",
            "game_over_reason": "6 Fascist policies enacted!",
            "messages": state["messages"] + ["GAME OVER: Fascists win with 6 policies!"],
        }
    if state["fascist_policies"] == 3 and state.get("previous_president_idx") is not None:
        if state.get("drawn_policies", []) == [] and state.get("passed_policies", []) == []:
            has_uninvestigated = any(not p["investigated"] for p in state["players"] if p["alive"])
            if has_uninvestigated:
                print(f"\n[EXECUTIVE POWER] Investigate Loyalty unlocked!")
                return {"phase": "executive", "messages": state["messages"] + ["Executive power: Investigate Loyalty"]}
    next_pres = (state["current_president_idx"] + 1) % PLAYER_COUNT
    return {"phase": "nominate", "current_president_idx": next_pres, "nominated_chancellor_idx": None, "messages": state["messages"] + [f"Next round: Player {next_pres} is President."]}

def executive_action_node(state: GameState, runtime) -> GameState:
    agents = runtime.context.get("agents") if getattr(runtime, "context", None) else runtime.get("context", {})
    president = agents[state["previous_president_idx"]]
    target = president.investigate_player(state)
    target_player = state["players"][target]
    party = "Fascist" if target_player["team"] == "fascist" else "Liberal"
    logger(f"\n[INVESTIGATE] President {state['previous_president_idx']} investigates Player {target}")
    logger(f"  Result (SECRET to President): Player {target} is {party}")
    players = state["players"].copy()
    players[target] = {**players[target], "investigated": True}
    next_pres = (state["current_president_idx"] + 1) % PLAYER_COUNT
    return {"players": players, "phase": "nominate", "current_president_idx": next_pres, "nominated_chancellor_idx": None, "messages": state["messages"] + [f"President {state['previous_president_idx']} investigated Player {target} (result secret)."]}

def game_over_node(state: GameState) -> GameState:
    logger("\n" + "=" * 60)
    logger("GAME OVER")
    logger("=" * 60)
    logger(f"\nWinner: {state['winner'].upper()}")
    logger(f"Reason: {state['game_over_reason']}")
    logger(f"\nFinal Score: {state['liberal_policies']} Liberal, {state['fascist_policies']} Fascist")
    logger("\n=== ROLE REVEAL ===")
    for p in state["players"]:
        logger(f"Player {p['id']}: {p['role'].upper()} ({p['team']})")
    logger("\n" + "=" * 60)
    return state

def route_phase(state: GameState) -> str:
    return state["phase"]