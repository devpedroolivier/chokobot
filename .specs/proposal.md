# Proposal: AI Agent Upgrade for Chokobot

## 1. Problem Statement
The current Chokobot WhatsApp assistant relies on rigid, state-based conversation flows (hardcoded IF/ELSE logic). This leads to:
- A frustrating user experience when customers want to make natural language requests (e.g., "I want a small chocolate cake with strawberry for Friday").
- Inability to easily correct or modify orders mid-conversation without restarting flows.
- High maintenance overhead for menu changes, as prices and items are hardcoded in the application logic (`precos.py`).
- Lack of intelligent handling for edge cases, FAQs, or ambiguities.

## 2. Objective
Upgrade the Chokobot application from a rule-based state machine to an intelligent, multi-agent AI system. We will leverage `openai-agents-python` to handle conversation orchestration and natural language understanding, while utilizing `Context7` concepts to decouple knowledge (menus, prices) from the source code.

## 3. Scope
- **In Scope:**
  - Replacing the rule-based router in `app/handler.py`.
  - Implementing an AI Agent Swarm (Router Agent, Order Agent, Support Agent) using `openai-agents-python`.
  - Creating a dynamic knowledge layer (RAG/Context7 style) for menus and FAQs.
  - Creating Tool/Function Calling interfaces for saving data to the existing SQLite database.
  - Maintaining the existing "Transfer to Human" (Atendimento) capability.
- **Out of Scope:**
  - Modifying the existing FastAPI endpoints for the Web Panel.
  - Changing the SQLite database schema (we will adapt the AI output to fit the current schema).

## 4. Success Criteria
- The bot can parse a complete cake order from a single natural language message.
- Users can modify their order conversationally.
- The bot successfully maps the NLP order into the exact `encomendas` SQLite structure.
- Hardcoded string menus are replaced by a knowledge base retrieval system.