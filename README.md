# Secret Hitler 5-Agent Benchmark

A single-run, multi-agent implementation of the Secret Hitler board game using **LangGraph** for orchestration and **Gemini Flash Lite** for AI decision-making.

## Overview

This benchmark simulates a complete 5-player game of Secret Hitler where AI agents:
- Are assigned random roles (3 Liberals, 1 Fascist, 1 Hitler)
- Make strategic decisions based on their roles and game state
- Communicate publicly through statements and claims
- Work toward their team's victory conditions

## Game Rules (5-Player Setup)

### Roles
- **3 Liberals**: Don't know anyone's role, must identify and stop fascists
- **1 Fascist**: Knows Hitler's identity, works to enact fascist policies
- **1 Hitler**: Knows the Fascist's identity, must stay hidden

### Win Conditions
- **Liberals win**: Enact 5 Liberal policies OR execute Hitler (not implemented)
- **Fascists win**: Enact 6 Fascist policies OR elect Hitler as Chancellor after 3 fascist policies

### Game Flow
1. **Presidential Nomination**: President nominates a Chancellor
2. **Election**: All players vote Ja (yes) or Nein (no)
   - Majority Ja: Government elected, proceed to legislation
   - Majority Nein: Election tracker advances, presidency rotates
   - 3 failed elections: Chaos - top policy auto-enacted
3. **Legislative Session** (if elected):
   - President draws 3 policies, discards 1, passes 2 to Chancellor
   - Chancellor discards 1, enacts 1
4. **Executive Action**: After 3rd fascist policy, President investigates a player's loyalty
5. **Next Round**: Presidency rotates clockwise

### Policies
- **Deck**: 6 Liberal + 11 Fascist policies
- **Reshuffle**: Discard pile shuffled back when deck depletes

## Technical Architecture

### Stack
- **LangGraph**: State graph orchestration for turn-based gameplay
- **LangChain**: Wrapper for Gemini API integration
- **Gemini 2.0 Flash Lite**: AI model for all agent decisions
- **Python 3.13+**: Core implementation language

### Components

#### 1. Game State (`GameState` TypedDict)
Centralized state tracking:
- Player roles, policies enacted, policy deck
- Current president/chancellor, election tracker
- Phase tracking (nominate ’ vote ’ legislate ’ executive ’ check_win)
- Full message log for agent context

#### 2. Agent System (`SecretHitlerAgent`)
Role-based AI agents with:
- **Role-specific prompting**: Different information for Liberals vs Fascists
- **Strategic decision-making**: Nomination, voting, legislation, investigation
- **Public communication**: Statements and claims to other players
- **JSON-structured responses**: Parsed and validated

#### 3. LangGraph Workflow
7 nodes with conditional routing:
- `nominate`: President nominates Chancellor
- `vote`: All players vote on government
- `legislate_president`: Draw 3 policies, pass 2
- `legislate_chancellor`: Receive 2 policies, enact 1
- `check_win`: Check victory conditions
- `executive`: Investigate player loyalty (after 3rd fascist policy)
- `game_over`: Display results and role reveal

## Setup

### Prerequisites
- Python 3.13+
- Gemini API key (free tier works)

### Installation

1. **Clone or download** this repository

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```
   Or with uv:
   ```bash
   uv pip install -e .
   ```

3. **Create `.env` file** with your API key:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a key at: https://ai.google.dev/

### Run the Game

```bash
python main.py
```

## Example Output

```
============================================================
SECRET HITLER - 5 PLAYER GAME
============================================================

[SETUP] Roles assigned (SECRET):
  Player 0: LIBERAL (liberal)
  Player 1: FASCIST (fascist)
  Player 2: LIBERAL (liberal)
  Player 3: HITLER (fascist)
  Player 4: LIBERAL (liberal)

[SETUP] Starting President: Player 2
[SETUP] Policy deck created: 6 Liberal, 11 Fascist

============================================================
STARTING GAME
============================================================

--- ROUND: President Player 2 ---
[NOMINATION] Player 2: I nominate Player 0 because they seem trustworthy.

[VOTING] On government: President 2, Chancellor 0
  Player 0: JA
  Player 1: NEIN
  Player 2: JA
  Player 3: JA
  Player 4: JA

[RESULT] Government ELECTED (4/5 Ja). President 2, Chancellor 0.

[LEGISLATIVE SESSION] President draws 3 policies...
  (President sees: 1 Liberal, 2 Fascist)
[PRESIDENT] Player 2: I drew 2 fascist and 1 liberal, passing both options.

[LEGISLATIVE SESSION] Chancellor receives 2 policies...
  (Chancellor sees: 1 Liberal, 1 Fascist)
[CHANCELLOR] Player 0: President gave me 1 liberal and 1 fascist, I enacted the liberal.

[POLICY ENACTED] LIBERAL policy enacted!

...

============================================================
GAME OVER
============================================================

Winner: LIBERALS
Reason: 5 Liberal policies enacted!

Final Score: 5 Liberal, 2 Fascist

=== ROLE REVEAL ===
Player 0: LIBERAL (liberal)
Player 1: FASCIST (fascist)
Player 2: LIBERAL (liberal)
Player 3: HITLER (fascist)
Player 4: LIBERAL (liberal)
```

## Implementation Details

### Agent Prompting Strategy

Each agent receives:
1. **Secret role information**:
   - Liberals: No role knowledge
   - Fascist: Knows Hitler's player ID
   - Hitler: Knows Fascist's player ID

2. **Visible game state**:
   - Policy counts (Liberal/Fascist)
   - Current president/chancellor
   - Election tracker status
   - Recent game history (last 10 actions)

3. **Action-specific context**:
   - Eligible choices (e.g., valid chancellor nominations)
   - Strategy tips for their role
   - Hitler Zone warnings (after 3 fascist policies)

### LLM Response Handling

- **Structured JSON output**: All agent responses formatted as JSON
- **Fallback validation**: Invalid responses use safe defaults + random choice
- **Markdown extraction**: Handles responses wrapped in code blocks
- **Error tolerance**: Game continues even with malformed LLM responses

### Key Design Decisions

1. **Stateless agents**: All context passed in prompts, no persistent memory
2. **Global agent list**: Simplifies node access (alternative: pass in state)
3. **Single LLM instance**: Shared across all agents for efficiency
4. **High temperature (0.8)**: Encourages varied strategic play
5. **Safety limit**: Terminates after 100 game actions to prevent infinite loops

## Limitations & Simplifications

This is a **minimal benchmark** implementation:

- **No veto power**: Requires 5 fascist policies (complex negotiation)
- **No execution power**: Would need player elimination logic
- **Single executive power**: Only "Investigate Loyalty" implemented
- **Limited strategy depth**: Agents don't track complex patterns over time
- **No multi-game learning**: Each run is independent

## Extending the Benchmark

Potential enhancements:

1. **Add more executive powers**: Special election, policy peek, execution
2. **Implement veto**: After 5 fascist policies
3. **Multi-game tournaments**: Track win rates across roles
4. **Strategy evaluation**: Measure bluffing effectiveness, trust building
5. **Different agent types**: Mix rule-based and LLM-based agents
6. **Larger games**: 7-10 players with adjusted role distribution
7. **Persistent memory**: Agents remember previous game patterns

## Troubleshooting

### API Key Issues
```
ValueError: GEMINI_API_KEY not found in environment variables
```
**Solution**: Create `.env` file with `GEMINI_API_KEY=your_key`

### Dependency Errors
```
ImportError: No module named 'langgraph'
```
**Solution**: Run `pip install -e .` to install dependencies

### LLM Timeout/Errors
The game has fallback logic but may produce warnings:
```
[WARNING] Failed to parse LLM response, using default
```
This is expected occasionally - the game will continue with safe defaults.

## Architecture Notes

### Why LangGraph?
- **State management**: Clean separation of game state from logic
- **Conditional routing**: Different paths based on votes/win conditions
- **Node modularity**: Each phase is a self-contained function
- **Graph visualization**: Can render workflow (not implemented here)

### Why Gemini Flash Lite?
- **Fast inference**: Sub-second responses for smooth gameplay
- **Cost-effective**: Free tier supports many games
- **Good reasoning**: Handles strategic decision-making well
- **JSON mode**: Reliable structured output (with fallback parsing)

## License

MIT License - Feel free to use for research, education, or benchmarking.

## Acknowledgments

- **Secret Hitler** board game by Max Temkin, Mike Boxleiter, Tommy Maranges
- **LangGraph** by LangChain team for state graph framework
- **Gemini API** by Google for AI model access
