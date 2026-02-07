# The FDE -- The Continual Learning Forward Deployed Engineer

![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

An autonomous agent that starts as a **novice** and becomes an **expert** by learning from each client data onboarding. It uses vector memory (ChromaDB) for continual learning, real phone calls (Plivo) for human-in-the-loop feedback, AI reasoning (Google Gemini) with web research (You.com) for column analysis, browser automation (AGI Inc) to scrape client portals, and tool execution (Composio) to deploy transformed data -- all orchestrated through a real-time dashboard powered by Flask and Server-Sent Events.

---

## Architecture

```
+-------------------------------------------------------------+
|                      THE FDE AGENT                          |
+-------------------------------------------------------------+
|                                                             |
|  Browser (AGI Inc)  -> Scrape client portal data            |
|       |                                                     |
|  Brain (Gemini)     -> Analyze columns, score confidence    |
|       |                                                     |
|  Research (You.com) -> Domain context for unknowns          |
|       |                                                     |
|  Teacher (Plivo)    -> Call human when uncertain             |
|       |                                                     |
|  Memory (ChromaDB)  -> Store learned mappings as vectors    |
|       |                                                     |
|  Tools (Composio)   -> Deploy transformed data              |
|                                                             |
|  +--------------------------------------+                   |
|  |  Dashboard (Flask + SSE)             |                   |
|  |  Real-time pipeline visualization    |                   |
|  +--------------------------------------+                   |
+-------------------------------------------------------------+

CONTINUAL LEARNING: Novice ----------> Expert
   Client A        Client B        Client C
   (Many calls)    (Fewer calls)   (Zero calls)
```

---

## Sponsor Stack

| Sponsor | Role |
|---------|------|
| **Google Gemini** | AI reasoning engine for column analysis and confidence scoring |
| **AGI Inc** | Browser automation agent for scraping enterprise client portals |
| **You.com** | Search API providing domain context for ambiguous column names |
| **Plivo** | Voice calls enabling human-in-the-loop confirmation when uncertain |
| **Composio** | Tool execution framework for deploying mapped data to Google Sheets |

---

## Key Features

- **Continual Learning** -- Vector memory (ChromaDB) stores every learned column mapping. Knowledge from Client A transfers directly to Client B, reducing human intervention to zero over time.
- **Human-in-the-Loop with Real Phone Calls** -- When the agent is uncertain, it places an actual phone call via Plivo, speaks the mapping question, and collects DTMF confirmation. Not a chatbot -- a real voice call.
- **Data Transformation with Type Coercion** -- Boolean normalization (yes/no/true/false/1/0), date format detection and standardization, numeric parsing, and field-level validation before deployment.
- **Real-Time Dashboard** -- A live Flask dashboard streams pipeline events via Server-Sent Events. Watch the agent think, recall from memory, place calls, and deploy data in real time.
- **3-Client Demo** -- Three mock enterprise portals (Acme Corp, Globex Inc, Initech Ltd) with progressively different column naming conventions demonstrate the full novice-to-expert learning curve.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/your-org/the-fde.git
cd the-fde
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (or skip for demo mode)

# Run demo (no API keys needed)
python run_demo.py --demo-mode --reset

# Run with live dashboard
python -m server.webhooks &   # Start server on port 5001
python run_demo.py --reset    # Open http://localhost:5001/dashboard
```

---

## Demo Modes

| Flag | Description |
|------|-------------|
| `--demo-mode` | Uses mock APIs -- no API keys required. Perfect for local testing. |
| `--reset` | Clears vector memory for a fresh start. Shows the full novice-to-expert arc. |
| `--auto` | Auto-pacing for hackathon presentations (approximately 3 minutes end to end). |

Combine flags as needed:

```bash
python run_demo.py --demo-mode --reset --auto
```

---

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Lint check
ruff check src/ tests/ server/
```

---

## Project Structure

```
the-fde/
  src/
    agent.py          # Main orchestrator -- runs the 5-step pipeline
    brain.py          # Gemini-powered reasoning with confidence scoring
    browser.py        # AGI Inc browser automation for portal scraping
    memory.py         # ChromaDB vector store for continual learning
    research.py       # You.com search API for domain context
    teacher.py        # Plivo voice calls for human-in-the-loop
    tools.py          # Composio tool execution for deployment
    config.py         # Centralized configuration and environment
  server/
    webhooks.py       # Flask server: portals, dashboard, Plivo webhooks
    events.py         # SSE event bus for real-time streaming
    templates/        # HTML templates for portals and dashboard
    static/           # CSS and JS assets
  data/
    mock/             # Mock CSV files for each client portal
    target_schema.json# Target CRM schema definition
    memory/           # ChromaDB persistent storage (auto-created)
  tests/              # Pytest suite covering all phases
  run_demo.py         # Demo entry point
  requirements.txt    # Python dependencies
```

---

## How It Works

The FDE operates on a simple but powerful loop:

**1. Scrape and Analyze** -- The browser agent logs into a client's enterprise portal, extracts CSV data, and hands it to the Gemini brain. The brain checks vector memory for previously learned mappings, queries You.com for domain context on unknowns, then scores every column mapping with a confidence level.

**2. Learn from Humans** -- For any mapping below the confidence threshold, the agent places a real phone call to a human engineer via Plivo. The human presses 1 to confirm or 2 to reject. Every confirmed mapping is stored in ChromaDB as a vector embedding, growing the agent's knowledge base.

**3. Deploy and Remember** -- Confirmed mappings are deployed to Google Sheets via Composio with full type coercion (booleans, dates, numbers). The next client benefits from everything learned before -- fewer calls, faster onboarding, and eventually zero human intervention.

The result: an agent that genuinely gets smarter with each client it onboards.
