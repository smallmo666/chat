import os
import warnings

# Configure Matplotlib cache directory to be local and writable
# Must be set before importing matplotlib
os.environ['MPLCONFIGDIR'] = os.path.join(os.getcwd(), '.matplotlib_cache')
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.middleware.rate_limit import RateLimitMiddleware

from src.core.database import get_app_db
from src.workflow.graph import create_graph

try:
    if os.getenv("ENABLE_PHOENIX", "true").lower() == "true":
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor
        tracer_provider = register(project_name="smallmo-chat")
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        print("Phoenix Tracing Enabled.")
    else:
        print("Phoenix Tracing Disabled by ENV.")
except Exception as e:
    print(f"Failed to initialize Phoenix tracing: {e}")

from src.api.routes import datasource, project, audit, chat, llm, auth, feedback
from src.api.routes import query

# Ignore warnings
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# Include Routers
app.include_router(datasource.router, prefix="/api")
app.include_router(project.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(query.router, prefix="/api")

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
