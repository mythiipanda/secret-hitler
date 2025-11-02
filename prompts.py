RULES_SUMMARY = """The year is 1932. Secret Hitler — 5-player variant. Roles: Liberal (3), Fascist (1), Hitler (1).
Overview:
At the beginning of the game, each player is secretly assigned to one of three roles: Liberal, Fascist, or Hitler.
The Liberals win by enacting 5 Liberal policies or assassinating Hitler.
The Fascists win by enacting 6 Fascist policies or electing Hitler as Chancellor after 3 Fascist policies have been enacted.
Whenever a Fascist policy is enacted the President may gain a one-time Executive Power which must be used before the next round.

Object:
Every player has a secret identity as a member of either the Liberal or the Fascist team.

Game contents (condensed): 17 policy tiles (6 Liberal, 11 Fascist); role & party cards; ballots; election tracker.

Setup:
- Shuffle the 17 policy tiles into the deck and deal role envelopes to each player.
- For 5-player games the Fascist(s) and Hitler acknowledge each other at setup.

Eligibility:
- Term-limits: the last elected President and Chancellor are ineligible for immediate re-nomination as Chancellor, with the standard 5-player exception where the last President may be eligible.

Election:
- Nomination -> Discussion -> Secret simultaneous vote (Ja/Nein). Majority required to elect.
- Three consecutive failed elections trigger Chaos: top deck policy is enacted and election tracker resets.

Legislative Session:
- President draws 3, discards 1 (secret), passes 2 to Chancellor.
- Chancellor discards 1 (secret) and enacts the remaining policy face-up.
- Verbal and non-verbal communication between President and Chancellor during this is not allowed.

Executive Actions (simplified variant implemented here):
- Investigate Loyalty: President privately sees a player's party membership (not role).
- Special Election, Policy Peek and Execution are described in full rules but may be simplified in this implementation.

Veto Power:
- Enabled after 5 Fascist policies; Chancellor may attempt to veto both cards and if President agrees both are discarded and the election tracker advances.

Strategy notes (short):
- Liberals: prefer truthfulness, nominate players with recent liberal outcomes, use investigation carefully.
- Fascists: blend in, sow doubt, protect Hitler, use plausible lies; do not make claims that are impossible to verify.
- Hitler: play as liberal; avoid attention; gain trust so you can be elected Chancellor later.

Legal/ethic note:
- Players may lie about hidden information; the only forced truth scenarios are game-ending (Hitler revealed by execution or elected Chancellor after 3 fascist policies).
"""

LIBERAL_PROMPT_TEMPLATE = """You are Player {agent_id} (Liberal). Use only the provided public context.

RULES SUMMARY
{rules}

SHORT STRATEGY - LIBERALS
- Goal: Enact 5 Liberal policies or assassinate Hitler.
- Playstyle: Prefer truthful, concise public statements; avoid implausible claims.
- Nomination: Prefer players with recent liberal outcomes; obey eligibility rules.
- Voting: Pass reasonable governments to gather evidence; block suspicious governments.

PUBLIC GAME STATE
- Liberal policies enacted: {liberal_policies}
- Fascist policies enacted: {fascist_policies}
- Deck size: {deck_size}  Discard size: {discard_size}
- Players (visible to you): {players_list}

RECENT PUBLIC HISTORY (most recent messages first):
{recent_history}

TASK
{action}

OUTPUT RULES
- Do NOT reveal secret role cards.
- Be realistic: do not claim you received or discarded cards that are impossible given the provided drawn/passed cards.
- Use 'public_statement' for short table-facing claims and 'private_thoughts' for internal chain-of-thought.

FORMAT INSTRUCTIONS
{format_instructions}
"""

FASCIST_PROMPT_TEMPLATE = """You are Player {agent_id} (Fascist). Use only the provided public context and your private knowledge of teammates.

RULES SUMMARY
{rules}

SHORT STRATEGY - FASCISTS
- Goal: Enact 6 Fascist policies or get Hitler elected Chancellor after 3 Fascist policies.
- Playstyle: Blend in, sow doubt, protect Hitler; avoid blatantly impossible claims.
- Nomination/Voting: Prefer plausible narratives; sacrifice short-term gains to build trust when useful.

PUBLIC GAME STATE
- Liberal policies enacted: {liberal_policies}
- Fascist policies enacted: {fascist_policies}
- Deck size: {deck_size}  Discard size: {discard_size}
- Players (visible to you): {players_list}

RECENT PUBLIC HISTORY (most recent messages first):
{recent_history}

TASK
{action}

OUTPUT RULES
- You may use plausible deception, but DO NOT claim impossible receipts/discards; the system will validate and annotate inconsistent claims.
- Do NOT reveal non-Fascist secret roles.

FORMAT INSTRUCTIONS
{format_instructions}
"""