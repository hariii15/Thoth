"""
Vector Database utilities for Pinecone integration
Handles embedding generation, storage, and retrieval of conversation memories
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import json

class VectorDBManager:
    def __init__(self, api_key: str, index_name: str = "thoth-memories"):
        """
        Initialize Pinecone vector database manager
        
        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index to use
        """
        self.api_key = api_key
        self.index_name = index_name
        self.dimension = 384  # all-MiniLM-L6-v2 embedding dimension
        
        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Create or connect to index
        self._setup_index()
    
    def _setup_index(self):
        """Create Pinecone index if it doesn't exist"""
        try:
            # Check if index exists
            existing_indexes = [index.name for index in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                print(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
                print(f"Index {self.index_name} created successfully")
            else:
                print(f"Using existing Pinecone index: {self.index_name}")
            
            # Connect to the index
            self.index = self.pc.Index(self.index_name)
            print(f"Connected to Pinecone index: {self.index_name}")
            
        except Exception as e:
            print(f"Error setting up Pinecone index: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using sentence-transformers
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values
        """
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def store_memory(self, conversation_summary: str, metadata: Optional[Dict] = None) -> str:
        """
        Store a conversation summary in the vector database
        
        Args:
            conversation_summary: Text summary of the conversation
            metadata: Optional metadata to store with the memory
            
        Returns:
            Unique ID of the stored memory
        """
        try:
            # Generate unique ID
            memory_id = str(uuid.uuid4())
            
            # Generate embedding
            embedding = self.generate_embedding(conversation_summary)
            
            # Prepare metadata
            memory_metadata = {
                "text": conversation_summary,
                "timestamp": datetime.now().isoformat(),
                "type": "conversation_summary"
            }
            
            if metadata:
                memory_metadata.update(metadata)
            
            # Store in Pinecone
            self.index.upsert(
                vectors=[{
                    "id": memory_id,
                    "values": embedding,
                    "metadata": memory_metadata
                }]
            )
            
            print(f"Stored memory with ID: {memory_id}")
            return memory_id
            
        except Exception as e:
            print(f"Error storing memory: {e}")
            raise
    
    def retrieve_relevant_memories(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories based on semantic similarity to query
        
        Args:
            query: Query text to find similar memories for
            top_k: Number of top similar memories to return
            
        Returns:
            List of relevant memories with their metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            # Format results
            memories = []
            for match in results.matches:
                memory = {
                    "id": match.id,
                    "score": float(match.score),
                    "text": match.metadata.get("text", ""),
                    "timestamp": match.metadata.get("timestamp", ""),
                    "metadata": match.metadata
                }
                memories.append(memory)
            
            print(f"Retrieved {len(memories)} relevant memories for query: {query[:50]}...")
            return memories
            
        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness
            }
        except Exception as e:
            print(f"Error getting memory stats: {e}")
            return {"error": str(e)}


# Global instance (will be initialized when needed)
vector_db_manager = None

def get_vector_db() -> VectorDBManager:
    """Get or initialize the global vector database manager"""
    global vector_db_manager
    
    if vector_db_manager is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key or api_key == "your-pinecone-api-key-here":
            raise ValueError("PINECONE_API_KEY not set in .env file. Please add your Pinecone API key.")
        
        vector_db_manager = VectorDBManager(api_key)
    
    return vector_db_manager
