
import uuid
from langchain_core.messages import HumanMessage
from src.graph import create_graph

def debug_graph():
    print("Initializing Graph...")
    app = create_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    user_input = "用户有多少人"
    print(f"User Input: {user_input}")
    
    inputs = {"messages": [HumanMessage(content=user_input)]}
    
    print("Starting Execution (Stream Mode)...")
    try:
        # Use simple stream to see if nodes are hit
        for output in app.stream(inputs, config=config):
            for key, value in output.items():
                print(f"Node: {key}")
                print(f"Output: {value}")
                print("-" * 20)
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_graph()
