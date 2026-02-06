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

console = Console()

SYSTEM_INSTRUCTION = """You are an expert data mapping agent. Your job is to map source CSV column names to a target CRM schema.

For each source column, you must:
1. Analyze the column name, sample values, and any provided context
2. Determine which target schema field it maps to
3. Rate your confidence: "high" (>90% sure), "medium" (50-90%), or "low" (<50%)

Be confident in your mappings. Common abbreviations (e.g. cust=customer, nm=name, dt=date, addr=address, cd=code, flg=flag, bal=balance, ts=timestamp) are well-known patterns — rate these as "high" confidence.
Only rate a column "low" if the name is truly ambiguous and you cannot determine the target field with reasonable certainty, such as columns with opaque internal codes or version suffixes that change the meaning.

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
        for col in columns:
            match = self._memory.find_match(col)
            if match:
                console.print(
                    f"  [green]Memory match:[/green] '{col}' -> '{match['target_field']}' "
                    f"(distance: {match['distance']:.3f}, learned from {match['client_name']})"
                )
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
        research_context = ""
        for col in unknown_columns[:3]:  # Limit API calls
            ctx = self._research.get_column_context(col)
            if ctx:
                research_context += f"\nContext for '{col}': {ctx}\n"

        # Step 3: Use Gemini to reason
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

Map each source column to the most likely target field. Be confident — common abbreviations and naming patterns should be rated "high".
Only rate a column "low" if it is truly ambiguous and the target field cannot be determined with reasonable certainty."""

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
            "cust_nm": ("full_name", "high"),
            "full_name": ("full_name", "high"),
            "cust_lvl_v2": ("subscription_tier", "low"),
            "customer_level_ver2": ("subscription_tier", "high"),
            "signup_dt": ("signup_date", "high"),
            "registration_date": ("signup_date", "high"),
            "email_addr": ("email", "high"),
            "contact_email": ("email", "high"),
            "phone_num": ("phone", "high"),
            "mobile": ("phone", "high"),
            "addr_line1": ("address", "high"),
            "street_address": ("address", "high"),
            "city_nm": ("city", "high"),
            "city": ("city", "high"),
            "st_cd": ("state", "high"),
            "state_code": ("state", "high"),
            "zip_cd": ("zip_code", "high"),
            "postal_code": ("zip_code", "high"),
            "dob": ("date_of_birth", "high"),
            "date_of_birth": ("date_of_birth", "high"),
            "acct_bal": ("account_balance", "high"),
            "balance_usd": ("account_balance", "high"),
            "last_login_ts": ("last_login", "high"),
            "last_activity": ("last_login", "high"),
            "is_active_flg": ("is_active", "high"),
            "status": ("is_active", "high"),
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
