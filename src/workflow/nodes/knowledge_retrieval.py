from typing import Any, Dict
from src.workflow.state import AgentState
from src.core.models import Knowledge
from src.core.database import get_app_db
from sqlmodel import select

async def knowledge_retrieval_node(state: AgentState, config: Dict = None) -> Dict[str, Any]:
    """
    Knowledge Retrieval Node
    Retrieves relevant business knowledge (terms, formulas) based on user query.
    Currently uses simple keyword matching (LIKE). Future: Vector Similarity Search.
    """
    print("DEBUG: Entering Knowledge Retrieval Node")
    
    # 1. Get user query
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    if not query:
        return {"knowledge_context": None}

    # 2. Search Knowledge Base (Simple Keyword Match)
    # TODO: Upgrade to Vector Search with ChromaDB
    retrieved_knowledge = []
    
    try:
        app_db = get_app_db()
        with app_db.get_session() as session:
            # Fetch all terms (optimization: fetch only relevant if possible)
            # For MVP, we fetch all and match in python or use simple LIKE query if specific keywords found
            # Let's try simple LIKE for each word in query (naive approach)
            
            # Better Naive Approach: Fetch all knowledge and check if term exists in query
            all_knowledge = session.exec(select(Knowledge)).all()
            
            for k in all_knowledge:
                if k.term.lower() in query.lower():
                    retrieved_knowledge.append(f"- **{k.term}**: {k.definition}" + (f" (Formula: {k.formula})" if k.formula else ""))
                    
    except Exception as e:
        print(f"Knowledge Retrieval Failed: {e}")
        # Fail gracefully
        return {"knowledge_context": None}

    # 3. Format Context
    if not retrieved_knowledge:
        print("DEBUG: No relevant knowledge found.")
        return {"knowledge_context": None}
        
    knowledge_context = "### Relevant Business Knowledge:\n" + "\n".join(retrieved_knowledge)
    print(f"DEBUG: Retrieved {len(retrieved_knowledge)} knowledge items.")
    
    return {"knowledge_context": knowledge_context}
