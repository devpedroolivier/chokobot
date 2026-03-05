# Implementation Tasks

## Phase 1: Preparation & Environment
- [x] 1.1 Review and approve `proposal.md` and `design.md`.
- [x] 1.2 Update `requirements.txt` with necessary AI libraries (e.g., `openai`, `pydantic`, `litellm` or specific `openai-agents-python` package).
- [x] 1.3 Set up environment variables (`.env`) for OpenAI API keys or Upstash/Context7 keys.

## Phase 2: Knowledge Base & Tools
- [x] 2.1 Extract hardcoded menus from `cafeteria.py` and `encomendas.py` into markdown/JSON knowledge files (to simulate Context7 retrieval).
- [x] 2.2 Create `app/ai/tools.py`.
- [x] 2.3 Implement the `create_cake_order` tool using strict Pydantic models that match the `encomendas` SQLite schema.
- [x] 2.4 Implement the `escalate_to_human` tool bridging to the existing Redis/In-memory state.

## Phase 3: Agent Configuration
- [x] 3.1 Create `app/ai/agents.py`.
- [x] 3.2 Define the `TriageAgent` with its system prompt and handoff capabilities.
- [x] 3.3 Define the `CakeOrderAgent` with strict instructions on required fields (Massa, Recheio, etc.) and access to the `create_cake_order` tool.
- [x] 3.4 Define the `KnowledgeAgent` with access to the extracted menu documents.

## Phase 4: Integration
- [x] 4.1 Modify `app/handler.py`.
- [x] 4.2 Replace the numbered IF/ELSE block with a call to the `openai-agents` runner, passing the user's phone number as the session ID.
- [x] 4.3 Ensure the "Atendimento Humano" override still functions perfectly before the AI is invoked.

## Phase 5: Testing & Deployment
- [ ] 5.1 Test a natural language full cake order flow locally.
- [ ] 5.2 Test order modification mid-conversation.
- [ ] 5.3 Test handoff to human.
- [ ] 5.4 Commit changes and rebuild Docker container.