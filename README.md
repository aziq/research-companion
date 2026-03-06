# Research Companion

A Telegram bot that acts as a personal AI research analyst. Send it links, articles, voice memos, photos, PDFs, or raw text and it returns structured analysis with actionable next steps. Everything is stored in a local SQLite knowledge base you can search and browse from the CLI.

## What It Does

1. **Ingest** -- send any content to the bot via Telegram (URLs, text, voice, video, photos, documents)
2. **Extract** -- fetches and extracts text from the source (smart handling for YouTube, Twitter/X, articles, PDFs, audio transcription)
3. **Analyze** -- an LLM produces a structured breakdown: main idea, why it matters, category, suggested experiment, time to explore
4. **Store** -- saves the original content, analysis, and your context message to a local knowledge base
5. **Browse** -- query and review your knowledge base from the CLI

## Supported Input Types

| Input | How It's Processed |
|---|---|
| URLs (articles) | HTML extracted via trafilatura |
| YouTube links | Transcript fetched (fallback: yt-dlp description) |
| Twitter/X links | fxtwitter API > X syndication API > yt-dlp (including X Articles/Notes) |
| Plain text | Analyzed directly |
| Voice messages | Transcribed with Whisper, then analyzed |
| Audio files | Transcribed with Whisper (MP3, OGG, M4A, WAV, FLAC) |
| Videos / video notes | Audio extracted, transcribed, then analyzed |
| Photos | Vision model extracts text and key info, then analyzed |
| PDFs | Text extracted with pdfplumber |
| Text documents | Read directly |

## Setup

### Prerequisites

- Python 3.11+
- ffmpeg (required by faster-whisper for audio/video transcription)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- At least one AI API key (Anthropic or OpenAI)

### Installation

```bash
git clone <repo-url>
cd research-companion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
# Required
TELEGRAM_TOKEN=your-telegram-bot-token

# AI provider (at least one required; Anthropic preferred if both set)
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key

# Optional -- set for production webhook mode
WEBHOOK_URL=https://your-domain.com
```

## Usage

### Running the Bot

**Local development** (polling, no public URL needed):

```bash
python main.py
```

**Production** (webhook via FastAPI/uvicorn):

```bash
export WEBHOOK_URL=https://your-domain.com
uvicorn main:app --host 0.0.0.0 --port 8080
```

The mode is selected automatically -- if `WEBHOOK_URL` is set, it builds a FastAPI app with a `/webhook` endpoint and `/health` check. Otherwise it runs in long-polling mode.

### Bot Commands

Once the bot is running, use these commands inside the Telegram chat:

| Command | Description |
|---|---|
| `/list` | Browse the 20 most recent knowledge base entries |
| `/show <id>` | Show full analysis and metadata for an entry |
| `/search <query>` | Search across source, content, and analysis |
| `/delete <id>` | Remove an entry from the knowledge base |

**Register commands with BotFather** (optional, enables autocomplete in Telegram):

1. Message [@BotFather](https://t.me/BotFather) → `/setcommands`
2. Select your bot
3. Paste:

```
list - Browse recent knowledge base entries
show - /show <id>  Show full entry
search - /search <query>  Search the knowledge base
delete - /delete <id>  Remove an entry
```

### Knowledge Base CLI

```bash
python kb.py                    # List all saved items
python kb.py <id>               # Show full item (original content + analysis)
python kb.py search <query>     # Full-text search across all fields
python kb.py delete <id>        # Delete an item
```

Example list output:

```
  ID  TYPE          DATE              NOTE                  SOURCE
--------------------------------------------------------------------------------
  10  🔗 url        2026-03-06T13:03  check this out        https://example.com/article
   9  🎙 voice_memo 2026-03-06T12:50   - NA -
   8  📄 document   2026-03-06T12:45   - NA -               report.pdf
```

## Project Structure

```
research-companion/
├── main.py              # Entry point: polling (dev) or webhook (prod)
├── kb.py                # CLI knowledge base browser
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not committed)
├── research.db          # SQLite database (created at runtime, not committed)
└── bot/
    ├── application.py   # Telegram app builder, registers handlers
    ├── handlers.py      # Message handlers for each input type
    ├── analyzer.py      # LLM analysis (Anthropic / OpenAI)
    ├── fetcher.py       # URL content extraction (YouTube, X, generic)
    ├── transcriber.py   # Audio/video transcription (Whisper)
    └── db.py            # SQLite interface + schema migrations
```

## Database Schema

```sql
CREATE TABLE items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT,     -- url, note, voice_memo, audio, video, photo, document
    source      TEXT,     -- URL, filename, or identifier
    content     TEXT,     -- original extracted text / transcription
    analysis    TEXT,     -- LLM analysis output
    user_note   TEXT,     -- context message from the user (caption, surrounding text)
    created_at  TEXT      -- ISO 8601 timestamp
);
```

Existing databases are migrated automatically on startup.

## AI Providers

| Provider | Model | Used When |
|---|---|---|
| Anthropic | claude-haiku-4-5 | `ANTHROPIC_API_KEY` is set (preferred) |
| OpenAI | gpt-4o-mini | Fallback when only `OPENAI_API_KEY` is set |

Both text analysis and vision (photo) analysis are supported through either provider.

## Dependencies

| Package | Purpose |
|---|---|
| python-telegram-bot | Telegram Bot API |
| fastapi + uvicorn | Webhook server (production) |
| anthropic / openai | LLM analysis |
| trafilatura | Article text extraction from HTML |
| youtube-transcript-api | YouTube transcript fetching |
| yt-dlp | Video metadata extraction (YouTube, X fallback) |
| faster-whisper | Speech-to-text (Whisper base model, CPU, int8) |
| pdfplumber | PDF text extraction |
| httpx | Async HTTP client |

## License

MIT
