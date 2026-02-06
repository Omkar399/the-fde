# Phase 4: Orchestrator & Demo (Hour 4: 2:30 PM - 4:30 PM)

## Goal
Wire everything together into the main agent loop and polish for the 3-minute demo.

## Tasks

### 4.1 Main Agent Loop (`src/agent.py`)
- [x] Orchestrate the full pipeline:
  1. Browser fetches data from client portal
  2. Brain analyzes + maps columns with confidence
  3. High confidence -> auto-map
  4. Low confidence -> call human via Plivo
  5. Store new mappings in vector memory
  6. Execute deployment via Composio
- [x] Rich terminal output showing each step

### 4.2 Demo Runner (`run_demo.py`)
- [x] Phase 1 (Novice): Run agent on Client A
  - Shows browser scraping
  - Shows Gemini reasoning
  - Triggers Plivo call for uncertain columns
  - Stores learned mappings
- [x] Phase 2 (Expert): Run agent on Client B
  - Shows browser scraping
  - Shows memory match (no call needed!)
  - Auto-maps and deploys
- [x] Beautiful terminal UI with Rich

### 4.3 Polish
- [x] Error handling and graceful fallbacks
- [x] Demo mode (skip real API calls, use mocks)
- [x] README with setup instructions

## Demo Flow (3 minutes)
```
[0:00] "This is The FDE - a continual learning agent"
[0:15] Trigger Client A onboarding
[0:30] Browser opens, scrapes CSV (AGI Inc)
[0:45] Gemini analyzes - flags uncertain column
[1:00] Phone rings on stage! (Plivo)
[1:15] Human confirms mapping
[1:30] Agent learns, deploys via Composio
[1:45] "Now watch what happens with Client B..."
[2:00] Trigger Client B onboarding
[2:15] Browser scrapes new CSV
[2:30] Memory match found! No call needed!
[2:45] Auto-deploy. "The FDE just learned."
[3:00] Show memory growth visualization
```

## Validation
- Full end-to-end run with `python run_demo.py`
- Demo mode works without any API keys: `DEMO_MODE=true python run_demo.py`
