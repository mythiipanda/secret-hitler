from typing import List, Any, Tuple
from tools import nominate_tool, vote_tool, president_legislate_tool, chancellor_legislate_tool, investigate_tool

class Agent:
    def __init__(self, aid: int, role: str, team: str, model: str | None = None):
        self.agent_id = aid
        self.role = role
        self.team = team
        self.model = model

    def nominate(self, state: dict) -> int:
        eligible = [
            p["id"]
            for p in state["players"]
            if p["alive"]
            and p["id"] != state["current_president_idx"]
            and (state.get("previous_chancellor_idx") is None or p["id"] != state.get("previous_chancellor_idx"))
            and (state.get("previous_president_idx") is None or p["id"] != state.get("previous_president_idx"))
        ]
        cid, _ = nominate_tool(self.agent_id, self.role, eligible, model=self.model)
        if cid not in eligible:
            cid = eligible[0] if eligible else 0
        return cid

    def vote(self, state: dict) -> bool:
        president_idx = state["current_president_idx"]
        nominated = state["nominated_chancellor_idx"]
        v, _ = vote_tool(self.agent_id, self.role, president_idx, nominated, model=self.model)
        return v

    def president_legislate(self, state: dict) -> List[str]:
        drawn = state.get("drawn_policies", [])
        rem, _ = president_legislate_tool(self.agent_id, drawn, model=self.model)
        return rem

    def chancellor_legislate(self, state: dict) -> str:
        passed = state.get("passed_policies", [])
        enact, _ = chancellor_legislate_tool(self.agent_id, passed, model=self.model)
        return enact

    def investigate_player(self, state: dict) -> int:
        eligible = [p["id"] for p in state["players"] if p["alive"] and not p.get("investigated", False)]
        target, _ = investigate_tool(self.agent_id, eligible, model=self.model)
        if target not in eligible:
            target = eligible[0] if eligible else 0
        return target

def initialize_agents(players: List[dict], model: str | None = None) -> List[Agent]:
    return [Agent(p["id"], p["role"], p["team"], model) for p in players]