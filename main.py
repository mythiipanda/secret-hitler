from typing import TypedDict, Literal, Optional
import os
import random
import json
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import PydanticOutputParser

from google import genai

load_dotenv()
random.seed(0)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")
client = genai.Client(api_key=API_KEY)


class GameState(TypedDict):
    players: list[dict]
    liberal_policies: int
    fascist_policies: int
    policy_deck: list[str]
    discard_pile: list[str]
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
    drawn_policies: list[str]
    passed_policies: list[str]
    messages: list[str]
    winner: str | None
    game_over_reason: str | None


# Pydantic models for structured outputs
class NominationOut(BaseModel):
    nominated_chancellor: int = Field(..., description="Player id nominated for Chancellor")
    public_statement: Optional[str] = Field("", description="Public statement to table")


class VoteOut(BaseModel):
    vote: bool = Field(..., description="True for Ja, False for Nein")
    public_statement: Optional[str] = Field("", description="Optional public statement")


class PresidentLegislateOut(BaseModel):
    discard: Literal["liberal", "fascist"] = Field(..., description="Policy to discard")
    public_claim: Optional[str] = Field("", description="Public claim by President")


class ChancellorLegislateOut(BaseModel):
    enact: Literal["liberal", "fascist"] = Field(..., description="Policy to enact")
    public_claim: Optional[str] = Field("", description="Public claim by Chancellor")


class InvestigateOut(BaseModel):
    investigate: int = Field(..., description="Player id to investigate")
    reason: Optional[str] = Field("", description="Reasoning for investigation")


# Parsers
nom_parser = PydanticOutputParser(pydantic_object=NominationOut)
vote_parser = PydanticOutputParser(pydantic_object=VoteOut)
pres_parser = PydanticOutputParser(pydantic_object=PresidentLegislateOut)
chanc_parser = PydanticOutputParser(pydantic_object=ChancellorLegislateOut)
inv_parser = PydanticOutputParser(pydantic_object=InvestigateOut)


class Agent:
    def __init__(self, aid: int, role: str, team: str):
        self.agent_id = aid
        self.role = role
        self.team = team

    def _call_model(self, prompt: str) -> str:
        resp = client.models.generate_content(model=MODEL, contents=prompt)
        return resp.text

    def nominate(self, state: GameState) -> int:
        eligible = [
            p["id"]
            for p in state["players"]
            if p["alive"]
            and p["id"] != state["current_president_idx"]
            and (state["previous_chancellor_idx"] is None or p["id"] != state["previous_chancellor_idx"])
            and (state["previous_president_idx"] is None or p["id"] != state["previous_president_idx"])
        ]
        instructions = nom_parser.get_format_instructions()
        prompt = f"You are Player {self.agent_id} ({self.role}). Eligible: {eligible}.\n{instructions}\nProvide only the JSON conforming to the schema."
        resp_text = self._call_model(prompt)
        parsed = nom_parser.parse(resp_text)
        cid = int(parsed.nominated_chancellor)
        if cid not in eligible:
            cid = random.choice(eligible)
        if parsed.public_statement:
            print(f"[NOMINATION] Player {self.agent_id}: {parsed.public_statement}")
        return cid

    def vote(self, state: GameState) -> bool:
        instructions = vote_parser.get_format_instructions()
        prompt = f"You are Player {self.agent_id} ({self.role}). President {state['current_president_idx']} nominated {state['nominated_chancellor_idx']}.\n{instructions}\nProvide only the JSON."
        resp_text = self._call_model(prompt)
        parsed = vote_parser.parse(resp_text)
        if parsed.public_statement:
            print(f"[VOTE] Player {self.agent_id}: {parsed.public_statement}")
        return bool(parsed.vote)

    def president_legislate(self, state: GameState) -> list[str]:
        drawn = state["drawn_policies"]
        instructions = pres_parser.get_format_instructions()
        prompt = f"You are President {self.agent_id}. You drew {drawn}.\n{instructions}\nProvide only the JSON."
        resp_text = self._call_model(prompt)
        parsed = pres_parser.parse(resp_text)
        discard = parsed.discard
        if discard not in drawn:
            discard = drawn[0]
        rem = drawn.copy()
        rem.remove(discard)
        if parsed.public_claim:
            print(f"[PRESIDENT] Player {self.agent_id}: {parsed.public_claim}")
        return rem

    def chancellor_legislate(self, state: GameState) -> str:
        passed = state["passed_policies"]
        instructions = chanc_parser.get_format_instructions()
        prompt = f"You are Chancellor {self.agent_id}. You received {passed}.\n{instructions}\nProvide only the JSON."
        resp_text = self._call_model(prompt)
        parsed = chanc_parser.parse(resp_text)
        enact = parsed.enact
        if enact not in passed:
            enact = random.choice(passed)
        if parsed.public_claim:
            print(f"[CHANCELLOR] Player {self.agent_id}: {parsed.public_claim}")
        return enact

    def investigate_player(self, state: GameState) -> int:
        eligible = [p["id"] for p in state["players"] if p["alive"] and not p["investigated"]]
        instructions = inv_parser.get_format_instructions()
        prompt = f"You are President {self.agent_id}. Eligible to investigate: {eligible}.\n{instructions}\nProvide only the JSON."
        resp_text = self._call_model(prompt)
        parsed = inv_parser.parse(resp_text)
        target = int(parsed.investigate)
        if target not in eligible:
            target = eligible[0]
        return target


def create_initial_state() -> GameState:
    roles = ["liberal", "liberal", "liberal", "fascist", "hitler"]
    random.shuffle(roles)
    players = []
    for i, r in enumerate(roles):
        team = "liberal" if r == "liberal" else "fascist"
        players.append({"id": i, "role": r, "team": team, "alive": True, "investigated": False})
    deck = ["liberal"] * 6 + ["fascist"] * 11
    random.shuffle(deck)
    start = random.randint(0, 4)
    print("=" * 60)
    print("SECRET HITLER - 5 PLAYER GAME")
    print("=" * 60)
    print("\n[SETUP] Roles assigned (SECRET):")
    for p in players:
        print(f"  Player {p['id']}: {p['role'].upper()} ({p['team']})")
    print(f"\n[SETUP] Starting President: Player {start}")
    print(f"[SETUP] Policy deck created: {deck.count('liberal')} Liberal, {deck.count('fascist')} Fascist\n")
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


def initialize_agents(state: GameState) -> list[Agent]:
    return [Agent(p["id"], p["role"], p["team"]) for p in state["players"]]


AGENTS: list[Agent] = []


def nomination_node(state: GameState) -> GameState:
    print(f"\n--- ROUND: President Player {state['current_president_idx']} ---")
    president = AGENTS[state["current_president_idx"]]
    chancellor_id = president.nominate(state)
    msg = f"Player {state['current_president_idx']} nominated Player {chancellor_id} as Chancellor."
    return {"nominated_chancellor_idx": chancellor_id, "phase": "vote", "messages": state["messages"] + [msg]}


def voting_node(state: GameState) -> GameState:
    print(f"\n[VOTING] On government: President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}")
    votes = {}
    for agent in AGENTS:
        if state["players"][agent.agent_id]["alive"]:
            vote = agent.vote(state)
            votes[str(agent.agent_id)] = vote
            print(f"  Player {agent.agent_id}: {'JA' if vote else 'NEIN'}")
    ja_votes = sum(1 for v in votes.values() if v)
    total_votes = len(votes)
    elected = ja_votes > total_votes / 2
    if elected:
        msg = f"Government ELECTED ({ja_votes}/{total_votes} Ja). President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}."
        print(f"\n[RESULT] {msg}")
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
        print(f"\n[RESULT] {msg}")
        new_tracker = state["election_tracker"] + 1
        if new_tracker >= 3:
            policy = state["policy_deck"][0]
            new_deck = state["policy_deck"][1:]
            chaos_msg = f"CHAOS! Top policy enacted: {policy.upper()}"
            print(f"\n[CHAOS] {chaos_msg}")
            new_liberal = state["liberal_policies"] + (1 if policy == "liberal" else 0)
            new_fascist = state["fascist_policies"] + (1 if policy == "fascist" else 0)
            if len(new_deck) < 3:
                new_deck = new_deck + state["discard_pile"]
                random.shuffle(new_deck)
                new_discard = []
            else:
                new_discard = state["discard_pile"]
            next_pres = (state["current_president_idx"] + 1) % 5
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
            next_pres = (state["current_president_idx"] + 1) % 5
            return {
                "votes": votes,
                "phase": "nominate",
                "election_tracker": new_tracker,
                "current_president_idx": next_pres,
                "nominated_chancellor_idx": None,
                "messages": state["messages"] + [msg],
            }


def president_legislative_node(state: GameState) -> GameState:
    print(f"\n[LEGISLATIVE SESSION] President draws 3 policies...")
    drawn = state["policy_deck"][:3]
    remaining_deck = state["policy_deck"][3:]
    if len(remaining_deck) < 3:
        remaining_deck = remaining_deck + state["discard_pile"]
        random.shuffle(remaining_deck)
        new_discard = []
    else:
        new_discard = state["discard_pile"]
    print(f"  (President sees: {drawn.count('liberal')} Liberal, {drawn.count('fascist')} Fascist)")
    president = AGENTS[state["current_president_idx"]]
    passed = president.president_legislate({**state, "drawn_policies": drawn})
    rem = drawn.copy()
    for p in passed:
        if p in rem:
            rem.remove(p)
    discarded = rem[0] if rem else None
    return {
        "drawn_policies": drawn,
        "passed_policies": passed,
        "policy_deck": remaining_deck,
        "discard_pile": new_discard + ([discarded] if discarded else []),
        "phase": "legislate_chancellor",
        "messages": state["messages"] + ["President drew 3 policies and passed 2 to Chancellor."],
    }


def chancellor_legislative_node(state: GameState) -> GameState:
    print(f"\n[LEGISLATIVE SESSION] Chancellor receives 2 policies...")
    passed = state["passed_policies"]
    print(f"  (Chancellor sees: {passed.count('liberal')} Liberal, {passed.count('fascist')} Fascist)")
    chancellor = AGENTS[state["nominated_chancellor_idx"]]
    enacted = chancellor.chancellor_legislate({**state, "passed_policies": passed})
    remaining = passed.copy()
    remaining.remove(enacted)
    discarded = remaining[0] if remaining else None
    print(f"\n[POLICY ENACTED] {enacted.upper()} policy enacted!")
    new_liberal = state["liberal_policies"] + (1 if enacted == "liberal" else 0)
    new_fascist = state["fascist_policies"] + (1 if enacted == "fascist" else 0)
    msg = f"{enacted.upper()} policy enacted. Board: {new_liberal} Liberal, {new_fascist} Fascist."
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
    if state["fascist_policies"] == 3 and state["previous_president_idx"] is not None:
        if state["drawn_policies"] == [] and state["passed_policies"] == []:
            has_uninvestigated = any(not p["investigated"] for p in state["players"] if p["alive"])
            if has_uninvestigated:
                print(f"\n[EXECUTIVE POWER] Investigate Loyalty unlocked!")
                return {"phase": "executive", "messages": state["messages"] + ["Executive power: Investigate Loyalty"]}
    next_pres = (state["current_president_idx"] + 1) % 5
    return {"phase": "nominate", "current_president_idx": next_pres, "nominated_chancellor_idx": None, "messages": state["messages"] + [f"Next round: Player {next_pres} is President."]}


def executive_action_node(state: GameState) -> GameState:
    president = AGENTS[state["previous_president_idx"]]
    target = president.investigate_player(state)
    target_player = state["players"][target]
    party = "Fascist" if target_player["team"] == "fascist" else "Liberal"
    print(f"\n[INVESTIGATE] President {state['previous_president_idx']} investigates Player {target}")
    print(f"  Result (SECRET to President): Player {target} is {party}")
    players = state["players"].copy()
    players[target] = {**players[target], "investigated": True}
    next_pres = (state["current_president_idx"] + 1) % 5
    return {"players": players, "phase": "nominate", "current_president_idx": next_pres, "nominated_chancellor_idx": None, "messages": state["messages"] + [f"President {state['previous_president_idx']} investigated Player {target} (result secret)."]}


def game_over_node(state: GameState) -> GameState:
    print("\n" + "=" * 60)
    print("GAME OVER")
    print("=" * 60)
    print(f"\nWinner: {state['winner'].upper()}")
    print(f"Reason: {state['game_over_reason']}")
    print(f"\nFinal Score: {state['liberal_policies']} Liberal, {state['fascist_policies']} Fascist")
    print("\n=== ROLE REVEAL ===")
    for p in state["players"]:
        print(f"Player {p['id']}: {p['role'].upper()} ({p['team']})")
    print("\n" + "=" * 60)
    return state


def route_phase(state: GameState) -> str:
    return state["phase"]


def build_workflow() -> StateGraph:
    g = StateGraph(GameState)
    g.add_node("nominate", nomination_node)
    g.add_node("vote", voting_node)
    g.add_node("legislate_president", president_legislative_node)
    g.add_node("legislate_chancellor", chancellor_legislative_node)
    g.add_node("check_win", check_win_node)
    g.add_node("executive", executive_action_node)
    g.add_node("game_over", game_over_node)
    g.set_entry_point("nominate")
    g.add_edge("nominate", "vote")
    g.add_conditional_edges(
        "vote",
        route_phase,
        {"nominate": "nominate", "legislate_president": "legislate_president", "check_win": "check_win", "game_over": "game_over"},
    )
    g.add_edge("legislate_president", "legislate_chancellor")
    g.add_edge("legislate_chancellor", "check_win")
    g.add_conditional_edges("check_win", route_phase, {"nominate": "nominate", "executive": "executive", "game_over": "game_over"})
    g.add_edge("executive", "nominate")
    g.add_edge("game_over", END)
    return g


def main():
    global AGENTS
    state = create_initial_state()
    AGENTS = initialize_agents(state)
    app = build_workflow().compile()
    print("\n" + "=" * 60)
    print("STARTING GAME")
    print("=" * 60)
    finished = False
    for output in app.stream(state, stream_mode="updates", config={"recursion_limit": 1000}):
        for node_name, node_state in output.items():
            state = node_state
            if len(state.get("messages", [])) > 500:
                print("\n[ERROR] Game exceeded 500 actions, terminating.")
                finished = True
            if node_state.get("phase") == "game_over" or node_state.get("winner") is not None:
                finished = True
        if finished:
            break
    print("\n" + "=" * 60)
    print("GAME SIMULATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()