import os
import warnings

# Fix for OpenMP runtime conflict (OMP: Error #15)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Configure Matplotlib cache directory to be local and writable
# Must be set before importing matplotlib
os.environ['MPLCONFIGDIR'] = os.path.join(os.getcwd(), '.matplotlib_cache')
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.middleware.rate_limit import RateLimitMiddleware

from src.core.database import get_app_db
from src.workflow.graph import create_graph

try:
    if os.getenv("ENABLE_PHOENIX", "true").lower() == "true":
        import socket
        reachable = False
        try:
            with socket.create_connection(("localhost", 4317), timeout=0.3) as _:
                reachable = True
        except Exception:
            reachable = False
        if reachable:
            from phoenix.otel import register
            from openinference.instrumentation.langchain import LangChainInstrumentor
            tracer_provider = register(project_name="smallmo-chat")
            LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
            print("Phoenix Tracing Enabled.")
        else:
            print("Phoenix Tracing Disabled: OTLP endpoint not reachable.")
    else:
        print("Phoenix Tracing Disabled by ENV.")
except Exception as e:
    print(f"Failed to initialize Phoenix tracing: {e}")

from src.api.routes import datasource, project, audit, chat, llm, auth, feedback
from src.api.routes import query

# Ignore warnings
warnings.filterwarnings("ignore")

app = FastAPI(title="Text2SQL Agent API")
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error for {request.url}: {exc.errors()}")
    try:
        body = await request.json()
        print(f"Request Body: {body}")
    except:
        pass
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": "See server logs for request body"},
    )

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
    
    # Background schema indexing (pre-warm) to avoid blocking first requests
    try:
        if settings.ENABLE_SCHEMA_BACKGROUND_INDEX:
            import asyncio
            from src.domain.schema.search import get_schema_searcher
            from src.core.models import Project
            from sqlmodel import select
            async def _bg_index():
                try:
                    app_db = get_app_db()
                    with app_db.get_session() as session:
                        projects = session.exec(select(Project)).all()
                        if not projects:
                            print("Background schema indexing skipped: no projects found.")
                            return
                        # Controlled concurrency pool
                        sem = asyncio.Semaphore(6)
                        async def _run_index(pid: int):
                            async with sem:
                                searcher = get_schema_searcher(pid)
                                await asyncio.to_thread(searcher.index_schema, False)
                        tasks = [asyncio.create_task(_run_index(p.id)) for p in projects]
                        await asyncio.gather(*tasks)
                        print(f"Background schema indexing completed for {len(projects)} project(s).")
                except Exception as e:
                    print(f"Background schema indexing failed: {e}")
            asyncio.create_task(_bg_index())
    except Exception as e:
        print(f"Failed to schedule background indexing: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
