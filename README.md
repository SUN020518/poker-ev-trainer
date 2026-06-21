# Poker EV Trainer v2.0

A beginner-friendly **Texas Hold'em EV trainer** with Monte Carlo equity simulation, range analysis, and a simplified preflop advisor.

Built with **Python + Streamlit + treys**. Runs locally on Windows and deploys to **Streamlit Community Cloud**.

---

## Features (v2)

| Tab | Description |
|-----|-------------|
| **EV Calculator** | Hand + board + pot/call → Win/Tie/Lose %, pot odds, Call EV, Call/Fold decision |
| **Range Analysis** | Hero vs Random / Tight / Standard / Loose villain ranges |
| **Preflop Advisor** | Simplified GTO-inspired chart by position & scenario |
| **How It Works** | Glossary and usage guide |

---

## Requirements

- **Windows 10 / 11** (or any OS with Python)
- **Python 3.9+** (3.10+ recommended)

---

## Local Setup (Windows)

### Step 1 — Check Python

```powershell
python --version
```

Install from https://www.python.org/downloads/ if needed (check **Add Python to PATH**).

### Step 2 — Go to project folder

```powershell
cd "D:\poker project"
```

### Step 3 — Create & activate virtual environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

You should see `(venv)` in your prompt.

### Step 4 — Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 5 — Run the app

```powershell
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

Press **Ctrl + C** in the terminal to stop.

---

## Testing Each Tab

### EV Calculator

1. Hero Hand: `Ah Ks`
2. Board: `2h 7d Tc` (leave blank for preflop)
3. Pot Size: `100`, Call Amount: `50`
4. Click **Calculate Equity & EV**
5. Verify: Win/Tie/Lose metrics, equity bar, green **Call** or red **Fold**

### Range Analysis

1. Hero Hand: `Ah Ks`
2. Board: leave blank or add flop
3. Villain Range: try **Tight** vs **Loose**
4. Click **Run Range Analysis**
5. Compare effective equity — tighter ranges should show lower hero equity with marginal hands

### Preflop Advisor

1. Hand: `Ah Kh` (or `Ah Ks`)
2. Position: **BTN**, Scenario: **First In**
3. Click **Get Preflop Advice** → expect **Raise** for AK
4. Try weak hand `7h 2d` from **UTG** → expect **Fold**

### How It Works

Read-only tab — confirm glossary and card format render correctly.

---

## Card Format

| | |
|---|---|
| Ranks | `2 3 4 5 6 7 8 9 T J Q K A` |
| Suits | `h`♥ `d`♦ `c`♣ `s`♠ |
| Example | `Ah Ks` = Ace of hearts + King of spades |

---

## Deploy to Streamlit Cloud

If the app is already live on Streamlit Community Cloud, push updates with git:

### Step 1 — Check changes

```powershell
cd "D:\poker project"
git status
git diff
```

### Step 2 — Stage and commit

```powershell
git add app.py README.md requirements.txt
git commit -m "Upgrade to v2: modern UI, range analysis, preflop advisor"
```

### Step 3 — Push to GitHub

```powershell
git push origin main
```

> Replace `main` with your branch name if different (e.g. `master`).

Streamlit Cloud redeploys automatically within 1–3 minutes after push.

### First-time Streamlit Cloud setup

1. Push this repo to **GitHub**
2. Go to https://share.streamlit.io
3. **New app** → select repo → main file: `app.py`
4. Deploy — no secrets needed for this project

---

## Project Structure

```
poker project/
├── app.py              # Main app (UI + all logic)
├── requirements.txt    # streamlit, treys
├── README.md           # This file
└── venv/               # Local virtual env (not committed)
```

---

## Tech Stack

- **Python** — core language
- **Streamlit** — web UI
- **treys** — hand evaluation

---

## Disclaimer

Range Analysis and Preflop Advisor use **simplified models** for learning purposes. They are not full GTO solver outputs. Use EV Calculator results as estimates — accuracy improves with more Monte Carlo iterations.
