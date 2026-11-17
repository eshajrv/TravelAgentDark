import asyncio
from dotenv import load_dotenv
load_dotenv()
import cognee

DATASET = "redeye"
SESSION = "night_1"

async def main():
    await cognee.forget(everything=True)

    await cognee.remember(
        "Tier A conferences have an economy fare cap of $600.",
        dataset_name=DATASET,
        self_improvement=False,
    )

    await cognee.remember(
        "Night 1: bought SFO-JFK at $412 at 11pm; the night's low was $287 at 2am. Regret $125.",
        dataset_name=DATASET,
        session_id=SESSION,
        self_improvement=False,
    )

    q = "When should we buy SFO-JFK, and what's the cap?"
    print("BEFORE:", await cognee.recall(q, datasets=[DATASET]))

    await cognee.improve(dataset=DATASET, session_ids=[SESSION])

    print("AFTER:", await cognee.recall(q, datasets=[DATASET]))

asyncio.run(main())
