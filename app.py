"""Poker EV Trainer v2 — Monte Carlo equity, range analysis & preflop advisor."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal

import streamlit as st
from treys import Card, Deck, Evaluator

APP_VERSION = "v2.0"
CARD_PATTERN = re.compile(r"^([2-9TJQKA])([hdcs])$", re.IGNORECASE)
RANK_ORDER = "23456789TJQKA"
RANK_VALUE = {r: i for i, r in enumerate(RANK_ORDER, start=2)}

RangeType = Literal["Random", "Tight", "Standard", "Loose"]
Position = Literal["UTG", "HJ", "CO", "BTN", "SB", "BB"]
Scenario = Literal["First In", "Facing Open", "Facing 3Bet"]
PreflopAction = Literal["Raise", "Call", "Fold", "3Bet"]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    win_pct: float
    tie_pct: float
    lose_pct: float
    iterations: int


@dataclass
class EvAnalysis:
    pot_odds: float
    required_equity: float
    equity: float
    call_ev: float
    recommendation: str


# ---------------------------------------------------------------------------
# Card parsing & validation
# ---------------------------------------------------------------------------


def parse_cards(text: str) -> list[int]:
    """Parse card strings like 'Ah Ks' or 'AhKs' into treys card integers."""
    text = text.strip()
    if not text:
        return []

    tokens: list[str] = []
    if re.search(r"[\s,;/]+", text):
        tokens = re.split(r"[\s,;/]+", text)
    else:
        cleaned = text.replace("10", "T")
        i = 0
        while i < len(cleaned):
            if cleaned[i : i + 2].upper().startswith("10"):
                tokens.append(cleaned[i : i + 3])
                i += 3
            else:
                tokens.append(cleaned[i : i + 2])
                i += 2

    cards: list[int] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        token = token.replace("10", "T")
        match = CARD_PATTERN.match(token)
        if not match:
            raise ValueError(
                f"Invalid card format: '{token}'. Use rank + suit, e.g. Ah, Ks, Td."
            )
        rank, suit = match.group(1).upper(), match.group(2).lower()
        cards.append(Card.new(f"{rank}{suit}"))

    if len(cards) != len(set(cards)):
        raise ValueError("Duplicate cards detected within the same input field.")

    return cards


def validate_cards(hero_text: str, board_text: str) -> tuple[list[int], list[int]]:
    """Validate hero hand (exactly 2) and board (0–5), no duplicates across fields."""
    hero = parse_cards(hero_text)
    board = parse_cards(board_text)

    if len(hero) != 2:
        raise ValueError("Hero hand must be exactly 2 cards, e.g. Ah Ks.")
    if len(board) > 5:
        raise ValueError("Board can have at most 5 cards (0–5 allowed).")

    combined = hero + board
    if len(combined) != len(set(combined)):
        raise ValueError(
            "Duplicate cards between hero hand and board. Each card can appear only once."
        )
    return hero, board


def normalize_hand(card_a: int, card_b: int) -> str:
    """Convert two treys cards to standard notation: AA, AKs, AKo, etc."""
    rank_a = Card.get_rank_int(card_a)
    rank_b = Card.get_rank_int(card_b)
    suit_a = Card.get_suit_int(card_a)
    suit_b = Card.get_suit_int(card_b)

    # treys rank int: 2=0..A=12 — map back to char
    def rank_char(rank_int: int) -> str:
        return RANK_ORDER[rank_int]

    r1, r2 = rank_a, rank_b
    if r1 < r2:
        r1, r2 = r2, r1

    c1, c2 = rank_char(r1), rank_char(r2)
    if r1 == r2:
        return f"{c1}{c2}"
    suited = suit_a == suit_b
    return f"{c1}{c2}{'s' if suited else 'o'}"


# ---------------------------------------------------------------------------
# Villain range definitions (simplified model)
# ---------------------------------------------------------------------------

TIGHT_RANGE: set[str] = {
    "TT", "JJ", "QQ", "KK", "AA",
    "AKs", "AKo", "AQs", "AQo", "AJs", "KQs",
}

STANDARD_RANGE: set[str] = TIGHT_RANGE | {
    "99", "88", "77", "ATs", "A9s", "KJs", "KTs", "QJs", "QTs", "JTs", "T9s",
    "AJo", "ATo", "KQo", "98s", "87s",
}

LOOSE_RANGE: set[str] = STANDARD_RANGE | {
    "66", "55", "44", "33", "22",
    "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
    "A9o", "A8o", "A7o", "A6o", "A5o",
    "K9s", "K8s", "K7s", "KJo", "KTo",
    "Q9s", "Q8s", "QJo", "J9s", "J8s", "T8s", "97s", "76s", "65s", "54s",
}

RANGE_MAP: dict[RangeType, set[str] | None] = {
    "Random": None,
    "Tight": TIGHT_RANGE,
    "Standard": STANDARD_RANGE,
    "Loose": LOOSE_RANGE,
}


def _hand_string_to_combos(hand: str) -> list[tuple[str, str]]:
    """Expand AKs / AKo / AA into list of (rank+suit, rank+suit) string pairs."""
    if len(hand) == 2:
        rank = hand[0]
        combos = []
        suits = ["h", "d", "c", "s"]
        for i, s1 in enumerate(suits):
            for s2 in suits[i + 1 :]:
                combos.append((f"{rank}{s1}", f"{rank}{s2}"))
        return combos

    rank1, rank2 = hand[0], hand[1]
    suited = hand[2].lower() == "s"
    combos = []
    suits = ["h", "d", "c", "s"]
    if suited:
        for s in suits:
            combos.append((f"{rank1}{s}", f"{rank2}{s}"))
    else:
        for s1 in suits:
            for s2 in suits:
                if s1 != s2:
                    combos.append((f"{rank1}{s1}", f"{rank2}{s2}"))
    return combos


def build_range_combos(range_name: RangeType, excluded: set[int]) -> list[list[int]]:
    """Build all concrete two-card combos for a range, excluding known cards."""
    hand_set = RANGE_MAP[range_name]
    if hand_set is None:
        return []

    combos: list[list[int]] = []
    seen: set[frozenset[int]] = set()
    for hand in hand_set:
        for c1_str, c2_str in _hand_string_to_combos(hand):
            c1, c2 = Card.new(c1_str), Card.new(c2_str)
            combo = [c1, c2]
            if set(combo) & excluded:
                continue
            key = frozenset(combo)
            if key not in seen:
                seen.add(key)
                combos.append(combo)
    return combos


# ---------------------------------------------------------------------------
# Monte Carlo equity
# ---------------------------------------------------------------------------


def _evaluate_showdown(
    evaluator: Evaluator,
    hero_hand: list[int],
    villain_hands: list[list[int]],
    board: list[int],
) -> Literal["win", "tie", "lose"]:
    """Compare hero vs one or more villains; lower treys score wins."""
    hero_score = evaluator.evaluate(hero_hand, board)
    villain_scores = [evaluator.evaluate(v, board) for v in villain_hands]
    best_score = min([hero_score, *villain_scores])

    if hero_score < best_score:
        return "win"
    if hero_score == best_score:
        winners = sum(1 for s in [hero_score, *villain_scores] if s == best_score)
        return "win" if winners == 1 else "tie"
    return "lose"


def calculate_equity(
    hero_hand: list[int],
    board: list[int],
    num_opponents: int = 1,
    iterations: int = 10000,
    seed: int | None = None,
) -> SimulationResult:
    """Monte Carlo: random opponent hands + random runouts → win/tie/lose %."""
    evaluator = Evaluator()
    known = set(hero_hand + board)
    wins = ties = losses = 0
    rng = random.Random(seed)

    for _ in range(iterations):
        deck = Deck()
        remaining = [c for c in deck.cards if c not in known]
        rng.shuffle(remaining)

        idx = 0
        villain_hands = [
            [remaining[idx], remaining[idx + 1]] for _ in range(num_opponents)
        ]
        idx += num_opponents * 2
        sim_board = board + remaining[idx : idx + (5 - len(board))]

        outcome = _evaluate_showdown(evaluator, hero_hand, villain_hands, sim_board)
        if outcome == "win":
            wins += 1
        elif outcome == "tie":
            ties += 1
        else:
            losses += 1

    total = wins + ties + losses
    return SimulationResult(
        win_pct=wins / total * 100,
        tie_pct=ties / total * 100,
        lose_pct=losses / total * 100,
        iterations=total,
    )


def calculate_equity_vs_range(
    hero_hand: list[int],
    board: list[int],
    range_name: RangeType,
    iterations: int = 10000,
    seed: int | None = None,
) -> SimulationResult:
    """Monte Carlo vs a fixed villain range (or random if range_name is Random)."""
    if range_name == "Random":
        return calculate_equity(hero_hand, board, num_opponents=1, iterations=iterations, seed=seed)

    known = set(hero_hand + board)
    range_combos = build_range_combos(range_name, known)
    if not range_combos:
        raise ValueError(
            f"No valid {range_name} range combos remain after removing known cards."
        )

    evaluator = Evaluator()
    wins = ties = losses = 0
    rng = random.Random(seed)

    for _ in range(iterations):
        deck = Deck()
        remaining = [c for c in deck.cards if c not in known]
        villain_hand = rng.choice(range_combos)

        # Remove villain cards from runout deck
        runout_pool = [c for c in remaining if c not in villain_hand]
        rng.shuffle(runout_pool)
        cards_needed = 5 - len(board)
        sim_board = board + runout_pool[:cards_needed]

        outcome = _evaluate_showdown(evaluator, hero_hand, [villain_hand], sim_board)
        if outcome == "win":
            wins += 1
        elif outcome == "tie":
            ties += 1
        else:
            losses += 1

    total = wins + ties + losses
    return SimulationResult(
        win_pct=wins / total * 100,
        tie_pct=ties / total * 100,
        lose_pct=losses / total * 100,
        iterations=total,
    )


# ---------------------------------------------------------------------------
# EV calculation
# ---------------------------------------------------------------------------


def calculate_ev(
    result: SimulationResult,
    pot_size: float,
    call_amount: float,
    num_opponents: int = 1,
) -> EvAnalysis:
    """Pot odds, required equity, effective equity, call EV, and decision."""
    total_pot_after_call = pot_size + call_amount
    pot_odds = call_amount / total_pot_after_call if total_pot_after_call > 0 else 0.0
    required_equity = pot_odds * 100

    # Effective equity = win% + share of tie pot (split among all tied players)
    tie_share = result.tie_pct / (num_opponents + 1)
    equity = result.win_pct + tie_share

    call_ev = (equity / 100) * total_pot_after_call - call_amount
    recommendation = "Call" if call_ev >= 0 else "Fold"

    return EvAnalysis(
        pot_odds=pot_odds * 100,
        required_equity=required_equity,
        equity=equity,
        call_ev=call_ev,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Preflop advisor (simplified GTO-inspired chart)
# ---------------------------------------------------------------------------

HAND_TIER: dict[str, int] = {}
for _hand in ["AA", "KK", "QQ", "JJ", "AKs"]:
    HAND_TIER[_hand] = 1
for _hand in ["TT", "99", "AKo", "AQs", "AJs", "KQs"]:
    HAND_TIER[_hand] = 2
for _hand in ["88", "77", "AQo", "ATs", "KJs", "QJs", "JTs", "T9s"]:
    HAND_TIER[_hand] = 3
for _hand in [
    "66", "55", "44", "33", "22", "A9s", "A8s", "A7s", "A6s", "A5s",
    "AJo", "ATo", "KQo", "KTs", "QTs", "98s", "87s", "76s",
]:
    HAND_TIER[_hand] = 4


def _hand_tier(hand: str) -> int:
    return HAND_TIER.get(hand, 5)


# tier thresholds per (scenario, position) → action
# First In: mostly Raise or Fold
_FIRST_IN: dict[str, int] = {
    "UTG": 2, "HJ": 3, "CO": 3, "BTN": 4, "SB": 4, "BB": 5,
}
# Facing Open: tier ≤3bet → 3Bet, ≤call → Call, else Fold
_FACING_OPEN_3BET: dict[str, int] = {
    "UTG": 1, "HJ": 1, "CO": 2, "BTN": 2, "SB": 2, "BB": 2,
}
_FACING_OPEN_CALL: dict[str, int] = {
    "UTG": 2, "HJ": 3, "CO": 3, "BTN": 4, "SB": 3, "BB": 4,
}
# Facing 3Bet: tier ≤3bet → 3Bet (4-bet), ≤call → Call, else Fold
_FACING_3BET_4BET: dict[str, int] = {
    "UTG": 1, "HJ": 1, "CO": 1, "BTN": 2, "SB": 2, "BB": 2,
}
_FACING_3BET_CALL: dict[str, int] = {
    "UTG": 2, "HJ": 2, "CO": 2, "BTN": 3, "SB": 3, "BB": 3,
}


def get_preflop_advice(hand: str, position: Position, scenario: Scenario) -> PreflopAction:
    """Return simplified preflop action from built-in chart (not a full solver)."""
    tier = _hand_tier(hand)

    if scenario == "First In":
        raise_threshold = _FIRST_IN[position]
        return "Raise" if tier <= raise_threshold else "Fold"

    if scenario == "Facing Open":
        if tier <= _FACING_OPEN_3BET[position]:
            return "3Bet"
        if tier <= _FACING_OPEN_CALL[position]:
            return "Call"
        return "Fold"

    # Facing 3Bet
    if tier <= _FACING_3BET_4BET[position]:
        return "3Bet"
    if tier <= _FACING_3BET_CALL[position]:
        return "Call"
    return "Fold"


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(165deg, #070b14 0%, #0f1a2e 45%, #132238 100%);
        }
        [data-testid="stSidebar"] { background: #0a1220; }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1100px;
        }
        @media (max-width: 768px) {
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .hero-title { font-size: 1.6rem !important; }
        }
        .hero-header {
            background: linear-gradient(135deg, #14532d 0%, #0f3460 55%, #1a1a2e 100%);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 1.6rem 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.45);
        }
        .hero-title {
            font-size: 2.1rem;
            font-weight: 800;
            color: #f0fdf4;
            margin: 0;
            letter-spacing: -0.02em;
        }
        .hero-sub {
            color: #94a3b8;
            font-size: 1rem;
            margin: 0.35rem 0 0 0;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(34,197,94,0.2);
            color: #86efac;
            border: 1px solid rgba(34,197,94,0.35);
            border-radius: 999px;
            padding: 0.15rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 0.6rem;
        }
        .panel-card {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 14px;
            padding: 1.25rem 1.4rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }
        .panel-title {
            color: #e2e8f0;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }
        .decision-call {
            background: linear-gradient(135deg, #065f46, #047857);
            color: #ecfdf5;
            border-radius: 14px;
            padding: 1.1rem 1.4rem;
            font-size: 1.35rem;
            font-weight: 800;
            text-align: center;
            box-shadow: 0 4px 24px rgba(16,185,129,0.35);
            margin: 0.8rem 0;
        }
        .decision-fold {
            background: linear-gradient(135deg, #7f1d1d, #991b1b);
            color: #fef2f2;
            border-radius: 14px;
            padding: 1.1rem 1.4rem;
            font-size: 1.35rem;
            font-weight: 800;
            text-align: center;
            box-shadow: 0 4px 24px rgba(239,68,68,0.3);
            margin: 0.8rem 0;
        }
        .decision-raise {
            background: linear-gradient(135deg, #1e3a5f, #2563eb);
            color: #eff6ff;
            border-radius: 14px;
            padding: 1.1rem 1.4rem;
            font-size: 1.35rem;
            font-weight: 800;
            text-align: center;
            box-shadow: 0 4px 24px rgba(59,130,246,0.35);
            margin: 0.8rem 0;
        }
        .equity-bar-wrap {
            background: #1e293b;
            border-radius: 10px;
            height: 28px;
            position: relative;
            overflow: hidden;
            margin: 0.5rem 0 0.25rem 0;
            border: 1px solid rgba(148,163,184,0.15);
        }
        .equity-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }
        .equity-marker {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 3px;
            background: #fbbf24;
            z-index: 2;
        }
        .equity-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.78rem;
            color: #94a3b8;
            margin-top: 0.25rem;
        }
        .hint-text { color: #64748b; font-size: 0.82rem; margin-top: 0.2rem; }
        .disclaimer {
            background: rgba(251,191,36,0.08);
            border-left: 3px solid #fbbf24;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            color: #fde68a;
            font-size: 0.88rem;
            margin: 0.8rem 0;
        }
        div[data-testid="stMetric"] {
            background: rgba(30,41,59,0.6);
            border: 1px solid rgba(148,163,184,0.1);
            border-radius: 12px;
            padding: 0.75rem 1rem;
        }
        div[data-testid="stMetric"] label { color: #94a3b8 !important; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_header() -> None:
    st.markdown(
        f"""
        <div class="hero-header">
            <p class="hero-title">♠ Poker EV Trainer</p>
            <p class="hero-sub">Equity, Pot Odds &amp; EV Decision Assistant</p>
            <span class="hero-badge">{APP_VERSION}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_equity_bar(equity: float, required: float) -> None:
    """Visual bar: green fill = your equity, yellow line = required equity."""
    fill_pct = min(max(equity, 0), 100)
    req_pct = min(max(required, 0), 100)
    color = "#22c55e" if equity >= required else "#ef4444"
    st.markdown(
        f"""
        <div class="equity-bar-wrap">
            <div class="equity-fill" style="width:{fill_pct}%; background:{color};"></div>
            <div class="equity-marker" style="left:calc({req_pct}% - 1.5px);"></div>
        </div>
        <div class="equity-labels">
            <span>Your Equity: {equity:.1f}%</span>
            <span>Required: {required:.1f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ev_explanation(ev: EvAnalysis) -> str:
    if ev.call_ev >= 0:
        return (
            f"Your equity is **{ev.equity:.1f}%**, which beats the required **{ev.required_equity:.1f}%** "
            f"to break even on a call. Call EV is **{ev.call_ev:+.2f}** — calling is +EV."
        )
    return (
        f"Your equity is **{ev.equity:.1f}%**, below the required **{ev.required_equity:.1f}%** "
        f"to break even. Call EV is **{ev.call_ev:+.2f}** — folding saves chips long-term."
    )


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------


def tab_ev_calculator() -> None:
    st.markdown('<div class="panel-title">EV Calculator</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Hand Setup**")
        hole_cards_text = st.text_input(
            "Hero Hand",
            value="Ah Ks",
            placeholder="Ah Ks",
            help="Exactly 2 cards",
        )
        st.caption("Example: Ah Ks")
        board_text = st.text_input(
            "Board",
            value="2h 7d Tc",
            placeholder="2h 7d Tc (leave empty preflop)",
            help="0 to 5 community cards",
        )
        st.caption("Example: 2h 7d Tc — leave blank preflop")
        num_opponents = st.number_input("Opponents", min_value=1, max_value=8, value=1, step=1)

    with col_r:
        st.markdown("**Pot & Simulation**")
        pot_size = st.number_input("Pot Size", min_value=0.0, value=100.0, step=1.0, format="%.2f")
        call_amount = st.number_input("Call Amount", min_value=0.0, value=50.0, step=1.0, format="%.2f")
        iterations = st.slider("Monte Carlo Iterations", 1000, 50000, 10000, 1000)

    if st.button("Calculate Equity & EV", type="primary", use_container_width=True):
        try:
            hero, board = validate_cards(hole_cards_text, board_text)
            if pot_size < 0 or call_amount < 0:
                st.error("Pot size and call amount cannot be negative.")
                return

            with st.spinner(f"Running {iterations:,} simulations…"):
                result = calculate_equity(
                    hero, board, int(num_opponents), int(iterations)
                )
                ev = calculate_ev(result, pot_size, call_amount, int(num_opponents))

            st.success(f"Done — {result.iterations:,} simulations")

            m1, m2, m3 = st.columns(3)
            m1.metric("Win %", f"{result.win_pct:.2f}%")
            m2.metric("Tie %", f"{result.tie_pct:.2f}%")
            m3.metric("Lose %", f"{result.lose_pct:.2f}%")

            st.markdown("---")
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Your Equity", f"{ev.equity:.2f}%")
            e2.metric("Required Equity", f"{ev.required_equity:.2f}%")
            e3.metric("Pot Odds", f"{ev.pot_odds:.2f}%")
            e4.metric("Call EV", f"{ev.call_ev:+.2f}")

            st.markdown("**Equity vs Required Equity**")
            render_equity_bar(ev.equity, ev.required_equity)

            css_class = "decision-call" if ev.call_ev >= 0 else "decision-fold"
            icon = "✓" if ev.call_ev >= 0 else "✗"
            st.markdown(
                f'<div class="{css_class}">Decision: {ev.recommendation} {icon}</div>',
                unsafe_allow_html=True,
            )
            st.info(ev_explanation(ev))

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Calculation error: {exc}")


def tab_range_analysis() -> None:
    st.markdown('<div class="panel-title">Range Analysis</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hint-text">Estimate hero equity vs a simplified villain range model.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disclaimer">⚠ Simplified range model — not a full GTO solver. '
        "Use for study and rough estimates only.</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        hero_text = st.text_input("Hero Hand", value="Ah Ks", key="range_hero", placeholder="Ah Ks")
        st.caption("Example: Ah Ks")
    with c2:
        board_text = st.text_input("Board", value="", key="range_board", placeholder="Optional — 2h 7d Tc")
        st.caption("Example: 2h 7d Tc (optional)")

    villain_range = st.selectbox(
        "Villain Range",
        ["Random", "Tight", "Standard", "Loose"],
        help="Random = any two cards; others use predefined simplified ranges",
    )

    with st.expander("What each range includes"):
        st.markdown(
            f"""
            - **Random** — any two cards from the deck
            - **Tight** — {', '.join(sorted(TIGHT_RANGE)[:8])}… (pairs TT+, strong Ax, Broadway)
            - **Standard** — Tight range plus medium pairs, suited connectors, broadways
            - **Loose** — Standard plus small pairs, suited aces, more offsuit broadways
            """
        )

    iterations = st.slider("Iterations", 1000, 50000, 10000, 1000, key="range_iter")

    if st.button("Run Range Analysis", type="primary", use_container_width=True):
        try:
            hero, board = validate_cards(hero_text, board_text)
            with st.spinner(f"Simulating vs {villain_range} range…"):
                result = calculate_equity_vs_range(
                    hero, board, villain_range, int(iterations)  # type: ignore[arg-type]
                )

            st.success(f"Done — {result.iterations:,} simulations vs **{villain_range}**")

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Win %", f"{result.win_pct:.2f}%")
            r2.metric("Tie %", f"{result.tie_pct:.2f}%")
            r3.metric("Lose %", f"{result.lose_pct:.2f}%")
            effective = result.win_pct + result.tie_pct / 2
            r4.metric("Effective Equity", f"{effective:.2f}%")

            st.info(
                f"**{normalize_hand(hero[0], hero[1])}** vs **{villain_range}** range "
                f"has ~**{effective:.1f}%** effective equity "
                f"({'ahead' if effective > 50 else 'behind' if effective < 50 else 'roughly even'} vs random hand)."
            )

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Calculation error: {exc}")


def tab_preflop_advisor() -> None:
    st.markdown('<div class="panel-title">Preflop Advisor</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="disclaimer">This is a simplified GTO-inspired chart, not a full solver output.</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        hand_text = st.text_input("Your Hand", value="Ah Ks", key="pf_hand", placeholder="Ah Ks")
        st.caption("Example: Ah Ks")
    with c2:
        position = st.selectbox("Position", ["UTG", "HJ", "CO", "BTN", "SB", "BB"])
    with c3:
        scenario = st.selectbox("Scenario", ["First In", "Facing Open", "Facing 3Bet"])

    if st.button("Get Preflop Advice", type="primary", use_container_width=True):
        try:
            cards = parse_cards(hand_text)
            if len(cards) != 2:
                raise ValueError("Enter exactly 2 cards, e.g. Ah Ks.")
            hand = normalize_hand(cards[0], cards[1])
            advice = get_preflop_advice(hand, position, scenario)  # type: ignore[arg-type]

            tier = _hand_tier(hand)
            tier_label = {1: "Premium", 2: "Strong", 3: "Playable", 4: "Marginal", 5: "Weak"}[tier]

            action_styles = {
                "Raise": "decision-raise",
                "Call": "decision-call",
                "Fold": "decision-fold",
                "3Bet": "decision-raise",
            }
            st.markdown(
                f'<div class="{action_styles[advice]}">Advice: {advice}</div>',
                unsafe_allow_html=True,
            )

            a1, a2, a3 = st.columns(3)
            a1.metric("Hand", hand)
            a2.metric("Strength Tier", tier_label)
            a3.metric("Scenario", scenario)

            scenario_notes = {
                "First In": f"From **{position}**, open-raise hands tier ≤ {_FIRST_IN[position]}; fold weaker.",
                "Facing Open": "3-bet strong value, call medium hands, fold the rest.",
                "Facing 3Bet": "4-bet (shown as 3Bet) premiums, call strong hands, fold weak ones.",
            }
            st.info(
                f"**{hand}** from **{position}** ({scenario}): **{advice}**. "
                + scenario_notes[scenario]
            )

        except ValueError as exc:
            st.error(str(exc))


def tab_how_it_works() -> None:
    st.markdown('<div class="panel-title">How It Works</div>', unsafe_allow_html=True)

    st.markdown(
        """
        ### EV Calculator
        1. Enter your **2 hole cards** and **0–5 board cards**
        2. Set **pot size** and **call amount**
        3. Monte Carlo simulates thousands of random runouts and opponent hands
        4. Compares your **equity** vs **required equity** (pot odds) to compute **Call EV**

        ### Key Terms

        | Term | Meaning |
        |------|---------|
        | **Equity** | Your share of the pot (% chance to win, plus split on ties) |
        | **Pot Odds** | Call ÷ (Pot + Call) — the price you pay |
        | **Required Equity** | Minimum equity to break even on a call |
        | **Call EV** | Expected profit/loss of calling: (Equity × Total Pot) − Call |

        ### Range Analysis
        Simulates your hand vs predefined villain ranges (Tight / Standard / Loose).
        This is a **simplified model** — real opponents mix frequencies and bet sizes.

        ### Preflop Advisor
        Uses tier-based charts inspired by common GTO opening/defending ranges.
        **Not a solver** — for learning hand categories and rough guidance only.

        ### Card Format
        - Ranks: `2 3 4 5 6 7 8 9 T J Q K A` (T = 10)
        - Suits: `h` ♥ `d` ♦ `c` ♣ `s` ♠
        - Example: `Ah Ks` = Ace of hearts + King of spades
        """
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Poker EV Trainer",
        page_icon="♠️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    render_hero_header()

    tab_ev, tab_range, tab_preflop, tab_help = st.tabs(
        ["EV Calculator", "Range Analysis", "Preflop Advisor", "How It Works"]
    )

    with tab_ev:
        tab_ev_calculator()
    with tab_range:
        tab_range_analysis()
    with tab_preflop:
        tab_preflop_advisor()
    with tab_help:
        tab_how_it_works()


if __name__ == "__main__":
    main()
