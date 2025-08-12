// src/aiAgent.ts

interface MemoryInfo {
  should_save_memory: boolean;
  summary: string;
}

interface QueryResponse {
  response: string;
  memory: MemoryInfo;
}

interface CollaborativeResponse {
  response: string;
  routing_decision: string;
  needs_collaboration: boolean;
  validation_passed: boolean;
  validation_message: string;
  is_coding_request: boolean;
  success: boolean;
}

/**
 * Removes JSON memory blocks from the response text and logs the extracted JSON
 * @param responseText - The raw response from the backend
 * @returns Object containing cleaned text and extracted memory JSON
 */
function cleanResponseAndExtractMemory(responseText: string): { cleanedText: string; memoryJson: any } {
  // Pattern to match the JSON memory block
  const jsonPattern = /```json\s*\{\s*"should_save_memory"\s*:\s*(true|false)\s*,\s*"summary"\s*:\s*".*?"\s*\}\s*```/gs;

  let extractedJson = null;
  let cleanedText = responseText;

  // Find and extract the JSON block
  const match = responseText.match(jsonPattern);
  if (match) {
    try {
      // Extract just the JSON part (without the ```json wrapper)
      const jsonText = match[0].replace(/```json\s*/, '').replace(/\s*```$/, '');
      extractedJson = JSON.parse(jsonText);

      // Log the extracted JSON
      console.log('Extracted memory JSON:', extractedJson);

      // Remove the JSON block from the response
      cleanedText = responseText.replace(jsonPattern, '').trim();

      console.log('Cleaned response text:', cleanedText);
    } catch (parseError) {
      console.error('Failed to parse extracted JSON:', parseError);
    }
  }

  // Always remove any leftover code fences
  cleanedText = cleanedText.replace(/```/g, '').trim();

  return {
    cleanedText,
    memoryJson: extractedJson
  };
}

/**
 * Show a confirmation dialog for saving memory
 * @param summary - The summary that would be saved
 * @returns Promise resolving to true if user confirms, false otherwise
 */
async function showMemoryConfirmationDialog(summary: string): Promise<boolean> {
  return new Promise((resolve) => {
    // Create dialog elements
    const overlay = document.createElement('div');
    overlay.className = 'memory-dialog-overlay';

    const dialog = document.createElement('div');
    dialog.className = 'memory-dialog';

    dialog.innerHTML = `
      <div class="memory-dialog-header">
        <h3>Save Conversation Memory?</h3>
      </div>
      <div class="memory-dialog-content">
        <p>Thoth wants to remember this conversation for future reference:</p>
        <div class="memory-summary">${summary}</div>
        <p>This will help provide better assistance in future conversations.</p>
      </div>
      <div class="memory-dialog-actions">
        <button id="memory-cancel" class="memory-btn-cancel">Don't Save</button>
        <button id="memory-confirm" class="memory-btn-confirm">Save Memory</button>
      </div>
    `;

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Add event listeners
    const confirmBtn = dialog.querySelector('#memory-confirm') as HTMLButtonElement;
    const cancelBtn = dialog.querySelector('#memory-cancel') as HTMLButtonElement;

    confirmBtn.onclick = () => {
      document.body.removeChild(overlay);
      resolve(true);
    };

    cancelBtn.onclick = () => {
      document.body.removeChild(overlay);
      resolve(false);
    };

    // Close on overlay click
    overlay.onclick = (e) => {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
        resolve(false);
      }
    };
  });
}

/**
 * Store a memory summary in the vector database
 * @param summary - The conversation summary to store
 * @returns Promise resolving to success status
 */
async function storeMemory(summary: string): Promise<boolean> {
  try {
    const res = await fetch('http://localhost:8000/store_memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        summary,
        metadata: {
          timestamp: new Date().toISOString(),
          source: 'chat_conversation'
        }
      })
    });

    const data = await res.json();
    console.log('Memory storage result:', data);

    return data.success;
  } catch (error) {
    console.error('Error storing memory:', error);
    return false;
  }
}

export async function sendPromptWithMemory(prompt: string, chatHistory: string = "", signal?: AbortSignal, isCodingRequest: boolean = false): Promise<string> {
  try {
    console.log('Sending prompt with collaborative agent:', prompt, 'coding:', isCodingRequest);
    const res = await fetch('http://localhost:8000/collaborative', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        prompt,
        chat_history: chatHistory,
        is_coding_request: isCodingRequest
      }),
      signal
    });
    
    console.log('Response status:', res.status);
    const data: CollaborativeResponse = await res.json();
    console.log('Collaborative response data:', data);
    console.log('Routing decision:', data.routing_decision);
    console.log('Needs collaboration:', data.needs_collaboration);
    console.log('Is coding request:', data.is_coding_request);
    console.log('Validation passed:', data.validation_passed);
    console.log('Validation message:', data.validation_message);
    
    const responseText = data.response || 'No response.';
    
    // Show routing and validation information in console for debugging
    if (data.routing_decision) {
      console.log(`🤖 Agent routing: ${data.routing_decision}${data.needs_collaboration ? ' (collaborative)' : ''}`);
    }
    
    if (!data.validation_passed) {
      console.warn(`⚠️ Format validation failed: ${data.validation_message}`);
    }
    
    return responseText;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw err;
    }
    console.error('Error in sendPromptWithMemory:', err);
    return 'Error: ' + err.message;
  }
}

// Legacy function for backward compatibility
export async function sendPrompt(prompt: string): Promise<string> {
  return sendPromptWithMemory(prompt);
}
