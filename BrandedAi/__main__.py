import asyncio
import importlib

from pyrogram import idle

from BrandedAi import LOGGER, Branded
from BrandedAi.modules import ALL_MODULES


async def anony_boot():
    try:
        await Branded.start()
    except Exception as ex:
        LOGGER.error(ex)
        quit(1)

    for all_module in ALL_MODULES:
        importlib.import_module("BrandedAi.modules." + all_module)

    LOGGER.info(f"@{Branded.username} Started.")
    await idle()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(anony_boot())
    LOGGER.info("𝐒𝐭𝐨𝐩𝐩𝐢𝐧𝐠 - 𝐁𝐫𝐚𝐧𝐝𝐞𝐝 - 𝐀𝐢 - 𝐁𝐨𝐭...")
