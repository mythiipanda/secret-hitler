from dotenv import load_dotenv
import os
import random
from game import create_initial_state
from agents import initialize_agents
from graph import build_workflow
from log import init as init_log, log as logger, close as close_log

load_dotenv()
random.seed(0)

def main():
    log_path = init_log()
    state = create_initial_state()
    model = os.environ.get("GEMINI_MODEL")
    state["agents"] = initialize_agents(state["players"], model=model)
    app = build_workflow().compile()
    logger("\n" + "=" * 60)
    logger("STARTING GAME")
    logger("=" * 60)
    finished = False
    for output in app.stream(state, stream_mode="updates", config={"recursion_limit": 1000}):
        for node_name, node_state in output.items():
            state = node_state
            if len(state.get("messages", [])) > 500:
                logger("\n[ERROR] Game exceeded 500 actions, terminating.")
                finished = True
            if node_state.get("phase") == "game_over" or node_state.get("winner") is not None:
                finished = True
        if finished:
            break
    logger("\n" + "=" * 60)
    logger("GAME SIMULATION COMPLETE")
    logger("=" * 60)
    close_log()

if __name__ == "__main__":
    main()