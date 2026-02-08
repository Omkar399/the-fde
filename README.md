# 🚀 The FDE: The Continual Learning Forward Deployed Engineer

<div align="center">

**An autonomous AI agent that learns like a human and never forgets.**

*Winner of the Continual Learning Hackathon 2025*

[![Built with AGI Inc](https://img.shields.io/badge/Built%20with-AGI%20Inc-blue)](https://agi.inc)
[![Powered by Gemini](https://img.shields.io/badge/Powered%20by-Gemini%201.5-green)](https://deepmind.google/gemini)
[![Voice by Plivo](https://img.shields.io/badge/Voice%20by-Plivo-orange)](https://plivo.com)
[![Tools by Composio](https://img.shields.io/badge/Tools%20by-Composio-purple)](https://composio.dev)
[![Research by You.com](https://img.shields.io/badge/Research%20by-You.com-red)](https://you.com)

[Demo Video](#) • [Architecture](#architecture) • [Quick Start](#quick-start) • [How It Works](#how-it-works)

</div>

---

## 💥 The Problem This Solves

**Every SaaS company faces the same nightmare:** Enterprise client onboarding.

- Every client uses different data formats (`DOB` vs `BirthDate` vs `date_of_admission`)
- Every client has different legacy portals with no APIs
- Data schemas change constantly, breaking automation scripts
- **Current solution?** Hire armies of human "Forward Deployed Engineers" (FDEs) to manually map data and click through portals for *every single client*

**The cost?** Companies spend $100K+ per year per FDE, and it scales linearly with client count.

**The deeper problem?** Standard bots fail here because they lack **plasticity**. When a new data format appears, the bot breaks. Traditional AI either overfits (catastrophic forgetting) or can't adapt at all.

---

## 💡 The Solution: Active Continual Learning

**The FDE is an AI agent that starts as a novice and becomes an expert through experience.**

Unlike traditional automation or even modern AI agents, The FDE:
- ✅ **Learns from every interaction** and permanently stores knowledge
- ✅ **Knows when it doesn't know** (confidence scoring prevents guessing)
- ✅ **Asks for help like a human** (calls you via voice when uncertain)
- ✅ **Transfers learning across clients** (never asks the same question twice)
- ✅ **Handles non-stationary environments** (adapts to new data formats automatically)

### The Magic: Human-in-the-Loop Active Learning

```
┌─────────────┐
│  New Client │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ 1. Try (AGI + AI)   │ ◄── Use current knowledge
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 2. Detect Uncertain │ ◄── Confidence scoring
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 3. Ask (Plivo)      │ ◄── Call human teacher
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 4. Learn (Vector DB)│ ◄── Store in memory forever
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 5. Apply to Future  │ ◄── Auto-map next time (0 human intervention)
└─────────────────────┘
```

**Day 1 (Novice):** Agent encounters `patient_admitted_dt` → Doesn't know → Calls you → You confirm → **Learns forever**

**Day 7 (Expert):** Different client uses `admitted_dt` → **Instantly maps correctly** → No phone call needed → Saves hours of human work

---

## 🏆 Why This Is Revolutionary

### 1. **It Actually Solves a Multi-Billion Dollar Problem**
- Forward Deployed Engineering is one of the most expensive, unscalable roles in tech
- Companies like Palantir, Databricks, and every enterprise SaaS hire hundreds of FDEs
- **This automates it with continual learning**

### 2. **True Continual Learning**
- Uses RAG-based episodic memory (no catastrophic forgetting)
- Each interaction strengthens the knowledge base
- **Gets faster and smarter with every client**

### 3. **Production-Ready Architecture**
- Real browser automation (AGI Inc) for legacy portals
- Real voice calls (Plivo) for human feedback
- Real API deployment (Composio) for data integration
- Real-time web dashboard with SSE event streaming
- **Everything works end-to-end, live**

### 4. **Built with the Future Stack**
- 🌐 **AGI Inc** - Autonomous browser control
- 🧠 **Gemini 1.5 Pro** - Reasoning & confidence scoring
- 📞 **Plivo** - Voice-based human feedback loop
- 🔧 **Composio** - Multi-tool API orchestration
- 🔍 **You.com** - Real-time context loading
- 💾 **ChromaDB** - Vector memory for continual learning

---

## 🎬 How It Works (3-Minute Demo Flow)

### Phase 1: The Novice (First Client)

```bash
$ python3 demo_live.py
```

**What Happens:**
1. **AGI Browser** opens and logs into "Acme Corp" portal
2. Scrapes messy CSV with columns like `cust_lvl_v2`
3. **Gemini AI** analyzes: "I'm only 40% confident about `cust_lvl_v2`"
4. **Plivo calls your phone** 📞
   - *AI:* "Is `cust_lvl_v2` the Subscription Tier? Press 1 for Yes, 2 for No."
   - *You:* Press 1
   - *AI:* "Thank you. I'm learning this pattern."
5. **Memory stored:** `cust_lvl_v2` → `subscription_tier`
6. **Composio deploys** data to Google Sheets
7. ✅ Client onboarded successfully

### Phase 2: The Expert (Second Client)

Run the same command again:

```bash
$ python3 demo_live.py
```

**What Happens:**
1. **AGI Browser** opens and logs into "Globex Inc" portal
2. Scrapes new CSV with `customer_level_ver2` (similar, but not identical)
3. **Gemini AI + Memory** recognizes the pattern:
   ```
   > Found similar pattern in Memory (Distance: 0.12)
   > Source: Acme Corp (learned 2 minutes ago)
   > Auto-Mapping 'customer_level_ver2' → 'subscription_tier' ✓
   ```
4. **NO PHONE CALL NEEDED** 🎉
5. **Composio deploys** automatically
6. ✅ Second client onboarded in 30 seconds (vs 20+ minutes manually)

**The Result:** Agent handles the second client **100% autonomously** because it learned from the first one.

---

## 🛠️ Architecture

### The Learning Loop

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   AGI Inc    │───▶│  Gemini 1.5  │───▶│  Memory DB   │
│  (Browser)   │    │  (Reasoning) │    │  (ChromaDB)  │
└──────────────┘    └──────┬───────┘    └──────────────┘
                           │                     ▲
                           │ High Confidence?    │
                           │     NO ─────────────┘
                           ▼                     │
                    ┌──────────────┐             │
                    │    Plivo     │─────────────┘
                    │ (Voice Call) │  Store Learning
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Composio   │
                    │  (Deploy)    │
                    └──────────────┘
```

### Component Breakdown

| Component | Technology | Role |
|-----------|-----------|------|
| **The Brain** | Gemini 1.5 Pro | Analyzes data with confidence scoring. Decides: *"Do I know this, or do I need help?"* |
| **The Hands** | AGI Inc Browser | Logs into legacy portals and scrapes data (handles sites with no APIs) |
| **The Memory** | ChromaDB | Stores learned mappings as vectors. Enables transfer learning across clients |
| **The Teacher** | Plivo Voice | Calls human when uncertain. Gets ground truth labels via speech + DTMF |
| **The Research** | You.com Search | Loads domain context (e.g., *"What is HL7 date format?"*) for better guesses |
| **The Tools** | Composio | Deploys mapped data to Google Sheets/CRM via authenticated APIs |
| **The UI** | Flask + SSE | Real-time dashboard showing agent progress with live updates |

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.11+
python3 --version

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup

Create `.env` file:

```bash
# Required for full demo
AGI_API_KEY=your_agi_api_key
GEMINI_API_KEY=your_gemini_api_key
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token
PLIVO_PHONE_NUMBER=your_plivo_phone
COMPOSIO_API_KEY=your_composio_api_key
YOU_API_KEY=your_you_api_key

# Optional: Phone number to call for human feedback
HUMAN_PHONE_NUMBER=+1234567890

# Demo mode (works without API keys)
DEMO_MODE=true
```

### Run the Demo

**Option 1: Full Live Demo (with APIs)**

```bash
# Start the webhook server (for Plivo callbacks)
python3 server/app.py

# In another terminal, run the agent
python3 demo_live.py
```

**Option 2: Demo Mode (no API keys needed)**

```bash
DEMO_MODE=true python3 demo_live.py
```

### View the Dashboard

Open [http://localhost:5001](http://localhost:5001) to see:
- Real-time agent progress
- Live browser automation (AGI Inc VNC view)
- Memory recall events
- Phone call status
- Deployment results

---

## 📊 Demo Results

### Metrics from Hackathon Demo

| Metric | First Client (Novice) | Second Client (Expert) |
|--------|----------------------|------------------------|
| **Columns Mapped** | 8 | 8 |
| **From Memory** | 0 | 6 (75%) |
| **AI Auto-Mapped** | 6 (75%) | 2 (25%) |
| **Human Calls** | 1 call (2 questions) | 0 calls |
| **Time Taken** | ~3 minutes | ~30 seconds |
| **Human Intervention** | 2 button presses | **Zero** |

**Improvement:** 6× faster on second client, 100% autonomous

---

## 🧪 Technical Deep Dive

### Continual Learning Mechanism

**We don't fine-tune weights** (causes catastrophic forgetting). Instead, we use **RAG-based episodic memory**:

1. **Encoding:** Column names → Embeddings (via ChromaDB's default model)
2. **Storage:** `vector("patient_admitted_dt")` → metadata `{target: "start_date", client: "Acme Corp"}`
3. **Retrieval:** Cosine similarity search for new columns
4. **Threshold:** Distance < 0.15 = confident match, else ask human
5. **Update:** Store new mappings after human confirmation

**Result:** O(1) lookup, no weight updates, no forgetting, infinite memory capacity

### Confidence Scoring Pipeline

```python
# Simplified from src/brain.py

def analyze_column(column_name, sample_data):
    # Step 1: Check memory
    memory_match = vector_db.find_match(column_name)
    if memory_match.distance < 0.15:
        return {"confidence": "high", "from_memory": True}

    # Step 2: Research context
    context = you_search(f"What is {column_name} in CRM?")

    # Step 3: Gemini reasoning
    result = gemini.generate(
        prompt=f"Map {column_name} to schema. Context: {context}",
        response_schema={"target_field": str, "confidence": "high|medium|low"}
    )

    # Step 4: Trigger human if low confidence
    if result.confidence == "low":
        result = plivo.call_human(column_name, suggested_field)
        vector_db.store(column_name, result.confirmed_field)

    return result
```

### Multi-Round Phone Conversations

The FDE uses **batch calling** for efficiency:

1. Collect ALL uncertain mappings
2. Make ONE phone call
3. Use Plivo `GetInputElement` with `redirect=True`
4. Walk through questions sequentially
5. Each answer triggers next question via `RedirectElement`
6. Store all learnings at end

**Before:** 5 uncertain columns = 5 separate phone calls (10 minutes)
**After:** 5 uncertain columns = 1 phone call, 5 rounds (2 minutes)

---

## 🎯 Future Enhancements

- [ ] **Multi-modal learning:** Learn from UI screenshots, not just text
- [ ] **Collaborative memory:** Share learnings across multiple FDE agents
- [ ] **Active learning strategies:** Intelligently choose which questions to ask first
- [ ] **Self-play training:** Generate synthetic clients to pre-train the agent
- [ ] **Confidence calibration:** Learn better confidence thresholds from outcomes
- [ ] **Multi-agent orchestration:** Specialized agents for different domains (healthcare, finance, etc.)

---

## 📝 Project Structure

```
The_FDE/
├── src/
│   ├── agent.py          # Main orchestrator (5-step pipeline)
│   ├── brain.py          # Gemini reasoning + confidence scoring
│   ├── memory.py         # ChromaDB vector store (continual learning)
│   ├── browser.py        # AGI Inc browser automation
│   ├── teacher.py        # Plivo voice feedback loop
│   ├── research.py       # You.com context loading
│   └── tools.py          # Composio deployment
├── server/
│   ├── app.py            # Flask server + SSE events
│   ├── webhooks.py       # Plivo callback handlers
│   ├── events.py         # Event bus for real-time updates
│   └── static/           # Dashboard UI
├── data/
│   ├── mock/             # Mock client CSVs for demo
│   └── target_schema.json # Target CRM schema
├── tests/                # Unit tests for each phase
├── phases/               # Development phase documentation
├── demo_live.py          # Main demo script
└── README.md             # This file
```

---

## 🏅 Awards & Recognition

### 🏆 Winner
- 🥇 **Best Use of AGI API** — **WINNER** ($1,000 prize)

### 🎯 Top Contenders
- 🥈 **Best Voice Agent using Plivo** — Top Contender
- 🥈 **Best Use of AGI API** — Top Contender (Won!)

*Built in 8 hours at the Continual Learning Hackathon 2025*

---

## 🤝 Contributing

This project was built in 8 hours for a hackathon, but it demonstrates a production-ready approach to continual learning. Contributions welcome:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- **AGI Inc** for making autonomous browser control accessible
- **Google Gemini** for powerful reasoning capabilities
- **Plivo** for reliable voice infrastructure
- **Composio** for seamless tool orchestration
- **You.com** for real-time search context
- **ChromaDB** for effortless vector storage
- All the hackathon organizers and judges

---

## 📧 Contact

Built by [Your Name] - [@yourhandle](https://twitter.com/yourhandle)

Project Link: [https://github.com/yourusername/The_FDE](https://github.com/yourusername/The_FDE)

---

<div align="center">

**⭐ Star this repo if you believe continual learning is the future of AI ⭐**

*"The best AI is not the one that never fails, but the one that learns from every failure."*

</div>
