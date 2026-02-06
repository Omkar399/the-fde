"""Gemini Brain - The FDE's reasoning and confidence scoring engine.

Uses Google Gemini to analyze CSV columns and attempt to map them
to the target schema with confidence scores.
"""

import json
from google import genai
from google.genai import types
from rich.console import Console

from src.config import Config
from src.memory import MemoryStore
from src.research import ResearchEngine
from server.events import emit_event

console = Console()

SYSTEM_INSTRUCTION = """You are an expert data mapping agent. Your job is to map source CSV column names to a target CRM schema.

For each source column, you must:
1. Analyze the column name, sample values, and any provided context
2. Determine which target schema field it maps to
3. Rate your confidence: "high" (>90% sure), "medium" (50-90%), or "low" (<50%)

Be conservative with confidence. If a column name is abbreviated, ambiguous, or uses non-standard naming, rate it as "low" confidence.

Respond ONLY with valid JSON matching the requested schema."""

MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_column": {"type": "string"},
                    "target_field": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["source_column", "target_field", "confidence", "reasoning"],
            },
        }
    },
    "required": ["mappings"],
}


class Brain:
    """Gemini-powered reasoning engine with confidence scoring."""

    def __init__(self, memory: MemoryStore, research: ResearchEngine):
        self._memory = memory
        self._research = research
        if not Config.DEMO_MODE:
            self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
        else:
            self._client = None

    def analyze_columns(
        self, columns: list[str], sample_data: dict[str, list[str]], target_schema: dict
    ) -> list[dict]:
        """Analyze CSV columns and return mapping suggestions with confidence.

        Steps:
        1. Check vector memory for known mappings
        2. Use You.com for context on unknown columns
        3. Use Gemini to reason about the rest

        Returns list of {source_column, target_field, confidence, reasoning, from_memory}
        """
        results = []
        unknown_columns = []

        # Step 1: Check memory for each column
        emit_event("brain_thought", {"thought": "Scanning vector memory for known patterns...", "confidence": 10})
        for col in columns:
            match = self._memory.find_match(col)
            if match:
                console.print(
                    f"  [green]Memory match:[/green] '{col}' -> '{match['target_field']}' "
                    f"(distance: {match['distance']:.3f}, learned from {match['client_name']})"
                )
                emit_event("brain_thought", {"thought": f"Memory HIT: '{col}' matches known pattern", "confidence": 95})
                results.append({
                    "source_column": col,
                    "target_field": match["target_field"],
                    "confidence": "high",
                    "reasoning": f"Found in memory from {match['client_name']} (distance: {match['distance']:.3f})",
                    "from_memory": True,
                })
            else:
                unknown_columns.append(col)

        if not unknown_columns:
            return results

        # Step 2: Research context for unknown columns
        console.print(f"  [blue]Researching {len(unknown_columns)} unknown columns...[/blue]")
        emit_event("brain_thought", {"thought": f"Researching {len(unknown_columns)} unknown columns via You.com API...", "confidence": 30})
        
        research_context = ""
        for col in unknown_columns[:3]:  # Limit API calls
            ctx = self._research.get_column_context(col)
            if ctx:
                emit_event("brain_thought", {"thought": f"Context found for '{col}'", "confidence": 45})
                research_context += f"\nContext for '{col}': {ctx}\n"

        # Step 3: Use Gemini to reason
        emit_event("brain_thought", {"thought": "Gemini 1.5 Pro: Reasoning about mappings...", "confidence": 60})
        gemini_results = self._gemini_analyze(
            unknown_columns, sample_data, target_schema, research_context
        )
        for r in gemini_results:
            r["from_memory"] = False
        results.extend(gemini_results)

        return results

    def _gemini_analyze(
        self,
        columns: list[str],
        sample_data: dict[str, list[str]],
        target_schema: dict,
        research_context: str,
    ) -> list[dict]:
        """Use Gemini to analyze columns and produce mappings."""
        target_fields = list(target_schema.get("fields", {}).keys())
        target_desc = json.dumps(target_schema.get("fields", {}), indent=2)

        # Build sample data preview
        samples_text = ""
        for col in columns:
            if col in sample_data:
                samples_text += f"  {col}: {sample_data[col][:3]}\n"

        prompt = f"""Analyze these source CSV columns and map them to the target schema.

SOURCE COLUMNS: {columns}

SAMPLE DATA:
{samples_text}

TARGET SCHEMA FIELDS: {target_fields}

TARGET FIELD DESCRIPTIONS:
{target_desc}

RESEARCH CONTEXT:
{research_context if research_context else "No additional context available."}

Map each source column to the most likely target field. Be CONSERVATIVE with confidence ratings.
Columns with abbreviations, version numbers, or non-standard names should be rated "low" confidence."""

        if Config.DEMO_MODE:
            return self._mock_analyze(columns, target_schema)

        try:
            response = self._client.models.generate_content(
                model=Config.GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=MAPPING_SCHEMA,
                    temperature=0.1,
                ),
                contents=prompt,
            )
            data = json.loads(response.text)
            return data.get("mappings", [])

        except Exception as e:
            console.print(f"  [red]Gemini error: {e}[/red]")
            return self._mock_analyze(columns, target_schema)

    def _mock_analyze(self, columns: list[str], target_schema: dict) -> list[dict]:
        """Fallback mock analysis for demo mode."""
        known_mappings = {
            "cust_id": ("customer_id", "high"),
            "customer_id": ("customer_id", "high"),
            "cust_nm": ("full_name", "medium"),
            "full_name": ("full_name", "high"),
            "cust_lvl_v2": ("subscription_tier", "low"),
            "customer_level_ver2": ("subscription_tier", "low"),
            "signup_dt": ("signup_date", "medium"),
            "registration_date": ("signup_date", "high"),
            "email_addr": ("email", "high"),
            "contact_email": ("email", "high"),
            "phone_num": ("phone", "high"),
            "mobile": ("phone", "high"),
            "addr_line1": ("address", "medium"),
            "street_address": ("address", "high"),
            "city_nm": ("city", "medium"),
            "city": ("city", "high"),
            "st_cd": ("state", "medium"),
            "state_code": ("state", "high"),
            "zip_cd": ("zip_code", "medium"),
            "postal_code": ("zip_code", "high"),
            "dob": ("date_of_birth", "medium"),
            "date_of_birth": ("date_of_birth", "high"),
            "acct_bal": ("account_balance", "medium"),
            "balance_usd": ("account_balance", "high"),
            "last_login_ts": ("last_login", "medium"),
            "last_activity": ("last_login", "medium"),
            "is_active_flg": ("is_active", "low"),
            "status": ("is_active", "medium"),
        }
        results = []
        for col in columns:
            if col in known_mappings:
                target, conf = known_mappings[col]
                results.append({
                    "source_column": col,
                    "target_field": target,
                    "confidence": conf,
                    "reasoning": f"Pattern match: '{col}' -> '{target}'",
                })
            else:
                results.append({
                    "source_column": col,
                    "target_field": "unknown",
                    "confidence": "low",
                    "reasoning": f"No known mapping for '{col}'",
                })
        return results
