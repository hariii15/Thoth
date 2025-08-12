import os
import re  # used to strip out memory JSON blocks
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_agent import run_langchain_agent, thoth_agent
from collaborative_agent import run_collaborative_agent, collaborative_system

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

class QueryWithCodingRequest(BaseModel):
    prompt: str
    chat_history: str = ""
    is_coding_request: bool = False

class CollaborativeResponse(BaseModel):
    response: str
    routing_decision: str
    needs_collaboration: bool
    validation_passed: bool
    validation_message: str
    is_coding_request: bool
    success: bool

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

@router.post("/collaborative", response_model=CollaborativeResponse)
async def collaborative_query(request: QueryWithCodingRequest):
    """
    Process queries using the collaborative agent system with LangGraph
    This intelligently routes between Thoth, GitHub, and Coding agents based on query content
    Includes validation for GitHub agent responses to ensure proper JSON format
    """
    try:
        print(f"Received collaborative query: {request.prompt} (coding: {request.is_coding_request})")
        result = collaborative_system.process_query(
            request.prompt, 
            request.chat_history, 
            request.is_coding_request
        )
        
        # Strip out memory JSON blocks from response
        response_text = result["response"]
        pattern = r'```json\s*\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}\s*```'
        clean_text = re.sub(pattern, '', response_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'\{\s*"should_save_memory"\s*:\s*(?:true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}', '', clean_text, flags=re.DOTALL).strip()
        
        return CollaborativeResponse(
            response=clean_text,
            routing_decision=result["routing_decision"],
            needs_collaboration=result["needs_collaboration"],
            validation_passed=result.get("validation_passed", True),
            validation_message=result.get("validation_message", ""),
            is_coding_request=result.get("is_coding_request", False),
            success=result["success"]
        )
    except Exception as e:
        print(f"Error in collaborative_query: {e}")
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
