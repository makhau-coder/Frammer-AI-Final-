# main.py
# Interactive test harness — run queries from the terminal.
#
# Usage:
#   python main.py                    # standard (blocking) mode
#   python main.py --debug            # shows token count + retrieved tables
#   python main.py --stream           # streams the insight token-by-token
#   python main.py --stream --debug   # both


import sys
import os
from dotenv import load_dotenv


load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))


from nlp.engine import query, query_stream, NLPResult


DEBUG  = "--debug"  in sys.argv
STREAM = "--stream" in sys.argv


print("━" * 60)
print("  Frammer NLP Engine — Interactive Test")
mode_label = "streaming" if STREAM else "standard"
print(f"  Mode: {mode_label}  |  Type your question.")
print("  'reset' to clear history. 'exit' to quit.")
print("━" * 60)


def _print_result(result: NLPResult) -> None:
    """Shared display logic for both streaming and non-streaming paths."""
    print()

    if result.needs_input:
        print(f"🤔  {result.message}")

    elif result.cannot_answer:
        print(f"⛔  {result.message}")

    elif not result.success and result.error:
        print(f"❌  {result.error}")

    else:
        print(f"Data: {result.data}")
        print(f"✅  {result.row_count} row(s)")
        if result.chart_path:
            print(f"\n📈  {result.chart_path}  [{result.chart_type}]")

    if DEBUG:
        print(f"\n🔍  Tables : {result.retrieved_tables}")
        print(f"🔍  SQL    : {result.sql}")


while True:
    try:
        text = input("\n❓ ").strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        if text.lower() in ("reset", "clear"):
            from nlp.agent import clear_memory
            clear_memory()
            print("🔄  History cleared.")
            continue

        if STREAM:
            # ── Streaming path ────────────────────────────────────────
            # query_stream() yields str chunks while Gemini is typing,
            # then yields a final NLPResult as the last item.
            result: NLPResult | None = None
            insight_started = False

            for chunk in query_stream(text, debug=DEBUG):
                if isinstance(chunk, str):
                    if not insight_started:
                        # Print the label just before the first token arrives
                        print("\n💡  ", end="", flush=True)
                        insight_started = True
                    print(chunk, end="", flush=True)
                else:
                    result = chunk   # NLPResult — stream is complete

            if insight_started:
                print()   # newline after streamed insight

            if result is not None:
                # Print everything except the insight (already streamed above)
                print()
                if result.needs_input:
                    print(f"🤔  {result.message}")
                elif result.cannot_answer:
                    print(f"⛔  {result.message}")
                elif not result.success and result.error:
                    print(f"❌  {result.error}")
                else:
                    print(f"Data: {result.data}")
                    print(f"✅  {result.row_count} row(s)")
                    if result.chart_path:
                        print(f"\n📈  {result.chart_path}  [{result.chart_type}]")

                if DEBUG:
                    print(f"\n🔍  Tables : {result.retrieved_tables}")
                    print(f"🔍  SQL    : {result.sql}")

        else:
            # ── Standard (blocking) path — identical to original ──────
            result = query(text, debug=DEBUG)
            print()

            if result.needs_input:
                print(f"🤔  {result.message}")

            elif result.cannot_answer:
                print(f"⛔  {result.message}")

            elif not result.success and result.error:
                print(f"❌  {result.error}")

            else:
                print(f"Data: {result.data}")
                print(f"✅  {result.row_count} row(s)")
                if result.message:
                    print(f"\n💡  {result.message}")
                if result.chart_path:
                    print(f"\n📈  {result.chart_path}  [{result.chart_type}]")

            if DEBUG:
                print(f"\n🔍  Tables : {result.retrieved_tables}")
                print(f"🔍  SQL    : {result.sql}")

    except KeyboardInterrupt:
        print("\n\nBye.")
        break