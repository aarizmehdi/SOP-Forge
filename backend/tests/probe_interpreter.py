"""One synthetic extraction; prints only error class/status, never credentials."""
import asyncio
from app.models.draft import RequestDraft
from app.services.candidate_extraction import extract_candidates


async def main():
    try:
        result = await extract_candidates("I have fever and need four days starting tomorrow.", RequestDraft(employee_id="synthetic-test"))
        print(result.model_dump_json())
    except Exception as exc:
        print({"error_type": type(exc).__name__, "http_status": getattr(exc, "status_code", None)})
        if exc.__cause__:
            print({"cause_type": type(exc.__cause__).__name__})


if __name__ == '__main__':
    asyncio.run(main())
