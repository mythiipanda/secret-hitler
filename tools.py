from typing import List, Optional, Tuple, Any
import time
import random
from parsers import NominationOut, VoteOut, PresidentLegislateOut, ChancellorLegislateOut, InvestigateOut
from prompts import LIBERAL_PROMPT_TEMPLATE, FASCIST_PROMPT_TEMPLATE, RULES_SUMMARY
from log import log as logger

RECENT_HISTORY_LINES = 6

def _players_list(state: dict, requester_id: int) -> str:
    """
    Return a players list string appropriate for the requesting agent.
    - Always show "Player N (role)" for the requester themself.
    - Liberals see only player ids.
    - Fascists see other fascists; in small games (<=6) fascists also see Hitler.
    - Hitler in 5-player games sees fascist(s); in 6-player games Hitler sees only themself.
    """
    players = state.get("players", [])
    num_players = len(players)
    # find requester role
    requester = next((p for p in players if p["id"] == requester_id), None)
    requester_role = requester.get("role") if requester else None

    reveal_hitler_to_fascists = num_players <= 6  # in 5 and 6 player games fascists know Hitler
    parts = []
    for p in players:
        pid = p["id"]
        prot = p.get("role")
        if pid == requester_id:
            parts.append(f"Player {pid} ({prot})")
            continue
        # if requester is fascist, reveal other fascists; reveal Hitler for small games
        if requester_role == "fascist":
            if prot == "fascist" or (prot == "hitler" and reveal_hitler_to_fascists):
                parts.append(f"Player {pid} ({prot})")
            else:
                parts.append(f"Player {pid}")
            continue
        # if requester is hitler
        if requester_role == "hitler":
            # in 5-player game Hitler knows fascists; in 6+ they do not
            if num_players == 5 and prot == "fascist":
                parts.append(f"Player {pid} ({prot})")
            else:
                parts.append(f"Player {pid}")
            continue
        # default (liberals): never reveal roles
        parts.append(f"Player {pid}")
    return ", ".join(parts)

def _recent_history(state: dict) -> str:
    msgs = state.get("messages", [])[-RECENT_HISTORY_LINES:]
    return "\n".join(reversed(msgs)) if msgs else "No history yet."

def _state_summary(state: dict) -> dict:
    return {
        "liberal_policies": state.get("liberal_policies", 0),
        "fascist_policies": state.get("fascist_policies", 0),
        "deck_size": len(state.get("policy_deck", [])),
        "discard_size": len(state.get("discard_pile", [])),
    }

def nominate_tool(agent_id: int, role: str, state: dict, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Tuple[int, str, str]:
    ss = _state_summary(state)
    tmpl = LIBERAL_PROMPT_TEMPLATE if role == "liberal" else FASCIST_PROMPT_TEMPLATE
    eligible = [str(p["id"]) for p in state["players"] if p["alive"] and p["id"] != agent_id]
    prompt = tmpl.format(
        agent_id=agent_id,
        role=role,
        liberal_policies=ss["liberal_policies"],
        fascist_policies=ss["fascist_policies"],
        deck_size=ss["deck_size"],
        discard_size=ss["discard_size"],
        players_list=_players_list(state, agent_id),
        recent_history=_recent_history(state),
        action=f"Nominate a Chancellor from eligible players: {', '.join(eligible)}.",
        format_instructions="Return a JSON object with: nominate_player (int), public_statement (string), private_thoughts (string)",
    )
    
    # Use LangChain's native structured output with retry logic
    structured_model = llm_client.with_structured_output(NominationOut)
    
    # Stream reasoning for display
    role_display = role.capitalize() if role else "Unknown"
    logger(f"[THOUGHTS][Player {agent_id} ({role_display})]: ", end="")
    
    # Retry logic for API rate limits
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get structured result directly without streaming first
            result = structured_model.invoke(prompt)
            
            # Stream the reasoning for display
            if hasattr(result, 'private_thoughts') and result.private_thoughts:
                logger(result.private_thoughts, end="")
            elif hasattr(result, 'content'):
                logger(result.content or "", end="")
            else:
                # Fallback: stream the raw result as string
                logger(str(result), end="")
            
            logger("", end="\n")
            break
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    logger(f"[RETRY] Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger(f"[ERROR] Max retries exceeded for rate limit. Using fallback nomination.")
                    # Fallback: return a default nomination
                    eligible_ids = [p["id"] for p in state["players"] if p["alive"] and p["id"] != agent_id]
                    result = NominationOut(
                        nominate_player=eligible_ids[0] if eligible_ids else 0,
                        public_statement="Rate limit exceeded, using default nomination",
                        private_thoughts="API rate limit prevented full reasoning"
                    )
            else:
                raise e
    
    # Extract the nominated player ID
    cid = result.nominate_player
    public_statement = result.public_statement
    private_thoughts = result.private_thoughts
    
    # Ensure the nominated player is eligible
    eligible_ids = [p["id"] for p in state["players"] if p["alive"] and p["id"] != agent_id]
    if cid not in eligible_ids:
        cid = eligible_ids[0] if eligible_ids else 0
    
    public = f"I nominate Player {cid}"
    if public_statement:
        public += f": {public_statement}"
    
    logger(f"[NOMINATION] Player {agent_id}: {public}")
    return cid, public, private_thoughts

def vote_tool(agent_id: int, role: str, state: dict, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Tuple[bool, str, str]:
    ss = _state_summary(state)
    tmpl = LIBERAL_PROMPT_TEMPLATE if role == "liberal" else FASCIST_PROMPT_TEMPLATE
    prompt = tmpl.format(
        agent_id=agent_id,
        role=role,
        liberal_policies=ss["liberal_policies"],
        fascist_policies=ss["fascist_policies"],
        deck_size=ss["deck_size"],
        discard_size=ss["discard_size"],
        players_list=_players_list(state, agent_id),
        recent_history=_recent_history(state),
        action=f"Vote on government: President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}.",
        format_instructions="Return a JSON object with: vote (boolean), public_statement (string), private_thoughts (string)",
    )
    
    # Use LangChain's native structured output with retry logic
    structured_model = llm_client.with_structured_output(VoteOut)
    
    # Stream reasoning for display
    role_display = role.capitalize() if role else "Unknown"
    logger(f"[THOUGHTS][Player {agent_id} ({role_display})]: ", end="")
    
    # Retry logic for API rate limits
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get structured result directly without streaming first
            result = structured_model.invoke(prompt)
            
            # Stream the reasoning for display
            if hasattr(result, 'private_thoughts') and result.private_thoughts:
                logger(result.private_thoughts, end="")
            elif hasattr(result, 'content'):
                logger(result.content or "", end="")
            else:
                # Fallback: stream the raw result as string
                logger(str(result), end="")
            
            logger("", end="\n")
            break
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    logger(f"[RETRY] Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger(f"[ERROR] Max retries exceeded for rate limit. Using fallback vote.")
                    # Fallback: return a default vote (Ja for first government)
                    result = VoteOut(
                        vote=True,
                        public_statement="Rate limit exceeded, voting Ja by default",
                        private_thoughts="API rate limit prevented full reasoning"
                    )
            else:
                raise e
    
    vote = result.vote
    public_statement = result.public_statement
    private_thoughts = result.private_thoughts
    
    public = "Ja" if vote else "Nein"
    if public_statement:
        public += f" ({public_statement})"
    
    logger(f"[VOTE] Player {agent_id}: {public}")
    return vote, public, private_thoughts

def president_legislate_tool(agent_id: int, state: dict, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Tuple[List[str], str, str]:
    ss = _state_summary(state)
    drawn = state.get("drawn_policies", [])
    role_local = state["players"][agent_id]["role"]
    tmpl = LIBERAL_PROMPT_TEMPLATE if role_local == "liberal" else FASCIST_PROMPT_TEMPLATE
    prompt = tmpl.format(
        agent_id=agent_id,
        role=role_local,
        liberal_policies=ss["liberal_policies"],
        fascist_policies=ss["fascist_policies"],
        deck_size=ss["deck_size"],
        discard_size=ss["discard_size"],
        players_list=_players_list(state, agent_id),
        recent_history=_recent_history(state),
        action=f"You are President and you drew: {drawn}.",
        format_instructions="Return a JSON object with: discard_policy ('liberal' or 'fascist'), public_statement (string), private_thoughts (string)",
    )
    
    # Use LangChain's native structured output with retry logic
    structured_model = llm_client.with_structured_output(PresidentLegislateOut)
    
    # Stream reasoning for display
    role_display = role_local.capitalize() if role_local else "Unknown"
    logger(f"[THOUGHTS][Player {agent_id} ({role_display})]: ", end="")
    
    # Retry logic for API rate limits
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get structured result directly without streaming first
            result = structured_model.invoke(prompt)
            
            # Stream the reasoning for display
            if hasattr(result, 'private_thoughts') and result.private_thoughts:
                logger(result.private_thoughts, end="")
            elif hasattr(result, 'content'):
                logger(result.content or "", end="")
            else:
                # Fallback: stream the raw result as string
                logger(str(result), end="")
            
            logger("", end="\n")
            break
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    logger(f"[RETRY] Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger(f"[ERROR] Max retries exceeded for rate limit. Using fallback legislation.")
                    # Fallback: return a default legislation (discard fascist)
                    result = PresidentLegislateOut(
                        discard_policy="fascist",
                        public_statement="Rate limit exceeded, discarding fascist by default",
                        private_thoughts="API rate limit prevented full reasoning"
                    )
            else:
                raise e
    
    discard = result.discard_policy
    public_claim = result.public_statement
    private_thoughts = result.private_thoughts
    
    rem = drawn.copy()
    if discard in rem:
        rem.remove(discard)
    else:
        rem = rem[1:] if len(rem) > 1 else []
    
    public = f"I discard {discard}"
    if public_claim:
        public += f": {public_claim}"
    
    logger(f"[PRESIDENT] Player {agent_id}: {public}")
    return rem, public, private_thoughts

def chancellor_legislate_tool(agent_id: int, state: dict, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Tuple[str, str, str]:
    ss = _state_summary(state)
    passed = state.get("passed_policies", [])
    role_local = state["players"][agent_id]["role"]
    tmpl = LIBERAL_PROMPT_TEMPLATE if role_local == "liberal" else FASCIST_PROMPT_TEMPLATE
    prompt = tmpl.format(
        agent_id=agent_id,
        role=role_local,
        liberal_policies=ss["liberal_policies"],
        fascist_policies=ss["fascist_policies"],
        deck_size=ss["deck_size"],
        discard_size=ss["discard_size"],
        players_list=_players_list(state, agent_id),
        recent_history=_recent_history(state),
        action=f"You are Chancellor and received: {passed}.",
        format_instructions="Return a JSON object with: policy_to_enact ('liberal' or 'fascist'), public_statement (string), private_thoughts (string)",
    )
    
    # Use LangChain's native structured output with retry logic
    structured_model = llm_client.with_structured_output(ChancellorLegislateOut)
    
    # Stream reasoning for display
    role_display = role_local.capitalize() if role_local else "Unknown"
    logger(f"[THOUGHTS][Player {agent_id} ({role_display})]: ", end="")
    
    # Retry logic for API rate limits
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get structured result directly without streaming first
            result = structured_model.invoke(prompt)
            
            # Stream the reasoning for display
            if hasattr(result, 'private_thoughts') and result.private_thoughts:
                logger(result.private_thoughts, end="")
            elif hasattr(result, 'content'):
                logger(result.content or "", end="")
            else:
                # Fallback: stream the raw result as string
                logger(str(result), end="")
            
            logger("", end="\n")
            break
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    logger(f"[RETRY] Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger(f"[ERROR] Max retries exceeded for rate limit. Using fallback enactment.")
                    # Fallback: return a default enactment (liberal)
                    result = ChancellorLegislateOut(
                        policy_to_enact="liberal",
                        public_statement="Rate limit exceeded, enacting liberal by default",
                        private_thoughts="API rate limit prevented full reasoning"
                    )
            else:
                raise e
    
    enact = result.policy_to_enact
    public_claim = result.public_statement
    private_thoughts = result.private_thoughts
    
    # Ensure the chosen enactment is one of the passed policies; if not, default to the first passed policy.
    if enact not in passed:
        enact = passed[0] if passed else enact
    
    public = f"I enact {enact}"
    if public_claim:
        public += f": {public_claim}"
    
    logger(f"[CHANCELLOR] Player {agent_id}: {public}")
    return enact, public, private_thoughts

def investigate_tool(agent_id: int, state: dict, model: Optional[str] = None, llm_client: Optional[Any] = None) -> Tuple[int, str, str]:
    ss = _state_summary(state)
    eligible = [p["id"] for p in state["players"] if p["alive"] and not p.get("investigated", False)]
    role_local = state["players"][agent_id]["role"]
    tmpl = LIBERAL_PROMPT_TEMPLATE if role_local == "liberal" else FASCIST_PROMPT_TEMPLATE
    prompt = tmpl.format(
        agent_id=agent_id,
        role=role_local,
        liberal_policies=ss["liberal_policies"],
        fascist_policies=ss["fascist_policies"],
        deck_size=ss["deck_size"],
        discard_size=ss["discard_size"],
        players_list=_players_list(state, agent_id),
        recent_history=_recent_history(state),
        action=f"You may investigate one player. Eligible: {eligible}.",
        format_instructions="Return a JSON object with: player_to_investigate (int), public_statement (string), private_thoughts (string)",
    )
    
    # Use LangChain's native structured output with retry logic
    structured_model = llm_client.with_structured_output(InvestigateOut)
    
    # Stream reasoning for display
    role_display = role_local.capitalize() if role_local else "Unknown"
    logger(f"[THOUGHTS][Player {agent_id} ({role_display})]: ", end="")
    
    # Retry logic for API rate limits
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            # Get structured result directly without streaming first
            result = structured_model.invoke(prompt)
            
            # Stream the reasoning for display
            if hasattr(result, 'private_thoughts') and result.private_thoughts:
                logger(result.private_thoughts, end="")
            elif hasattr(result, 'content'):
                logger(result.content or "", end="")
            else:
                # Fallback: stream the raw result as string
                logger(str(result), end="")
            
            logger("", end="\n")
            break
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if attempt < max_retries - 1:
                    logger(f"[RETRY] Rate limit hit, waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger(f"[ERROR] Max retries exceeded for rate limit. Using fallback investigation.")
                    # Fallback: return a default investigation
                    result = InvestigateOut(
                        player_to_investigate=eligible[0] if eligible else 0,
                        public_statement="Rate limit exceeded, investigating first eligible player by default",
                        private_thoughts="API rate limit prevented full reasoning"
                    )
            else:
                raise e
    
    target = result.player_to_investigate
    reason = result.public_statement
    private_thoughts = result.private_thoughts
    
    # Ensure the target is eligible
    if target not in eligible:
        target = eligible[0] if eligible else 0
    
    public = f"I investigate Player {target}"
    if reason:
        public += f": {reason}"
    
    logger(f"[INVESTIGATE] Player {agent_id} reason: {public}")
    return target, public, private_thoughts