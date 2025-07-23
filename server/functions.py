import os
import re  # used to strip out memory JSON blocks
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_agent import run_langchain_agent, thoth_agent

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str

class MemoryRequest(BaseModel):
    summary: str
    metadata: dict = None

class GeminiResponse(BaseModel):
    response: str

class MemoryResponse(BaseModel):
    success: bool
    message: str
    memory_id: str = None

class QueryWithMemoryRequest(BaseModel):
    prompt: str
    chat_history: str = ""

class QueryWithMemoryResponse(BaseModel):
    response: str
    memory: dict

@router.post("/generate", response_model=GeminiResponse)
async def generate_content(request: PromptRequest):
    """
    Generate content using LangChain agent with Gemini
    """
    try:
        print(f"Received user query: {request.prompt}")
        response_text = run_langchain_agent(request.prompt)
        # Strip out memory JSON block so frontend does not receive it
        pattern = r'```json\s*\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}\s*```'
        clean_text = re.sub(pattern, '', response_text, flags=re.DOTALL).strip()
        # Remove any leftover memory JSON blocks (not in code fences)
        clean_text = re.sub(r'\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}', '', clean_text, flags=re.DOTALL).strip()
        return GeminiResponse(response=clean_text)
    except Exception as e:
        print(f"Error in generate_content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate_with_memory", response_model=QueryWithMemoryResponse)
async def generate_with_memory(request: QueryWithMemoryRequest):
    """
    Generate content using LangChain agent and return memory information
    """
    try:
        print(f"Received user query with history: {request.prompt}")
        result = thoth_agent.process_query(request.prompt, request.chat_history)
        
        # Strip out memory JSON block from response text
        response_text = result["response"]
        pattern = r'```json\s*\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}\s*```'
        clean_text = re.sub(pattern, '', response_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}', '', clean_text, flags=re.DOTALL).strip()
        
        return QueryWithMemoryResponse(
            response=clean_text,
            memory=result["memory"]
        )
    except Exception as e:
        print(f"Error in generate_with_memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store_memory", response_model=MemoryResponse)
async def store_memory(request: MemoryRequest):
    """
    Store a conversation summary in the vector database
    """
    try:
        from vector_db import get_vector_db
        
        vector_db = get_vector_db()
        memory_id = vector_db.store_memory(request.summary, request.metadata)
        
        return MemoryResponse(
            success=True,
            message="Memory stored successfully",
            memory_id=memory_id
        )
    except Exception as e:
        print(f"Error storing memory: {e}")
        return MemoryResponse(
            success=False,
            message=f"Failed to store memory: {str(e)}"
        )
