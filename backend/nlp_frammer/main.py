# main.py
# Interactive test harness — run queries from the terminal.
#
# Usage:
#   python main.py
#   python main.py --debug     # shows token count + raw Gemini response


import sys
import os
import json
from dotenv import load_dotenv


load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))


from nlp.engine import query


DEBUG = "--debug" in sys.argv


print("━" * 60)
print("  Frammer NLP Engine — Interactive Test")
print("  Type your question. Ctrl+C to exit.")
print("━" * 60)


while True:
    try:
        text = input("\n❓ ").strip()
        if not text:
            continue

        result = query(text, debug=DEBUG)

        print()

        # ── Cannot answer ─────────────────────────────────────────────
        if result.cannot_answer:
            print(f"⛔  CANNOT ANSWER: {result.error}")

        # ── Hard error ────────────────────────────────────────────────
        elif not result.success:
            print(f"❌  ERROR: {result.error}")
            if result.sql:
                print(f"\n    SQL attempted:\n    {result.sql}")

        # ── Success ───────────────────────────────────────────────────
        else:
            print(f"✅  {result.row_count} row(s) returned")

            print(f"\n📋  SQL:\n{result.sql}")

            print(f"\n📊  Data:\n{json.dumps(result.data, indent=2, default=str)}")

            # Insight
            if result.insight:
                print(f"\n💡  Insight:\n{result.insight}")
            else:
                print("\n💡  Insight: (not generated)")

            # Chart
            if result.chart_path:
                print(f"\n📈  Chart  : {result.chart_path}  [{result.chart_type}]")
            else:
                print(f"\n📈  Chart  : (not generated — single stat or unsupported shape)")

        # ── Debug ─────────────────────────────────────────────────────
        if DEBUG:
            print(f"\n🔍  Tables retrieved : {result.retrieved_tables}")
            print(f"🔍  Prompt tokens    : ~{result.prompt_tokens}")
            print(f"🔍  Raw response     :\n{result.raw_response}")

    except KeyboardInterrupt:
        print("\n\nBye.")
        break
