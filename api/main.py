"""
AutoStack FastAPI Application

Main entry point for the AutoStack API server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings

# Import routes
from api.routes import projects, tasks, workflow, logs, health, auth
from api.routes import settings as settings_router

# Create FastAPI application
app = FastAPI(
    title="AutoStack API",
    description="Autonomous multi-agent software development system",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(workflow.router)
app.include_router(tasks.router)
app.include_router(logs.router)
app.include_router(health.router)
app.include_router(settings_router.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AutoStack API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


def main():
    """Main entry point for running the API server"""
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()