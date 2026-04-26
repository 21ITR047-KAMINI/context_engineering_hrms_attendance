from graph.graph_builder import build_graph
from graph.state import create_initial_state
import time


def run(query: str):
    graph = build_graph()
    start = time.time()
    state = create_initial_state(query)
    final = graph.invoke(state)
    latency = time.time() - start
    print("FINAL STATE KEYS:", list(final.keys()))
    print("RESPONSE:", final.get("response"))
    print("LATENCY:", latency)


if __name__ == '__main__':
    q = "list the employee AD25061070 march month attendance detail, with half day, full day - leave or worked or permission"
    run(q)
