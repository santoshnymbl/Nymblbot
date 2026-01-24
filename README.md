# 🕐 Miss Minutes - Nymbl AI Assistant

**Personal AI assistant for everyone in the organization.**

Miss Minutes provides:
- ⏰ **Personalized Friday reminders** to log time on MyNos
- 🤖 **AI-powered Q&A** about Nymbl policies, processes, and people
- ⚙️ **Customizable settings** per user (timezone, reminder time)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SLACK WORKSPACE                              │
│                                                                 │
│   User 1 (DM)    User 2 (DM)    User 3 (DM)    #channel        │
│       │              │              │              │            │
│       └──────────────┴──────────────┴──────────────┘            │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                     Slack Events API
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                    MISS MINUTES SERVER                           │
│                                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│   │ Slack Bolt  │  │  Scheduler  │  │     RAG Pipeline        │ │
│   │  Handler    │  │  (Per-user) │  │  BM25 + Reranker + LLM  │ │
│   └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  SQLite: user_preferences, interactions, reminder_log   │   │
│   └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Quick Start (30 minutes)

### Step 1: Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From manifest**
3. Select your workspace
4. Paste contents of `slack_manifest.json`
5. Click **Create**

### Step 2: Install to Workspace

1. Go to **OAuth & Permissions**
2. Click **Install to Workspace** → **Allow**
3. Copy **Bot User OAuth Token** (starts with `xoxb-`)

### Step 3: Get Signing Secret

1. Go to **Basic Information**
2. Copy **Signing Secret**

### Step 4: Get Claude API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create API key (you get $5 free credits)

### Step 5: Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → Sign up with GitHub
3. **New Project** → **Deploy from GitHub repo**
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_SIGNING_SECRET` | Your signing secret |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `MYNOS_URL` | Your time tracking URL |

5. Wait for deploy to complete
6. Copy your app URL (e.g., `https://miss-minutes-xxx.up.railway.app`)

### Step 6: Connect Slack to Server

1. Go back to [api.slack.com/apps](https://api.slack.com/apps) → Your app
2. **Event Subscriptions** → Enable Events
3. Set Request URL: `https://YOUR_URL.up.railway.app/slack/events`
4. Wait for ✅ Verified
5. **Interactivity & Shortcuts** → Enable
6. Set Request URL: `https://YOUR_URL.up.railway.app/slack/interactions`
7. Save Changes

### ✅ Done! Test It

1. Open Slack
2. DM Miss Minutes: "hi"
3. You'll see the welcome message!

---

## 🚀 Sharing with Your Team

### How It Works

Once deployed, **anyone in your Slack workspace** can use Miss Minutes:
- They DM `@Miss Minutes` or mention her in channels
- First message triggers personalized onboarding
- Each person gets their own settings (timezone, reminder time)
- **No additional setup required per user!**

### NO SHAREABLE LINK NEEDED!

Unlike external apps, Miss Minutes is **already available to everyone** in your workspace once you install it. Users don't need to:
- ❌ Click any install link
- ❌ Authorize anything
- ❌ Create accounts

They just:
- ✅ Search for "Miss Minutes" in Slack
- ✅ Send a DM
- ✅ Done!

---

### Sharing Strategy: Gradual Rollout

#### Phase 1: Test with Yourself
```
1. DM Miss Minutes
2. Try: "What is WGLL?"
3. Say: "subscribe" to opt-in to reminders
4. Say: "status" to see your settings
```

#### Phase 2: Invite 2-3 Beta Testers

**Copy-paste this DM to send to testers:**

```
Hey! 👋

I've set up an AI assistant called Miss Minutes for our team. She can:
• Answer questions about Nymbl (policies, processes, people)
• Send you Friday reminders to log your time

To try it out:
1. Search for "Miss Minutes" in Slack (or click: slack://user?team=YOUR_TEAM_ID&id=BOT_USER_ID)
2. Send her a DM saying "hi"
3. Ask anything like "What is WGLL?" or "How do I submit PTO?"

Let me know what you think!
```

#### Phase 3: Announce to Full Team

**Post in #general or #announcements:**

```
🕐 Introducing Miss Minutes - Your Nymbl AI Assistant!

Miss Minutes can help you with:

📚 *Questions about Nymbl*
Ask about policies, processes, acronyms, leadership - anything in our wiki!

⏰ *Friday Time Reminders*
Get personalized DM reminders to log your hours (opt-in)

*How to use:*
• DM @Miss Minutes with any question
• Or mention her in any channel: "@Miss Minutes what is WGLL?"

*Quick commands:*
• `subscribe` - Get Friday time reminders
• `status` - See your settings  
• `help` - All commands

Try it now - just DM Miss Minutes and say "hi"! 🚀
```

---

## Finding Miss Minutes in Slack

### Method 1: Search
1. Click the search bar in Slack
2. Type "Miss Minutes"
3. Click on the bot in results

### Method 2: Direct Link
Share this link format with users:
```
slack://user?team=TXXXXXXXX&id=UXXXXXXXX
```

To get the IDs:
1. In Slack, right-click on Miss Minutes
2. Click "Copy link"
3. The link contains the IDs

### Method 3: @ Mention
Just type `@Miss Minutes` in any channel - users will see her pop up.

---

## User Commands

| Command | Description | Example |
|---------|-------------|---------|
| `subscribe` | Opt-in to Friday reminders | "subscribe" |
| `unsubscribe` | Opt-out of reminders | "unsubscribe" |
| `status` | View your settings | "status" |
| `set timezone <tz>` | Change timezone | "set timezone US/Pacific" |
| `set reminder <time>` | Change reminder time | "set reminder 5pm" |
| `snooze <duration>` | Delay current reminder | "snooze 1 hour" |
| `done` | Acknowledge reminder | "done" |
| `help` | Show all commands | "help" |

---

## Features

### 1. Personalized Onboarding
First-time users see a welcome message with subscribe options.

### 2. AI Q&A (RAG)
- BM25 retrieval for fast candidate selection
- Cross-encoder reranking for precision
- Claude Sonnet for natural responses
- Trained on Nymbl wiki (3000+ lines)

### 3. Per-User Reminders
- Each user sets their own timezone
- Each user sets their own reminder time
- Reminders sent via DM (private)
- Snooze and acknowledge options

### 4. Privacy
- Questions aren't shared publicly
- DMs are private
- Each user controls their settings

---

## Project Structure

```
miss-minutes-v2/
├── src/
│   ├── app.py              # FastAPI main application
│   ├── config.py           # Settings and message templates
│   ├── models/
│   │   └── database.py     # SQLite models and queries
│   ├── ai/
│   │   ├── rag.py          # BM25 + Reranker pipeline
│   │   └── generator.py    # Claude AI integration
│   ├── slack/
│   │   ├── handler.py      # Event processing
│   │   └── commands.py     # Command handlers
│   ├── scheduler/
│   │   └── reminders.py    # Per-user reminder scheduler
│   └── utils/
│       └── timezone.py     # Timezone utilities
├── data/
│   └── nymbl_wiki.md       # Knowledge base
├── db/                     # SQLite database (auto-created)
├── requirements.txt
├── Procfile
├── railway.json
├── slack_manifest.json
└── README.md
```

---

## API Endpoints (Debug)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Status and stats |
| `/health` | GET | Health check |
| `/api/stats` | GET | Bot statistics |
| `/api/search?q=` | GET | Test RAG search |
| `/api/ask?question=` | POST | Test AI response |
| `/api/test-reminder` | POST | Send test reminder |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | ✅ | Bot OAuth token |
| `SLACK_SIGNING_SECRET` | ✅ | Request verification |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `MYNOS_URL` | ✅ | Time tracking URL |
| `DEFAULT_TIMEZONE` | ❌ | Default: America/New_York |
| `DEFAULT_REMINDER_TIME` | ❌ | Default: 16:30 |
| `DEBUG` | ❌ | Default: false |

---

## Cost

| Service | Free Tier | Estimated Use | Cost |
|---------|-----------|---------------|------|
| Railway | $5/month credit | ~$3-4 | **$0** |
| Claude API | $5 credit | ~$2-3 | **$0** |
| Slack | Free | Unlimited | **$0** |
| **Total** | | | **$0/month** |

---

## Troubleshooting

### Bot not responding?
1. Check Railway logs: `railway logs`
2. Verify Event URL shows ✅ Verified in Slack
3. Check bot has all required scopes

### Reminders not sending?
1. User must say `subscribe` to opt-in
2. Check user's timezone with `status`
3. Scheduler runs every 15 minutes

### Slow responses?
1. First request loads reranker model (~10s cold start)
2. Subsequent requests: 2-3 seconds
3. Use Railway ping service to prevent cold starts

---

## Adding More Knowledge

Drop additional `.md` or `.txt` files in `/data`:

```
data/
├── nymbl_wiki.md
├── policies.md
├── faq.md
└── onboarding.md
```

Restart the app to reindex.

---

## License

MIT - Built for Nymbl 🚀
