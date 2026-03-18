import os
import time
import json
import random
import asyncio
from collections import defaultdict, deque
from typing import Dict, Tuple, Deque, List

import discord
from discord.ext import commands
from discord import app_commands

import aiohttp
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN not found in .env")

GUILD_ID = os.getenv("GUILD_ID")

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_ENDPOINT = "/api/chat"

MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

MAX_MEMORY_TURNS = 8
MEMORY_EXPIRY_SECONDS = 60 * 30 # 30 minutes of inactivity before memory expires
DISCORD_MESSAGE_LIMIT = 2000
MAX_TRAIL_MESSAGES = 3

CHARACTER_DIR = "characters"
BASE_SYSTEM_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "baseSystem.txt",
)

STARTING_MESSAGES = [
    "Hmmm...",
    "Give me a moment...",
    "Thinking...",
    "Generating...",
    "One sec...",
]
THINKING_MESSAGE = (
    "I'm currently already thinking right now, give me a second and I'll get back to you."
)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

conversation_memory: Dict[
    Tuple[int, str], Deque[Dict[str, str]]
] = defaultdict(lambda: deque(maxlen=MAX_MEMORY_TURNS * 2))

last_activity: Dict[Tuple[int, str], float] = {}
bot_message_character: Dict[int, Tuple[str, float]] = {}
bot_message_trails: Dict[int, Deque[Dict[str, str]]] = {}

ongoing_generation: Dict[str, bool] = defaultdict(bool)
user_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

def get_characters() -> List[str]:
    if not os.path.isdir(CHARACTER_DIR):
        return []
    return [
        os.path.splitext(f)[0]
        for f in os.listdir(CHARACTER_DIR)
        if f.endswith(".txt")
    ]


def load_base_system_prompt() -> str:
    if not os.path.isfile(BASE_SYSTEM_FILE):
        raise RuntimeError("baseSystem.txt not found in project root.")
    with open(BASE_SYSTEM_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_character_prompt(character: str) -> str:
    path = os.path.join(CHARACTER_DIR, f"{character}.txt")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Character '{character}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_character_config(character: str) -> Dict[str, str]:
    path = os.path.join(CHARACTER_DIR, f"{character}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Character config for '{character}' not found (expected {character}.json)."
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    character_name = data.get("character_name")
    speech_style = data.get("specific_speech_style_or_tone")

    if not isinstance(character_name, str) or not character_name.strip():
        raise ValueError(
            f"Invalid 'character_name' in {character}.json."
        )
    if not isinstance(speech_style, str) or not speech_style.strip():
        raise ValueError(
            f"Invalid 'specific_speech_style_or_tone' in {character}.json."
        )

    return {
        "character_name": character_name.strip(),
        "specific_speech_style_or_tone": speech_style.strip(),
    }


def build_base_system_prompt(character: str) -> str:
    config = load_character_config(character)
    return (
        BASE_SYSTEM_TEMPLATE
        .replace("[Character Name]", config["character_name"])
        .replace(
            "[specific speech style or tone]",
            config["specific_speech_style_or_tone"],
        )
    )


def cleanup_expired_memory():
    now = time.time()
    expired = [
        key for key, ts in last_activity.items()
        if now - ts > MEMORY_EXPIRY_SECONDS
    ]
    for key in expired:
        conversation_memory.pop(key, None)
        last_activity.pop(key, None)

    expired_bot_messages = [
        message_id
        for message_id, (_, ts) in bot_message_character.items()
        if now - ts > MEMORY_EXPIRY_SECONDS
    ]
    for message_id in expired_bot_messages:
        bot_message_character.pop(message_id, None)
        bot_message_trails.pop(message_id, None)


def parse_character_prefix(message: str) -> Tuple[str, str] | None:
    stripped = message.lstrip()
    if not stripped:
        return None

    lower = stripped.casefold()
    for character in sorted(get_characters(), key=len, reverse=True):
        prefix = f"{character},"
        if lower.startswith(prefix.casefold()):
            return character, stripped[len(prefix):].lstrip()

    return None


def split_message(text: str) -> List[str]:
    if len(text) <= DISCORD_MESSAGE_LIMIT:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 > DISCORD_MESSAGE_LIMIT:
            chunks.append(current)
            current = paragraph
        else:
            if current:
                current += "\n"
            current += paragraph

    if current:
        chunks.append(current)

    return chunks

async def stream_ollama(model: str, messages: List[Dict[str, str]]):
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        "keep_alive": "45m",
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.05,
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "num_ctx": 4096,
            "num_predict": 120,
        },
    }

    buffer = ""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            OLLAMA_BASE_URL + OLLAMA_CHAT_ENDPOINT,
            json=payload,
            timeout=None,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama HTTP {resp.status}")

            async for chunk in resp.content.iter_any():
                buffer += chunk.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("done"):
                        return

                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

BASE_SYSTEM_TEMPLATE = load_base_system_prompt()

async def handle_character(
    *,
    send_func,
    edit_func,
    user_id: int,
    character: str,
    message: str,
    context_trail: List[Dict[str, str]] | None = None,
):
    cleanup_expired_memory()

    key = (user_id, character)
    last_activity[key] = time.time()

    try:
        base_system_prompt = build_base_system_prompt(character)
        character_prompt = load_character_prompt(character)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        await send_func(str(e))
        return

    system_prompt = f"---SYSTEM PROMPT---\n\n{base_system_prompt}\n\n---CHARACTER INFORMATION---\n\n{character_prompt}"

    async with user_locks[character]:
        if ongoing_generation[character]:
            await send_func(THINKING_MESSAGE)
            return

        ongoing_generation[character] = True
        await bot.change_presence(status=discord.Status.online)
        thinking_msg = await send_func(random.choice(STARTING_MESSAGES))
        
        user = await bot.fetch_user(user_id)

        memory = conversation_memory[key]
        messages = [{"role": "system", "content": system_prompt}]
        if context_trail is not None:
            messages.extend(context_trail)
        else:
            messages.extend(memory)
        messages.append({"role": "user", "content": f"{user.display_name} (@{user.name}) has asked: {message}.\n\n(to ping the user, use <@{user.id}>)"})

        full_reply = ""
        last_edit = time.monotonic()

        try:
            async for token in stream_ollama(MODEL_NAME, messages):
                full_reply += token

                if time.monotonic() - last_edit > 0.6:
                    await edit_func(
                        thinking_msg,
                        full_reply[-DISCORD_MESSAGE_LIMIT:],
                    )
                    last_edit = time.monotonic()

        except Exception as e:
            await edit_func(thinking_msg, f"Something went wrong while communicating to ollama: {e}")
            ongoing_generation[character] = False
            if not any(ongoing_generation.values()):
                await bot.change_presence(status=discord.Status.idle)
            return

        if not full_reply.strip():
            await edit_func(
                thinking_msg,
                "The model returned no output.",
            )
            ongoing_generation[character] = False
            if not any(ongoing_generation.values()):
                await bot.change_presence(status=discord.Status.idle)
            return

        memory.append({"role": "user", "content": message})
        memory.append({"role": "assistant", "content": full_reply})

        trail_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in {"user", "assistant"}
        ]
        trail_messages.append({"role": "assistant", "content": full_reply})
        trail = deque(trail_messages[-MAX_TRAIL_MESSAGES:], maxlen=MAX_TRAIL_MESSAGES)

        parts = split_message(full_reply)

        first_reply_msg = await edit_func(thinking_msg, parts[0])
        first_reply_id = first_reply_msg.id if first_reply_msg else thinking_msg.id
        bot_message_character[first_reply_id] = (character, time.time())
        bot_message_trails[first_reply_id] = deque(trail, maxlen=MAX_TRAIL_MESSAGES)

        for part in parts[1:]:
            sent_msg = await send_func(part)
            if sent_msg:
                bot_message_character[sent_msg.id] = (character, time.time())
                bot_message_trails[sent_msg.id] = deque(trail, maxlen=MAX_TRAIL_MESSAGES)

        ongoing_generation[character] = False
        if not any(ongoing_generation.values()):
            await bot.change_presence(status=discord.Status.idle)


def register_prefix_command(character: str):
    async def command(ctx: commands.Context, *, message: str):
        await handle_character(
            send_func=ctx.send,
            edit_func=lambda m, c: m.edit(content=c),
            user_id=ctx.author.id,
            character=character,
            message=message,
        )

    bot.command(name=character)(command)

def register_slash_command(character: str):
    @bot.tree.command(name=character, description=f"Talk to {character}")
    @app_commands.describe(message=f"What do you want to say to {character}?")
    async def slash(interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        await handle_character(
            send_func=interaction.followup.send,
            edit_func=lambda m, c: m.edit(content=c),
            user_id=interaction.user.id,
            character=character,
            message=message,
        )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    character_to_use = None
    content_to_send = ""
    context_trail = None

    parsed_prefix = parse_character_prefix(message.content)
    if parsed_prefix:
        character_to_use, content_to_send = parsed_prefix
    elif message.reference and message.reference.message_id:
        referenced = bot_message_character.get(message.reference.message_id)
        if referenced:
            character_to_use = referenced[0]
            content_to_send = message.content.strip()
            stored_trail = bot_message_trails.get(message.reference.message_id)
            if stored_trail:
                context_trail = list(stored_trail)

    if character_to_use and content_to_send:
        await handle_character(
            send_func=lambda c: message.reply(c, mention_author=False),
            edit_func=lambda m, c: m.edit(content=c),
            user_id=message.author.id,
            character=character_to_use,
            message=content_to_send,
            context_trail=context_trail,
        )
        return

    await bot.process_commands(message)

@bot.command(name="clearmemory")
async def clear_memory_prefix(ctx: commands.Context):
    user_id = ctx.author.id
    keys_to_remove = [key for key in conversation_memory.keys() if key[0] == user_id]
    
    for key in keys_to_remove:
        conversation_memory.pop(key, None)
        last_activity.pop(key, None)
    
    characters_cleared = len(keys_to_remove)
    if characters_cleared > 0:
        await ctx.send(f"Cleared your conversation memory for {characters_cleared} character(s).")
    else:
        await ctx.send("You don't have any conversation memory to clear.")

@bot.tree.command(name="clearmemory", description="Clear your conversation memory with all characters")
async def clear_memory_slash(interaction: discord.Interaction):
    user_id = interaction.user.id
    keys_to_remove = [key for key in conversation_memory.keys() if key[0] == user_id]
    
    for key in keys_to_remove:
        conversation_memory.pop(key, None)
        last_activity.pop(key, None)
    
    characters_cleared = len(keys_to_remove)
    if characters_cleared > 0:
        await interaction.response.send_message(
            f"Cleared your conversation memory for {characters_cleared} character(s).",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "You don't have any conversation memory to clear.",
            ephemeral=True
        )

@bot.event
async def on_ready():
    characters = get_characters()

    for character in characters:
        register_prefix_command(character)
        register_slash_command(character)

    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.clear_commands(guild=guild)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild {GUILD_ID}")
    else:
        await bot.tree.sync()
        print("Synced commands globally (may take up to 1 hour)")
    
    await bot.change_presence(status=discord.Status.idle)
    print(f"Logged in as {bot.user}")
    print(f"Loaded characters: {', '.join(characters)}")

bot.run(DISCORD_TOKEN)
