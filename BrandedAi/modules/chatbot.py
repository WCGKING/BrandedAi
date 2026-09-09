import random

from Abg.chat_status import adminsOnly
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ChatAction
from pyrogram.types import InlineKeyboardMarkup, Message

from config import MONGO_URL
from BrandedAi import Branded
from BrandedAi.modules.helpers import CHATBOT_ON


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def get_chat_db():
    return MongoClient(MONGO_URL)


async def safe_typing(client: Client, chat_id: int):
    """
    Send typing action without allowing Telegram permission
    errors to break the chatbot handler.
    """
    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)
    except Exception:
        pass


def is_command_message(message: Message) -> bool:
    """
    Ignore normal chatbot processing for commands.
    """
    text = message.text or message.caption or ""

    return text.startswith(("!", "/", "?", "@", "#"))


async def send_chatbot_response(message: Message, text, response_type):
    """
    Safely send a chatbot response.
    Prevents empty messages and invalid sticker IDs.
    """

    if not text:
        return

    text = str(text).strip()

    if not text:
        return

    try:
        if response_type == "sticker":
            # Sticker file_id must exist.
            await message.reply_sticker(text)
        else:
            await message.reply_text(text)

    except Exception as e:
        print(f"Chatbot response error: {e}")


def get_random_response(chatai, word):
    """
    Find a random response for a word.
    Returns (text, response_type) or (None, None).
    """

    if not word:
        return None, None

    try:
        results = list(chatai.find({"word": word}))

        if not results:
            return None, None

        valid_results = []

        for item in results:
            response = item.get("text")

            if response:
                response = str(response).strip()

            if not response:
                continue

            response_type = item.get("check", "none")

            valid_results.append(
                (
                    response,
                    response_type,
                )
            )

        if not valid_results:
            return None, None

        return random.choice(valid_results)

    except Exception as e:
        print(f"MongoDB chatbot lookup error: {e}")
        return None, None


def get_vick_status(vick, chat_id):
    try:
        return vick.find_one({"chat_id": chat_id})
    except Exception as e:
        print(f"Vick DB error: {e}")
        return None


# ---------------------------------------------------------
# CHATBOT ON/OFF COMMAND
# ---------------------------------------------------------

@Branded.on_cmd("chatbot", group_only=True)
@adminsOnly("can_delete_messages")
async def chaton_(_, m: Message):
    await m.reply_text(
        f"ᴄʜᴀᴛ: {m.chat.title}\n"
        "**ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴩᴛɪᴏɴ ᴛᴏ ᴇɴᴀʙʟᴇ/ᴅɪsᴀʙʟᴇ ᴄʜᴀᴛʙᴏᴛ.**",
        reply_markup=InlineKeyboardMarkup(CHATBOT_ON),
    )


# ---------------------------------------------------------
# TEXT CHATBOT
# ---------------------------------------------------------

@Branded.on_message(
    (filters.text | filters.sticker | filters.group)
    & ~filters.private
    & ~filters.bot,
    group=4,
)
async def chatbot_text(client: Client, message: Message):

    if is_command_message(message):
        return

    chatdb = get_chat_db()

    try:
        chatai = chatdb["Word"]["WordDb"]
        vick = chatdb["VickDb"]["Vick"]

        is_vick = get_vick_status(vick, message.chat.id)

        # -------------------------------------------------
        # NORMAL MESSAGE
        # -------------------------------------------------

        if not message.reply_to_message:

            if is_vick:
                return

            await safe_typing(client, message.chat.id)

            word = message.text

            if not word:
                return

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

            return

        # -------------------------------------------------
        # REPLY TO BOT
        # -------------------------------------------------

        replied_user = message.reply_to_message.from_user

        if replied_user and replied_user.id == client.id:

            if is_vick:
                return

            await safe_typing(client, message.chat.id)

            word = message.text

            if not word:
                return

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

            return

        # -------------------------------------------------
        # LEARN REPLY TO STICKER
        # -------------------------------------------------

        replied_message = message.reply_to_message

        if replied_message.sticker:

            sticker_word = replied_message.text

            if sticker_word:
                sticker_word = sticker_word.strip()

            sticker_id = replied_message.sticker.file_unique_id

            if sticker_id:

                existing = chatai.find_one(
                    {
                        "word": sticker_word,
                        "id": sticker_id,
                    }
                )

                if not existing:
                    chatai.insert_one(
                        {
                            "word": sticker_word,
                            "text": sticker_id,
                            "check": "sticker",
                            "id": sticker_id,
                        }
                    )

        # -------------------------------------------------
        # LEARN TEXT REPLY
        # -------------------------------------------------

        if message.text and replied_message.text:

            word = replied_message.text.strip()
            response = message.text.strip()

            if word and response:

                existing = chatai.find_one(
                    {
                        "word": word,
                        "text": response,
                    }
                )

                if not existing:
                    chatai.insert_one(
                        {
                            "word": word,
                            "text": response,
                            "check": "none",
                        }
                    )

    except Exception as e:
        print(f"chatbot_text error: {e}")

    finally:
        chatdb.close()


# ---------------------------------------------------------
# STICKER CHATBOT
# ---------------------------------------------------------

@Branded.on_message(
    (filters.sticker | filters.text | filters.group)
    & ~filters.private
    & ~filters.bot,
    group=4,
)
async def chatbot_sticker(client: Client, message: Message):

    if is_command_message(message):
        return

    # Only process this handler when a sticker is involved.
    if not message.sticker and not (
        message.reply_to_message and message.reply_to_message.sticker
    ):
        return

    chatdb = get_chat_db()

    try:
        chatai = chatdb["Word"]["WordDb"]
        vick = chatdb["VickDb"]["Vick"]

        is_vick = get_vick_status(vick, message.chat.id)

        # -------------------------------------------------
        # NORMAL STICKER
        # -------------------------------------------------

        if message.sticker and not message.reply_to_message:

            if is_vick:
                return

            await safe_typing(client, message.chat.id)

            word = message.sticker.file_unique_id

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

            return

        # -------------------------------------------------
        # REPLY TO BOT
        # -------------------------------------------------

        if message.reply_to_message:

            replied_user = message.reply_to_message.from_user

            if replied_user and replied_user.id == client.id:

                if is_vick:
                    return

                await safe_typing(client, message.chat.id)

                if message.sticker:
                    word = message.sticker.file_unique_id
                else:
                    word = message.text

                if not word:
                    return

                hey, response_type = get_random_response(
                    chatai,
                    word,
                )

                if not hey:
                    return

                await send_chatbot_response(
                    message,
                    hey,
                    response_type,
                )

                return

            # -------------------------------------------------
            # LEARN REPLY TO STICKER
            # -------------------------------------------------

            replied_sticker = message.reply_to_message.sticker

            if replied_sticker:

                sticker_word = replied_sticker.file_unique_id

                # User replies with text to a sticker
                if message.text:

                    response = message.text.strip()

                    if response:

                        existing = chatai.find_one(
                            {
                                "word": sticker_word,
                                "text": response,
                            }
                        )

                        if not existing:
                            chatai.insert_one(
                                {
                                    "word": sticker_word,
                                    "text": response,
                                    "check": "text",
                                }
                            )

                # User replies with another sticker
                if message.sticker:

                    response = message.sticker.file_id

                    if response:

                        existing = chatai.find_one(
                            {
                                "word": sticker_word,
                                "text": response,
                            }
                        )

                        if not existing:
                            chatai.insert_one(
                                {
                                    "word": sticker_word,
                                    "text": response,
                                    "check": "sticker",
                                }
                            )

    except Exception as e:
        print(f"chatbot_sticker error: {e}")

    finally:
        chatdb.close()


# ---------------------------------------------------------
# PRIVATE TEXT CHATBOT
# ---------------------------------------------------------

@Branded.on_message(
    filters.text & filters.private & ~filters.bot,
    group=4,
)
async def chatbot_pvt(client: Client, message: Message):

    if is_command_message(message):
        return

    chatdb = get_chat_db()

    try:
        chatai = chatdb["Word"]["WordDb"]

        # -------------------------------------------------
        # NORMAL PRIVATE MESSAGE
        # -------------------------------------------------

        if not message.reply_to_message:

            await safe_typing(client, message.chat.id)

            word = message.text

            if not word:
                return

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

            return

        # -------------------------------------------------
        # REPLY TO BOT
        # -------------------------------------------------

        replied_user = message.reply_to_message.from_user

        if replied_user and replied_user.id == client.id:

            await safe_typing(client, message.chat.id)

            word = message.text

            if not word:
                return

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

    except Exception as e:
        print(f"chatbot_pvt error: {e}")

    finally:
        chatdb.close()


# ---------------------------------------------------------
# PRIVATE STICKER CHATBOT
# ---------------------------------------------------------

@Branded.on_message(
    filters.sticker & filters.private & ~filters.bot,
    group=4,
)
async def chatbot_sticker_pvt(client: Client, message: Message):

    if not message.sticker:
        return

    chatdb = get_chat_db()

    try:
        chatai = chatdb["Word"]["WordDb"]

        # -------------------------------------------------
        # NORMAL PRIVATE STICKER
        # -------------------------------------------------

        if not message.reply_to_message:

            await safe_typing(client, message.chat.id)

            word = message.sticker.file_unique_id

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

            return

        # -------------------------------------------------
        # REPLY TO BOT
        # -------------------------------------------------

        replied_user = message.reply_to_message.from_user

        if replied_user and replied_user.id == client.id:

            await safe_typing(client, message.chat.id)

            word = message.sticker.file_unique_id

            hey, response_type = get_random_response(
                chatai,
                word,
            )

            if not hey:
                return

            await send_chatbot_response(
                message,
                hey,
                response_type,
            )

    except Exception as e:
        print(f"chatbot_sticker_pvt error: {e}")

    finally:
        chatdb.close()
```
