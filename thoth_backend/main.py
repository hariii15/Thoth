from fastapi import FastAPI
import uvicorn
from functions import router
from fastapi.middleware.cors import CORSMiddleware


# Create FastAPI instance
app = FastAPI(
    title="Thoth Backend API",
    description="A RAG system with web search using Tavily API and Pinecone vector DB",
    version="1.0.0" 
)

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Or specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the router from functions.py
app.include_router(router)

# Basic hello world route
@app.get("/")
async def root():
    return {"message": "Hello World! Thoth Backend is running successfully!"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "thoth-backend"}

# Run the application
if __name__ == "__main__":  
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  
        port=8000, 
        reload=True  # Enable auto-reload during development
    )