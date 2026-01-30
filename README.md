# GTD GPT (Best AI Chatbot Ever)

GTD GPT is a Discord bot designed for [Studs Studioz](https://discord.gg/XAJthkYArx) which brings characters from Generic TD into Discord where members can talk and ask questions.

### Add a Character

To add a new character, or to edit an existing character, go to /characters/ and add a new _.txt file _(replace \_ with the character name)_, then stop then start `main.py` (or restart the container) to see the new changes.
Whatever you set \_.txt to will be the name of the slash command for that character. Example: `boxer.txt` -> `/boxer [message]`

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
  - On Mac/Windows, use `host.docker.internal`
  - On Linux, use your Docker bridge IP or host networking
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
