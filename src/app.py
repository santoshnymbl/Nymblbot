"""
Miss Minutes - Main Application
Nymbl's AI Assistant Slack Bot

Personal bot for everyone in the organization.
"""
import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.models import init_database, get_stats
from src.ai import initialize_rag, ai_generator
from src.slack import create_slack_app
from src.scheduler import reminder_scheduler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Create Slack app
slack_app = create_slack_app()
slack_handler = AsyncSlackRequestHandler(slack_app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    
    # =========================================================================
    # STARTUP
    # =========================================================================
    logger.info("🕐 Miss Minutes starting up...")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_database()
    
    # Initialize RAG pipeline
    logger.info("Loading knowledge base...")
    initialize_rag()
    
    # Initialize AI generator
    logger.info("Initializing AI generator...")
    ai_generator.initialize()
    
    # Initialize and start scheduler
    logger.info("Starting reminder scheduler...")
    reminder_scheduler.initialize(slack_app.client)
    reminder_scheduler.start()
    
    logger.info("✅ Miss Minutes is ready!")
    logger.info(f"Next scheduler check: {reminder_scheduler.get_next_run()}")
    
    yield
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    logger.info("🕐 Miss Minutes shutting down...")
    reminder_scheduler.stop()
    logger.info("Goodbye!")


# Create FastAPI app
app = FastAPI(
    title="Miss Minutes",
    description="Nymbl's AI Assistant - Personal bot for everyone",
    version="2.0.0",
    lifespan=lifespan
)


# =============================================================================
# HEALTH ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with status"""
    stats = await get_stats()
    return {
        "status": "ok",
        "bot": "Miss Minutes 🕐",
        "version": "2.0.0",
        "stats": stats,
        "next_scheduler_check": reminder_scheduler.get_next_run()
    }


@app.get("/health")
async def health():
    """Health check for deployment platforms"""
    return {"status": "healthy"}


# =============================================================================
# SLACK ENDPOINTS
# =============================================================================

@app.post("/slack/events")
async def slack_events(request: Request):
    """Handle Slack events (mentions, DMs, etc.)"""
    return await slack_handler.handle(request)


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    """Handle Slack interactive components (buttons, modals)"""
    return await slack_handler.handle(request)


# =============================================================================
# DEBUG/ADMIN ENDPOINTS
# =============================================================================

@app.get("/api/stats")
async def api_stats():
    """Get bot statistics"""
    return await get_stats()


@app.get("/api/debug")
async def api_debug():
    """Debug endpoint to check paths and RAG status"""
    import os
    from pathlib import Path
    from src.ai import rag_pipeline
    from src.config import settings, PROJECT_ROOT
    
    # Check paths
    data_dir = Path(settings.data_dir)
    
    # List files in various locations
    cwd = os.getcwd()
    
    # Try to find data files
    possible_paths = [
        Path(settings.data_dir),
        Path("data"),
        Path("../data"),
        Path("/app/data"),
        PROJECT_ROOT / "data",
    ]
    
    found_files = {}
    for p in possible_paths:
        try:
            if p.exists():
                files = list(p.glob("*"))
                found_files[str(p)] = [str(f.name) for f in files]
            else:
                found_files[str(p)] = "PATH DOES NOT EXIST"
        except Exception as e:
            found_files[str(p)] = f"ERROR: {e}"
    
    # List root directory
    root_files = []
    try:
        root_files = os.listdir("/app") if os.path.exists("/app") else os.listdir(".")
    except Exception as e:
        root_files = [f"ERROR: {e}"]
    
    return {
        "current_working_directory": cwd,
        "settings_data_dir": settings.data_dir,
        "project_root": str(PROJECT_ROOT),
        "rag_loaded": rag_pipeline._loaded,
        "rag_chunks_count": len(rag_pipeline.chunks),
        "path_checks": found_files,
        "root_directory_files": root_files,
    }


@app.get("/api/search")
async def api_search(q: str, top_k: int = 5):
    """Search the knowledge base (debug)"""
    from src.ai import rag_pipeline
    
    results = rag_pipeline.search(q, top_k=top_k)
    
    return {
        "query": q,
        "results": [
            {
                "section": chunk.section,
                "source": chunk.source,
                "content": chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content,
                "score": float(score)
            }
            for chunk, score in results
        ]
    }


@app.post("/api/ask")
async def api_ask(question: str, user_name: str = "Test User"):
    """Ask Miss Minutes directly (debug)"""
    response, latency_ms = await ai_generator.generate(question, user_name)
    
    return {
        "question": question,
        "response": response,
        "latency_ms": latency_ms
    }


@app.get("/api/test-rag")
async def api_test_rag(q: str):
    """Test RAG context retrieval - shows exactly what Claude sees"""
    from src.ai.rag import rag_pipeline
    
    # Get context the same way generator does
    context = rag_pipeline.get_context(q)
    
    return {
        "query": q,
        "rag_loaded": rag_pipeline._loaded,
        "chunks_count": len(rag_pipeline.chunks),
        "context_length": len(context),
        "context_preview": context[:1000] if context else "EMPTY",
        "full_context": context
    }


@app.post("/api/test-reminder")
async def api_test_reminder(user_id: str, user_name: str = "Test User"):
    """Send a test reminder (debug)"""
    success = await reminder_scheduler.send_test_reminder(user_id, user_name)
    
    return {
        "status": "sent" if success else "failed",
        "user_id": user_id
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
