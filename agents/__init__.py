from typing import List, Any, Optional
from tools import nominate_tool, vote_tool, president_legislate_tool, chancellor_legislate_tool, investigate_tool
from log import log as logger

class Agent:
    def __init__(self, aid: int, role: str, team: str, model: Optional[str] = None, llm_client: Optional[Any] = None):
        """
        Agent is a lightweight wrapper around decision functions.
        LLM/tool clients are provided via runtime/context or explicit llm_client injection.
        """
        self.agent_id = aid
        self.role = role
        self.team = team
        self.model = model
        self.llm = llm_client

    def nominate(self, state: dict) -> int:
        eligible = [
            p["id"]
            for p in state["players"]
            if p["alive"]
            and p["id"] != state["current_president_idx"]
            and (state.get("previous_chancellor_idx") is None or p["id"] != state.get("previous_chancellor_idx"))
            and (state.get("previous_president_idx") is None or p["id"] != state.get("previous_president_idx"))
        ]
        cid, public, private = nominate_tool(self.agent_id, self.role, state, model=self.model, llm_client=self.llm)
        if cid not in eligible:
            fallback = eligible[0] if eligible else 0
            logger(f"[AGENT WARNING] Agent {self.agent_id}: LLM nominated invalid player {cid}; falling back to {fallback}.")
            cid = fallback
        return cid

    def vote(self, state: dict) -> bool:
        v, public, private = vote_tool(self.agent_id, self.role, state, model=self.model, llm_client=self.llm)
        return v

    def president_legislate(self, state: dict) -> List[str]:
        rem, public, private = president_legislate_tool(self.agent_id, state, model=self.model, llm_client=self.llm)
        # Validate returned policies are subset of drawn policies
        drawn = state.get("drawn_policies", [])
        if any(r not in drawn for r in rem):
            logger(f"[AGENT WARNING] Agent {self.agent_id}: President returned policies {rem} not subset of drawn {drawn}. Adjusting to intersection.")
            rem = [p for p in rem if p in drawn]
            if not rem:
                # fallback: pass first two drawn (or drawn itself)
                rem = drawn[:2]
                logger(f"[AGENT WARNING] Agent {self.agent_id}: Adjusted passed policies to {rem}.")
        return rem

    def chancellor_legislate(self, state: dict) -> str:
        enact, public, private = chancellor_legislate_tool(self.agent_id, state, model=self.model, llm_client=self.llm)
        passed = state.get("passed_policies", [])
        if enact not in passed:
            fallback = passed[0] if passed else enact
            logger(f"[AGENT WARNING] Agent {self.agent_id}: Chancellor chose invalid policy {enact}; falling back to {fallback}.")
            enact = fallback
        return enact

    def investigate_player(self, state: dict) -> int:
        eligible = [p["id"] for p in state["players"] if p["alive"] and not p.get("investigated", False)]
        target, public, private = investigate_tool(self.agent_id, state, model=self.model, llm_client=self.llm)
        if target not in eligible:
            fallback = eligible[0] if eligible else 0
            logger(f"[AGENT WARNING] Agent {self.agent_id}: Investigation target {target} not eligible; falling back to {fallback}.")
            target = fallback
        return target

def initialize_agents(players: List[dict], model: Optional[str] = None, llm_client: Optional[Any] = None) -> List[Agent]:
    """Create runtime Agent objects. Provide shared llm_client via injection if available."""
    return [Agent(p["id"], p["role"], p["team"], model, llm_client=llm_client) for p in players]