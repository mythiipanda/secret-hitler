from typing import List, Optional, Tuple
from llm import call_model, stream_model
from parsers import nom_parser, vote_parser, pres_parser, chanc_parser, inv_parser
from prompts import LIBERAL_PROMPT_TEMPLATE, FASCIST_PROMPT_TEMPLATE, RULES_SUMMARY

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

def _stream_and_parse(prompt: str, parser, agent_id: int, model: Optional[str] = None):
    """
    Stream model output and print private thoughts token-by-token.
    Expects the model to output PRIVATE_THOUGHTS plain text, then a line ===JSON===,
    then the JSON object. Returns the parsed Pydantic model.

    If streaming fails to produce a JSON body, fall back to a synchronous
    call_model() and attempt to extract JSON from that full response.
    """
    seen_marker = False
    json_parts: List[str] = []
    thought_started = False

    for chunk in stream_model(prompt, model=model):
        text = chunk or ""
        if not seen_marker:
            if "===JSON===" in text:
                before, _, after = text.partition("===JSON===")
                if before:
                    if not thought_started:
                        print(f"[THOUGHTS][Player {agent_id}]: ", end="", flush=True)
                        thought_started = True
                    print(before, end="", flush=True)
                seen_marker = True
                if after:
                    json_parts.append(after)
            else:
                if not thought_started:
                    print(f"[THOUGHTS][Player {agent_id}]: ", end="", flush=True)
                    thought_started = True
                print(text, end="", flush=True)
        else:
            json_parts.append(text)

    if thought_started:
        print()  # newline after streaming thoughts

    json_text = "".join(json_parts).strip()

    # If stream didn't produce JSON, fall back to synchronous model call and extract
    if not json_text:
        full = call_model(prompt, model=model)
        if "===JSON===" in full:
            _, _, after = full.partition("===JSON===")
            json_text = after.strip()
        else:
            # heuristic: extract last JSON-like substring
            import re

            m = re.search(r"(\{[\s\S]*\})\s*$", full)
            if m:
                json_text = m.group(1).strip()
            else:
                raise ValueError("Failed to extract JSON from model output (stream + fallback). Full response:\n" + full)

    parsed = parser.parse(json_text)
    return parsed

def nominate_tool(agent_id: int, role: str, state: dict, model: Optional[str] = None) -> Tuple[int, str, str]:
    fmt = nom_parser.get_format_instructions()
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
        action="Nominate a Chancellor from eligible players: " + ", ".join(str(p["id"]) for p in state["players"] if p["alive"] and p["id"] != agent_id),
        format_instructions=fmt,
    )
    parsed = _stream_and_parse(prompt, nom_parser, agent_id, model=model)
    cid = int(parsed.nominated_chancellor)
    public = parsed.public_statement or ""
    private = parsed.private_thoughts or ""
    if public:
        print(f"[NOMINATION] Player {agent_id}: {public}")
    return cid, public, private

def vote_tool(agent_id: int, role: str, state: dict, model: Optional[str] = None) -> Tuple[bool, str, str]:
    fmt = vote_parser.get_format_instructions()
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
        action=f"Vote on government: President {state['current_president_idx']}, Chancellor {state['nominated_chancellor_idx']}. Explain your public statement and provide private_thoughts.",
        format_instructions=fmt,
    )
    parsed = _stream_and_parse(prompt, vote_parser, agent_id, model=model)
    public = parsed.public_statement or ""
    private = parsed.private_thoughts or ""
    if public:
        print(f"[VOTE] Player {agent_id}: {public}")
    return bool(parsed.vote), public, private

def president_legislate_tool(agent_id: int, state: dict, model: Optional[str] = None) -> Tuple[List[str], str, str]:
    fmt = pres_parser.get_format_instructions()
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
        action=f"You are President and you drew: {drawn}. Discard one and pass remaining two to Chancellor.",
        format_instructions=fmt,
    )
    parsed = _stream_and_parse(prompt, pres_parser, agent_id, model=model)
    discard = parsed.discard
    rem = drawn.copy()
    if discard in rem:
        rem.remove(discard)
    else:
        rem = rem[1:] if len(rem) > 1 else []
    public = parsed.public_claim or ""
    private = parsed.private_thoughts or ""
    if public:
        print(f"[PRESIDENT] Player {agent_id}: {public}")
    return rem, public, private

def chancellor_legislate_tool(agent_id: int, state: dict, model: Optional[str] = None) -> Tuple[str, str, str]:
    fmt = chanc_parser.get_format_instructions()
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
        action=f"You are Chancellor and received: {passed}. Choose which policy to enact.",
        format_instructions=fmt,
    )
    parsed = _stream_and_parse(prompt, chanc_parser, agent_id, model=model)
    enact = parsed.enact
    public = parsed.public_claim or ""
    private = parsed.private_thoughts or ""
    if public:
        print(f"[CHANCELLOR] Player {agent_id}: {public}")
    return enact, public, private

def investigate_tool(agent_id: int, state: dict, model: Optional[str] = None) -> Tuple[int, str, str]:
    fmt = inv_parser.get_format_instructions()
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
        action=f"You may investigate one player. Eligible: {eligible}. Pick one and give reason.",
        format_instructions=fmt,
    )
    parsed = _stream_and_parse(prompt, inv_parser, agent_id, model=model)
    target = int(parsed.investigate)
    public = parsed.reason or ""
    private = parsed.private_thoughts or ""
    if public:
        print(f"[INVESTIGATE] Player {agent_id} reason: {public}")
    return target, public, private