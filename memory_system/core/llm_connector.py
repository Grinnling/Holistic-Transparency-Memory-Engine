#!/usr/bin/env python3
"""
LLM Connector - Flexible integration with TGI or LM Studio
Connects your memory system to actual LLM inference
"""

import requests
import json
import time
from typing import Dict, List, Optional
from enum import Enum

class LLMProvider(Enum):
    TGI = "tgi"
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"

class LLMConnector:
    def __init__(self, provider: LLMProvider = LLMProvider.LMSTUDIO, debug_mode: bool = False):
        self.provider = provider
        self.debug_mode = debug_mode
        
        # Configuration for different providers
        self.configs = {
            LLMProvider.TGI: {
                'base_url': 'http://localhost:8080',
                'endpoint': '/generate',
                'timeout': 300  # Increased for longer prompts
            },
            LLMProvider.LMSTUDIO: {
                'base_url': 'http://localhost:1234',
                'endpoint': '/v1/chat/completions',
                'timeout': 300  # Increased for longer prompts
            },
            LLMProvider.OLLAMA: {
                'base_url': 'http://localhost:11434',
                'endpoint': '/api/generate',
                'timeout': 300  # Increased for longer prompts
            }
        }
        
        self.config = self.configs[provider]
        self.is_connected = False
        
    def test_connection(self) -> bool:
        """Test if LLM service is accessible"""
        try:
            if self.provider == LLMProvider.LMSTUDIO:
                # LM Studio has a models endpoint
                response = requests.get(
                    f"{self.config['base_url']}/v1/models",
                    timeout=5
                )
                self.is_connected = response.status_code == 200
                if self.is_connected:
                    models = response.json().get('data', [])
                    if models:
                        print(f"✅ LM Studio connected - Model: {models[0].get('id', 'unknown')}")
                    else:
                        print("⚠️  LM Studio connected but no model loaded")
                        self.is_connected = False
                        
            elif self.provider == LLMProvider.TGI:
                # TGI has a health endpoint
                response = requests.get(
                    f"{self.config['base_url']}/health",
                    timeout=5
                )
                self.is_connected = response.status_code == 200
                if self.is_connected:
                    print("✅ TGI connected")
                    
            elif self.provider == LLMProvider.OLLAMA:
                # Ollama has a version endpoint
                response = requests.get(
                    f"{self.config['base_url']}/api/version",
                    timeout=5
                )
                self.is_connected = response.status_code == 200
                if self.is_connected:
                    print("✅ Ollama connected")
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ {self.provider.value} not accessible: {e}")
            self.is_connected = False
            
        return self.is_connected
    
    def generate_response(self,
                          user_message: str,
                          conversation_history: List[Dict] = None,
                          system_prompt: str = None,
                          skinflap_detection: Dict = None,
                          relevant_memories: List[Dict] = None) -> str:
        """Generate response from LLM with optional episodic memory context"""

        if not self.is_connected:
            if not self.test_connection():
                return "LLM service not available - using fallback response"

        try:
            if self.provider == LLMProvider.LMSTUDIO:
                return self._generate_lmstudio(user_message, conversation_history, system_prompt, skinflap_detection, relevant_memories)
            elif self.provider == LLMProvider.TGI:
                return self._generate_tgi(user_message, conversation_history, system_prompt, skinflap_detection, relevant_memories)
            elif self.provider == LLMProvider.OLLAMA:
                return self._generate_ollama(user_message, conversation_history, system_prompt, skinflap_detection, relevant_memories)

        except Exception as e:
            print(f"Error generating response: {e}")
            return f"Error connecting to {self.provider.value}: {str(e)}"
    
    def _generate_lmstudio(self, user_message: str, conversation_history: List[Dict], system_prompt: str, skinflap_detection: Dict = None, relevant_memories: List[Dict] = None) -> str:
        """Generate using LM Studio's OpenAI-compatible API"""

        messages = []

        # Build system prompt with optional skinflap detection info
        base_system_prompt = system_prompt if system_prompt else "You are a helpful AI assistant with memory capabilities. You can remember previous conversations and validate information for consistency."

        # Add skinflap detection context if available
        if skinflap_detection and skinflap_detection.get('detected_issues'):
            # Build pattern descriptions
            pattern_descriptions = []
            for issue in skinflap_detection['detected_issues']:
                pattern_descriptions.append(f"- {issue.get('pattern')}: {issue.get('description', 'Pattern detected')}")
            
            detection_context = f"""

QUERY ANALYSIS INFO:
The user's message has been analyzed for potential clarity issues:
- Issues detected: {len(skinflap_detection['detected_issues'])}
- Ready for processing: {skinflap_detection.get('ready_for_processing', True)}

Detected patterns:
{chr(10).join(pattern_descriptions)}

Instructions:
- You have permission to ask clarifying questions instead of guessing
- For multi-step requests with ambiguous references, prefer clarification over assumptions
- Check conversation history first - recent context often resolves "it", "that", "this"
- If you can reasonably infer the user's intent, proceed and mention your assumption
- When genuinely unclear, ask specific questions rather than generic "can you clarify?"
- Maintain natural conversation flow - don't be pedantic about minor ambiguities"""
            
            base_system_prompt += detection_context

        messages.append({"role": "system", "content": base_system_prompt})

        # Add relevant episodic memories BEFORE conversation history
        if relevant_memories and len(relevant_memories) > 0:
            memory_context_parts = [
                "RETRIEVED MEMORIES FROM YOUR EPISODIC MEMORY SYSTEM:",
                "",
                "These memories were retrieved from your episodic memory system.",
                "They're likely accurate, but memory retrieval isn't perfect.",
                "Treat them as high-confidence context unless they contradict more recent information.",
                "If something seems wrong or inconsistent, mention your uncertainty.",
                "This is your internal memory system - not external data you lack access to.",
                ""
            ]

            for i, memory in enumerate(relevant_memories, 1):
                # Episodic memories have full_conversation array with exchanges
                full_conversation = memory.get('full_conversation', [])

                # Process each exchange in the conversation
                for exchange in full_conversation:
                    user_input = exchange.get('user_input', exchange.get('user_message', ''))
                    assistant_response = exchange.get('assistant_response', exchange.get('assistant', ''))
                    timestamp = exchange.get('timestamp', memory.get('start_timestamp', 'unknown time'))

                    # Format memory snippet
                    memory_snippet = f"\n[MEMORY {i} - Retrieved from {timestamp}]"
                    if user_input:
                        memory_snippet += f"\nUser previously said: {user_input}"
                    if assistant_response:
                        memory_snippet += f"\nYou previously responded: {assistant_response}"

                    if user_input or assistant_response:  # Only add if we got something
                        memory_context_parts.append(memory_snippet)

            memory_context_parts.append("\n---")
            memory_context_parts.append("Use these memories to inform your response when relevant.")
            memory_context_parts.append("If the user asks about past conversations, you can reference what's here.")
            memory_context_parts.append("If memories conflict or seem off, acknowledge that uncertainty.")
            memory_context_parts.append("---")

            memory_context_str = "\n".join(memory_context_parts)
            print(f"DEBUG [llm_connector]: Injecting {len(relevant_memories)} memories into prompt")
            print(f"DEBUG [llm_connector]: Memory context preview: {memory_context_str[:200]}...")

            # Add as a system message
            messages.append({
                "role": "system",
                "content": memory_context_str
            })

        # Add conversation history
        if conversation_history:
            for exchange in conversation_history[-5:]:  # Last 5 exchanges
                if 'user' in exchange:
                    messages.append({"role": "user", "content": exchange['user']})
                if 'assistant' in exchange:
                    messages.append({"role": "assistant", "content": exchange['assistant']})
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        # Debug logging - show exactly what we're sending
        if self.debug_mode:
            print(f"\n🔍 DEBUG - Sending to {self.provider.value}:")
            print(f"📝 Messages count: {len(messages)}")
            for i, msg in enumerate(messages):
                role = msg['role']
                content = msg['content']
                
                # Show more content for system prompts with skinflap detection
                if role == 'system' and 'QUERY ANALYSIS INFO' in content:
                    print(f"   {i+1}. {role}: {content[:500]}...")
                    if len(content) > 500:
                        print("       [system prompt includes skinflap detection context]")
                else:
                    content = content[:100] + "..." if len(content) > 100 else content
                    print(f"   {i+1}. {role}: {content}")
            print("---")
        
        # Make request
        response = requests.post(
            f"{self.config['base_url']}{self.config['endpoint']}",
            json={
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,  # Increased for longer responses
                "stream": False
            },
            timeout=self.config['timeout']
        )
        
        if response.status_code == 200:
            result = response.json()
            model_response = result['choices'][0]['message']['content']
            if self.debug_mode:
                print(f"🤖 DEBUG - Model responded: {model_response[:200]}...")
                print("---\n")
            return model_response
        else:
            raise Exception(f"LM Studio returned {response.status_code}: {response.text}")
    
    def _generate_tgi(self, user_message: str, conversation_history: List[Dict], system_prompt: str, skinflap_detection: Dict = None, relevant_memories: List[Dict] = None) -> str:
        """Generate using TGI (Text Generation Inference)"""
        
        # Build prompt
        prompt_parts = []
        
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")
        
        if conversation_history:
            for exchange in conversation_history[-3:]:  # Last 3 exchanges
                if 'user' in exchange:
                    prompt_parts.append(f"User: {exchange['user']}")
                if 'assistant' in exchange:
                    prompt_parts.append(f"Assistant: {exchange['assistant']}")
        
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        
        full_prompt = "\n".join(prompt_parts)
        
        # Make request
        response = requests.post(
            f"{self.config['base_url']}{self.config['endpoint']}",
            json={
                "inputs": full_prompt,
                "parameters": {
                    "max_new_tokens": 2000,  # Increased for longer responses
                    "temperature": 0.7,
                    "do_sample": True,
                    "top_p": 0.95,
                    "stop": ["User:", "\n\n"]
                }
            },
            timeout=self.config['timeout']
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('generated_text', '').strip()
        else:
            raise Exception(f"TGI returned {response.status_code}: {response.text}")
    
    def _generate_ollama(self, user_message: str, conversation_history: List[Dict], system_prompt: str, skinflap_detection: Dict = None, relevant_memories: List[Dict] = None) -> str:
        """Generate using Ollama"""
        
        # Build prompt similar to TGI
        prompt_parts = []
        
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")
        
        if conversation_history:
            for exchange in conversation_history[-3:]:
                if 'user' in exchange:
                    prompt_parts.append(f"User: {exchange['user']}")
                if 'assistant' in exchange:
                    prompt_parts.append(f"Assistant: {exchange['assistant']}")
        
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        
        full_prompt = "\n".join(prompt_parts)
        
        # Make request
        response = requests.post(
            f"{self.config['base_url']}{self.config['endpoint']}",
            json={
                "model": "llama2",  # Change to your model
                "prompt": full_prompt,
                "stream": False
            },
            timeout=self.config['timeout']
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            raise Exception(f"Ollama returned {response.status_code}: {response.text}")
    
    def stream_response(self, user_message: str, conversation_history: List[Dict] = None):
        """Stream response token by token (for supported providers)"""
        # Implementation for streaming responses
        pass

class SmartLLMSelector:
    """Automatically detect and use available LLM"""
    
    @staticmethod
    def find_available_llm(debug_mode: bool = False) -> Optional[LLMConnector]:
        """Try each provider and return first available"""
        
        print("🔍 Searching for available LLM services...")
        
        # Try LM Studio first (most user-friendly)
        lm_connector = LLMConnector(LLMProvider.LMSTUDIO, debug_mode=debug_mode)
        if lm_connector.test_connection():
            return lm_connector
        
        # Try TGI
        tgi_connector = LLMConnector(LLMProvider.TGI, debug_mode=debug_mode)
        if tgi_connector.test_connection():
            return tgi_connector
        
        # Try Ollama
        ollama_connector = LLMConnector(LLMProvider.OLLAMA, debug_mode=debug_mode)
        if ollama_connector.test_connection():
            return ollama_connector
        
        print("❌ No LLM service found")
        print("\nTo use an LLM:")
        print("  - LM Studio: Start it and load a model")
        print("  - TGI: docker run --gpus all -p 8080:80 ghcr.io/huggingface/text-generation-inference:latest --model-id Qwen/Qwen2.5-0.5B-Instruct")
        print("  - Ollama: ollama run llama2")
        
        return None

# Quick test function
def test_llm_connection():
    """Test LLM connectivity"""
    
    # Auto-detect
    connector = SmartLLMSelector.find_available_llm()
    
    if connector:
        print(f"\n✅ Using {connector.provider.value}")
        
        # Test generation
        print("\n🧪 Testing generation...")
        response = connector.generate_response(
            "Hello! Can you help me test the memory system?",
            conversation_history=[],
            system_prompt="You are a helpful assistant testing the memory system integration."
        )
        
        print(f"\n📝 Response: {response}")
        return connector
    else:
        print("\n❌ No LLM available for testing")
        return None

if __name__ == "__main__":
    test_llm_connection()