# Bohrium

**Turn your Discord server into your own mini-Kaggle.**
Bohrium is a Discord bot that lets communities host, join, and run their own machine-learning competitions without ever leaving chat.

---

## What It Does

Bohrium brings Kaggle-style competition mechanics straight into Discord.
You can:

* 🏁 **Host your own ML contests** — create custom timed multiple problem contests based on already happening contests.
* 📊 **Auto-update leaderboards** from Kaggle-style evaluation metrics.
* 🧠 **Integrate with the Kaggle API** to pull datasets, validate submissions, and even sync with real Kaggle challenges.
* 💬 **Run everything inside Discord** — entries, updates, standings, and even banter.

Basically, it makes your Discord server a self-contained arena for data scientists and AI tinkerers.

---

## Setup in Minutes

1. Clone it:

   ```bash
   git clone https://github.com/Savyasachi123/Bohrium.git
   cd Bohrium
   ```
2. Create a virtual environment:

   ```
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Add your credentials:
   Create a `.env` file with:

   ```
    KAGGLE_USERNAME=<username>
    KAGGLE_KEY=<key>
    BOT_TOKEN=<custom_bot_token>
    GEMMA_API_KEY=<gemini-api-key>
   ```
5. Launch it:

   ```
   python bot.py
   ```
6. Invite Bohrium to your server and start a contest with your crew.

---

## Project Layout

```
Bohrium/
│
├── bot.py              # Main entry point
├── cogs/               # Modular bot commands (Kaggle, competitions, etc.)
├── data/               # Datasets, configs, leaderboards
├── requirements.txt    # Dependencies
├── LICENSE
└── .vscode/            # Optional workspace settings
```

---

## Why Kaggle Integration Matters

This isn’t just a random ML-themed Discord bot.
Bohrium **hooks into the actual Kaggle API**, which means:

* You can **import public Kaggle competitions** and challenges directly.
* Users can **submit results** that are **scored using Kaggle’s evaluation logic**.
* Leaderboards update in real-time, keeping the same competitive energy as Kaggle — but on your own turf.
* You’re no longer limited by Kaggle’s schedule or scope. Run private contests, hackathons, or friendly data battles whenever you want.

It’s Kaggle... but casual.

---

## Contribute or Extend

Want to add new commands, metrics, or integrations? Go for it.

1. Fork the repo.
2. Create a feature branch.
3. Open a pull request.

Ideas welcome — new features? Yes, please.

---

## Roadmap for the future

* Automated submission scoring and report summaries
* Expanded Kaggle dataset search and linking
* Better kaggle problem finding
* Personal duels feature
* Multi-guild (multi-server) competition support
* Optional API for third-party extensions

---

## 📜 License

Licensed under the **Apache 2.0 License** — see the `LICENSE` file for details.

---

## 💬 Join the Experiment

If you’ve ever wanted to **run your own Kaggle**, Bohrium gives you the keys.
Host your own data battles, train your models, and let the leaderboard settle the bragging rights.

---
