from typing import Any, Dict
from src.workflow.state import AgentState
from src.domain.knowledge.retriever import get_knowledge_retriever
from src.core.event_bus import EventBus

async def knowledge_retrieval_node(state: AgentState, config: Dict = None) -> Dict[str, Any]:
    """
    Knowledge Retrieval Node
    Retrieves relevant business knowledge (terms, formulas) based on user query using Milvus Vector Search.
    """
    print("DEBUG: Entering Knowledge Retrieval Node")
    project_id = config.get("configurable", {}).get("project_id") if config else None
    
    # 1. Get user query
    query = ""
    for msg in reversed(state["messages"]):
        if msg.type == "human":
            query = msg.content
            break
            
    if not query:
        return {"knowledge_context": None}

    # Emit Status
    await EventBus.emit_substep(
        node="KnowledgeRetrieval",
        step="检索中",
        detail=f"正在向量库中检索关于 '{query[:10]}...' 的知识"
    )

    # 2. Search Knowledge Base (Vector Search)
    try:
        retriever = get_knowledge_retriever(project_id)
        knowledge_context = retriever.retrieve(query)
        
        if knowledge_context:
            count = knowledge_context.count("- **")
            await EventBus.emit_substep(
                node="KnowledgeRetrieval",
                step="检索完成",
                detail=f"找到 {count} 条相关知识"
            )
            print(f"DEBUG: Retrieved {count} knowledge items.")
            return {"knowledge_context": knowledge_context}
        else:
            await EventBus.emit_substep(
                node="KnowledgeRetrieval",
                step="检索完成",
                detail="未找到相关知识"
            )
            print("DEBUG: No relevant knowledge found.")
            return {"knowledge_context": None}

    except Exception as e:
        print(f"Knowledge Retrieval Failed: {e}")
        await EventBus.emit_substep(
            node="KnowledgeRetrieval",
            step="错误",
            detail=f"检索失败: {str(e)}"
        )
        return {"knowledge_context": None}

