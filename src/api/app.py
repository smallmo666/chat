import warnings
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

from src.core.database import get_app_db
from src.workflow.graph import create_graph

# Setup Phoenix Tracing
# This will instrument all LangChain runs within this process
# tracer_provider = register()
# LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

from src.api.routes import datasource, project, audit, chat, llm, auth, feedback # Added feedback

# Ignore warnings
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(datasource.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(feedback.router, prefix="/api") # Registered feedback

@app.on_event("startup")
async def startup_event():
    print("Initializing Text2SQL Agent...")
    
    # Initialize DB (ensure tables created)
    try:
        get_app_db()
    except Exception as e:
        print(f"DB Init error: {e}")

    # Pre-warm graph (optional, since it's lazy loaded in chat route now)
    # But good to check for errors early
    try:
        create_graph()
        print("Graph initialized check passed.")
    except Exception as e:
        print(f"Graph initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
