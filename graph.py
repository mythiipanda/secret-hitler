from langgraph.graph import StateGraph, END
from game import (
    nomination_node,
    voting_node,
    president_legislative_node,
    chancellor_legislative_node,
    check_win_node,
    executive_action_node,
    game_over_node,
    route_phase,
)
from game_types import GameState

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