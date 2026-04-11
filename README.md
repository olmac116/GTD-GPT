# GTD GPT (Best AI Chatbot Ever)

GTD GPT is a Discord bot designed for [Studs Studioz](https://discord.gg/XAJthkYArx) which brings characters from Generic TD into Discord where members can talk and ask questions.

### Add a Character

To add a new character, or to edit an existing character, go to /characters/ and add:

- A _.txt file \*(replace _ with the character name)\* for full character instructions.
- A matching \_.json file with placeholder metadata for `baseSystem.txt`.

Then stop then start `main.py` (or restart the container) to see the new changes.

Whatever you set \_.txt to will be the name of the slash command for that character. Example: `boxer.txt` -> `/boxer [message]`

The matching JSON must include:

```json
{
  "display_name": "Boxer",
  "character_summary": "an upbeat common fighter from Roblox Generic Tower Defense who relies on grit, teamwork, and relentless optimism over raw strength",
  "voice_style": "casual, energetic, slightly overconfident, and highly motivational"
}
```

Field meanings:

- `display_name`: The in-character name inserted into the system prompt.
- `character_summary`: A short, high-level description of who they are.
- `voice_style`: The tone and speaking style the model should use.

### Prerequisites

- Ollama
  - You can download Ollama here: https://ollama.com/download
- Any Ollama model
- Docker
- Docker Compose
- Git
- Discord Application (bot)

> [!IMPORTANT]
> You will need basic docker, docker-compose & Discord Bot setup knowledge **before** setup since there are no listed instructions here.

### Environment

So everything works as it should, your `.env` must include:

```
DISCORD_TOKEN=
GUILD_ID=
OLLAMA_MODEL=
```

Fill in the empty variables with the correct data. To check your installed Ollama models, run this command into your host machine: `ollama list`, copy the name of the model you'd like to use and paste it into `OLLAMA_MODEL=` inside the `.env`

---

## Clone the Repository

1. Clone the repository into your host matchine:

```bash
git clone https://github.com/olmac116/GTD-GPT.git
```

2. Navigate into the repo directory

```bash
cd GTD-GPT
```

### Important Notes

- Ollama must be accessible from inside the Docker container.
  - This repo's default compose setup uses host networking on Linux, so `http://localhost:11434` works when Ollama is running on the host.
  - If you are using Docker Desktop or a bridge network, prefer `http://host.docker.internal:11434` and let the bot fall back to the host-gateway alias.
  - If you switch back to bridge networking, use `host.docker.internal` on Mac/Windows or your Docker bridge IP on Linux.
- Restart the container after adding or editing character files.
- Docker Compose automatically loads environment variables from `.env`.
- Make sure Ollama is serving, run `ollama serve` on your host machine.
- Some smaller Ollama models may not listen to roleplay instructions, so you might need to tweak the default system prompt. (You can do so by editing baseSystem.txt)

### Credits

- olmac116
  - Maintainer
- lolpleplays & Hbums
  - Permission to use characters from Generic TD for this project.

Join [Studs Studioz](https://discord.gg/XAJthkYArx) to see this bot in action!
