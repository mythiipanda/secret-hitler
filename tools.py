from typing import List, Optional, Tuple
from llm import call_model
from parsers import nom_parser, vote_parser, pres_parser, chanc_parser, inv_parser

def nominate_tool(agent_id: int, role: str, eligible: List[int], model: Optional[str] = None) -> Tuple[int, str]:
    fmt = nom_parser.get_format_instructions()
    prompt = f"You are Player {agent_id} ({role}). Eligible nominees: {eligible}.\n{fmt}\nProvide only the JSON."
    resp = call_model(prompt, model=model)
    parsed = nom_parser.parse(resp)
    cid = int(parsed.nominated_chancellor)
    if parsed.public_statement:
        print(f"[NOMINATION] Player {agent_id}: {parsed.public_statement}")
    return cid, parsed.public_statement or ""

def vote_tool(agent_id: int, role: str, president_idx: int, nominated_chancellor: int, model: Optional[str] = None) -> Tuple[bool, str]:
    fmt = vote_parser.get_format_instructions()
    prompt = f"You are Player {agent_id} ({role}). President {president_idx} nominated {nominated_chancellor}.\n{fmt}\nProvide only the JSON."
    resp = call_model(prompt, model=model)
    parsed = vote_parser.parse(resp)
    if parsed.public_statement:
        print(f"[VOTE] Player {agent_id}: {parsed.public_statement}")
    return bool(parsed.vote), parsed.public_statement or ""

def president_legislate_tool(agent_id: int, drawn: List[str], model: Optional[str] = None) -> Tuple[List[str], str]:
    fmt = pres_parser.get_format_instructions()
    prompt = f"You are President {agent_id}. You drew: {drawn}.\n{fmt}\nProvide only the JSON."
    resp = call_model(prompt, model=model)
    parsed = pres_parser.parse(resp)
    discard = parsed.discard
    rem = drawn.copy()
    if discard in rem:
        rem.remove(discard)
    else:
        rem = rem[1:] if len(rem) > 1 else []
    if parsed.public_claim:
        print(f"[PRESIDENT] Player {agent_id}: {parsed.public_claim}")
    return rem, parsed.public_claim or ""

def chancellor_legislate_tool(agent_id: int, passed: List[str], model: Optional[str] = None) -> Tuple[str, str]:
    fmt = chanc_parser.get_format_instructions()
    prompt = f"You are Chancellor {agent_id}. You received: {passed}.\n{fmt}\nProvide only the JSON."
    resp = call_model(prompt, model=model)
    parsed = chanc_parser.parse(resp)
    enact = parsed.enact
    if parsed.public_claim:
        print(f"[CHANCELLOR] Player {agent_id}: {parsed.public_claim}")
    return enact, parsed.public_claim or ""

def investigate_tool(agent_id: int, eligible: List[int], model: Optional[str] = None) -> Tuple[int, str]:
    fmt = inv_parser.get_format_instructions()
    prompt = f"You are President {agent_id}. Eligible to investigate: {eligible}.\n{fmt}\nProvide only the JSON."
    resp = call_model(prompt, model=model)
    parsed = inv_parser.parse(resp)
    target = int(parsed.investigate)
    return target, parsed.reason or ""