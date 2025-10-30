from dotenv import load_dotenv
import os
import random
from game import create_initial_state
from agents import initialize_agents
from graph import build_workflow

load_dotenv()
random.seed(0)

def main():
    state = create_initial_state()
    model = os.environ.get("GEMINI_MODEL")
    state["agents"] = initialize_agents(state["players"], model=model)
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