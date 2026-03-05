# Technical Design: Multi-Agent AI System

## 1. Architecture Overview
We will transition from a Redis/In-memory state machine to an LLM-driven session. The architecture will be based on the Agent/Handoff pattern provided by the `openai-agents-python` SDK.

## 2. Components

### A. The Agent Swarm
- **TriageAgent (Router):** The entry point. Analyzes the user's intent and routes the conversation to a specialized agent.
- **CakeOrderAgent:** Specialized in the complex flow of custom cakes (Massa, Recheio, Mousse, Adicional, Tamanho). It will use strict Pydantic schemas to ensure all required data is collected before finalizing.
- **CafeteriaAgent:** Handles ready-to-eat items, coffees, and Easter specials.
- **KnowledgeAgent:** Uses RAG/Context retrieval to answer FAQs (store hours, delivery zones, generic questions).

### B. Tool Functions (Function Calling)
Agents will interact with the system via specific Python tools:
- `get_menu(category: str)`: Fetches dynamic menu context (simulating Context7).
- `create_cake_order(order_details: CakeOrderSchema)`: Injects the validated order into the SQLite database.
- `escalate_to_human(reason: str)`: Triggers the existing `estados_atendimento` block.

### C. State Management
The `openai-agents` SDK handles message history inherently. We will deprecate `ConversationStateStore` for standard conversational flows, retaining it only for the global "Is Human Responding?" flag.

## 3. Data Flow
1. User sends WhatsApp message -> Webhook -> `app/handler.py`.
2. `handler.py` checks if the user is in "human mode". If not, it passes the message to the `openai-agents` runtime.
3. `TriageAgent` processes history and current message.
4. If an order is complete, an Agent calls the `create_cake_order` tool.
5. The tool executes the SQLite insert, and the Agent responds with a natural language confirmation.

## 4. Dependencies
- `openai-agents-python` (or equivalent LiteLLM + Pydantic AI setup based on final selection).
- `pydantic` (for strict tool schemas).