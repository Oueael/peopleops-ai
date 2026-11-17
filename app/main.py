from fastapi import FastAPI

app = FastAPI(
    title="PeopleOps AI Assistant",
    description="An AI-powered employee onboarding and policy assistant",
    version="0.1.0"
)


@app.get("/")
async def root():
    return {
        "application": "PeopleOps AI Assistant",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }