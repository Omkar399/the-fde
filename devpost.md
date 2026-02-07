# The FDE: The AI Forward Deployed Engineer

## Inspiration
Data onboarding is the bottleneck of enterprise software. Every time a new client signs up, a Forward Deployed Engineer (FDE) has to manually scrape their legacy portals, decipher cryptic column names (like `cust_lvl_v2` or `acct_bal`), map them to the platform's schema, and write transformation scripts. It's tedious, error-prone, and unscalable.

We asked: **What if we could clone the best FDE?** An agent that scrapes, thinks, remembers past mappings, and even calls you on the phone when it's confused—just like a real engineer.

## Architecture
We built a modular agentic architecture centered around the `FDEAgent` orchestrator.

```mermaid
graph TD
    User[Legacy Client Portal] -->|Scrapes CSV| Browser[AGI Browser Agent]
    Browser -->|Raw Columns| Orchestrator[FDE Orchestrator]
    
    subgraph "The Brain (Reasoning Loop)"
        Orchestrator -->|Query| Memory[(ChromaDB Memory)]
        Memory -->|Similar Mappings| Orchestrator
        Orchestrator -->|Unknown Terms| Research[You.com Search]
        Research -->|Context| Orchestrator
        Orchestrator -->|Context + Schema| Gemini[Gemini 1.5 Pro]
        Gemini -->|Confidence Scores| Orchestrator
    end
    
    Orchestrator -->|Low Confidence?| Teacher[Plivo Voice Agent]
    Teacher -->|Phone Call| Human[Human Engineer]
    Human -->|Voice Confirmation| Teacher
    Teacher -->|Verified Mapping| Orchestrator
    
    Orchestrator -->|Verified Data| Tools[Composio Toolset]
    Tools -->|Insert Rows| SaaS[Target SaaS (e.g. Google Sheets)]
```

## What it does
**The FDE** is a continual learning agent that fully automates client data onboarding.

1.  **Scrapes Data:** Logs into client portals and extracts raw data using an autonomous browser agent.
2.  **Analyzes & Maps:** Uses **Gemini 1.5 Pro** (Brain) and **You.com** (Research) to understand what the data means. It doesn't just guess; it researches industry terms to make informed decisions.
3.  **Remembers:** Uses **ChromaDB** (Memory) to recall how it mapped similar columns for previous clients. It gets smarter with every onboarding, using vector similarity to match `cust_id` (new) to `Customer ID` (learned).
4.  **Asks for Help:** If confidence is low, it uses **Plivo** (Teacher) to **call the human operator**, explain the ambiguity, and get a verbal confirmation via keypad input.
5.  **Deploys:** Once mapped, it uses **Composio** to transform and push the clean data directly into the target system (e.g., Google Sheets, Salesforce).

## How we built it
The system is built in Python with a modular design:

*   **The Brain (`src/brain.py`):** Powered by **Gemini 1.5 Pro**. It takes the source columns, target schema, and research context to generate mapping JSON with confidence scores.
*   **The Researcher (`src/research.py`):** Uses the **You.com Search API** to fetch definitions for obscure acronyms (e.g., "What does 'cust_lvl_v2' mean in CRM data?"). This context is fed into the LLM prompt.
*   **The Memory (`src/memory.py`):** A **ChromaDB** vector store that indexes past successful mappings. It uses cosine similarity to find relevant past decisions, allowing the agent to learn from experience.
*   **The Teacher (`src/teacher.py`):** A **Plivo** voice integration. When the agent is uncertain, it triggers a real phone call to the engineer. The human's keypad response (1 for Yes, 2 for No) is captured via webhook and fed back into the decision loop.
*   **The Hands (`src/tools.py`):** Uses **Composio** to execute the final data transfer. It handles authentication and API calls to external SaaS tools like Google Sheets.
*   **The Browser (`src/browser.py`):** An automated scraping agent (using AGI Inc API) that navigates complex portals to extract data.
*   **Interface:** A rich CLI for developer visibility and a Flask-based real-time dashboard (`server/`) for monitoring the agent's progress.

## Challenges we ran into
*   **Ambiguity in Data:** "Active" could mean a boolean `1/0`, `Y/N`, or a status string. We solved this by adding the **Research** module to look up context, rather than just relying on the LLM's training data.
*   **Voice Latency:** Making the AI phone call feel natural was tricky. We optimized the Plivo integration to ensure the agent speaks concisely and understands user intent quickly.
*   **Orchestration:** Coordinating 5 distinct "brains" (Scraper, LLM, Memory, Voice, Deployment) required a robust state machine to prevent race conditions and ensure data integrity.
*   **Vector Search Tuning:** Initially, simple string matching wasn't enough. We had to tune ChromaDB's embedding queries to correctly match semantically similar but syntactically different column names.

## Accomplishments that we're proud of
*   **True Continual Learning:** The agent literally gets faster and cheaper to run over time as it builds its memory of common data patterns.
*   **Voice-First Human-in-the-Loop:** Instead of a boring notification, the agent calls you. It feels like working with a real colleague.
*   **End-to-End Automation:** From a raw login URL to a populated database without writing a single line of Python for the specific client.
*   **Production-Ready Architecture:** The modular design allows us to swap out components (e.g., switch LLMs or vector stores) easily.

## What we learned
*   **Context is King:** LLMs are good, but LLMs with web search (You.com) and memory (ChromaDB) are superhuman at specific tasks like schema mapping.
*   **Agents need Tools:** Composio made the final deployment step trivial, allowing us to focus on the "thinking" part of the agent.
*   **Human-in-the-Loop is Critical:** AI isn't perfect. Providing a seamless fallback to human judgment (via voice) builds trust and reliability.

## What's next for The FDE
*   **Complex Transformations:** Handling data cleaning logic (e.g., formatting dates, parsing addresses) using generated code.
*   **More Integrations:** Adding support for Salesforce, HubSpot, and SQL databases via Composio.
*   **Multi-Modal Inputs:** Allowing the agent to "read" PDF contracts or architecture diagrams to understand the data better.
*   **Self-Correction:** Enabling the agent to detect deployment errors and attempt fixes automatically.
