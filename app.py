"""Poker EV Trainer — Monte Carlo equity calculator with Streamlit UI."""

import random
import re
from dataclasses import dataclass

import streamlit as st
from treys import Card, Deck, Evaluator

RANKS = "23456789TJQKA"
SUITS = "hdcs"
CARD_PATTERN = re.compile(r"^([2-9TJQKA]|[10])([hdcs])$", re.IGNORECASE)


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
            raise ValueError(f"无效牌面格式: '{token}'，请使用如 Ah、Ks、Td 的格式。")
        rank, suit = match.group(1).upper(), match.group(2).lower()
        cards.append(Card.new(f"{rank}{suit}"))

    if len(cards) != len(set(cards)):
        raise ValueError("检测到重复的牌，请检查手牌和公共牌是否冲突。")

    return cards


def run_monte_carlo(
    hero_hand: list[int],
    board: list[int],
    num_opponents: int,
    iterations: int,
    seed: int | None = None,
) -> SimulationResult:
    """Simulate random runouts and opponent hands to estimate equity."""
    if len(hero_hand) != 2:
        raise ValueError("手牌必须是 2 张。")
    if len(board) > 5:
        raise ValueError("公共牌最多 5 张。")

    evaluator = Evaluator()
    known = set(hero_hand + board)
    cards_needed = 5 - len(board) + num_opponents * 2

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

        hero_score = evaluator.evaluate(hero_hand, sim_board)
        villain_scores = [
            evaluator.evaluate(hand, sim_board) for hand in villain_hands
        ]
        best_score = min([hero_score] + villain_scores)

        if hero_score < best_score:
            wins += 1
        elif hero_score == best_score:
            winners = sum(1 for s in [hero_score] + villain_scores if s == best_score)
            if winners == 1:
                wins += 1
            else:
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


def analyze_call(
    result: SimulationResult,
    pot_size: float,
    call_amount: float,
    num_opponents: int,
) -> EvAnalysis:
    """Compute pot odds, required equity, call EV, and recommendation."""
    total_pot_after_call = pot_size + call_amount
    pot_odds = call_amount / total_pot_after_call if total_pot_after_call > 0 else 0.0
    required_equity = pot_odds * 100

    # Effective equity: full win share plus split share on ties.
    tie_share = result.tie_pct / (num_opponents + 1)
    equity = result.win_pct + tie_share

    call_ev = (equity / 100) * total_pot_after_call - call_amount
    recommendation = "Call ✅" if call_ev >= 0 else "Fold ❌"

    return EvAnalysis(
        pot_odds=pot_odds * 100,
        required_equity=required_equity,
        equity=equity,
        call_ev=call_ev,
        recommendation=recommendation,
    )


def main() -> None:
    st.set_page_config(
        page_title="Poker EV Trainer",
        page_icon="♠️",
        layout="centered",
    )

    st.markdown(
        """
        <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .subtitle {
            color: #6b7280;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 1rem 1.2rem;
            color: #f8fafc;
            text-align: center;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #94a3b8;
        }
        .metric-value {
            font-size: 1.6rem;
            font-weight: 700;
        }
        .rec-call {
            background: #065f46;
            color: #ecfdf5;
            padding: 1rem;
            border-radius: 12px;
            font-size: 1.4rem;
            font-weight: 700;
            text-align: center;
        }
        .rec-fold {
            background: #7f1d1d;
            color: #fef2f2;
            padding: 1rem;
            border-radius: 12px;
            font-size: 1.4rem;
            font-weight: 700;
            text-align: center;
        }
        .help-box {
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            padding: 0.8rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="main-title">♠️ Poker EV Trainer</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">输入牌局信息，用 Monte Carlo 模拟计算胜率与跟注 EV</p>',
        unsafe_allow_html=True,
    )

    with st.expander("📖 新手帮助：牌面怎么写？", expanded=False):
        st.markdown(
            """
            <div class="help-box">
            <b>牌面格式</b>：点数 + 花色，例如 <code>Ah Ks</code><br>
            <b>点数</b>：2 3 4 5 6 7 8 9 T(10) J Q K A<br>
            <b>花色</b>：h=红桃 ♥　d=方块 ♦　c=梅花 ♣　s=黑桃 ♠<br><br>
            <b>示例</b>：AK 同花 → <code>Ah Kh</code>　翻牌 → <code>2h 7d Tc</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🃏 牌局信息")
        hole_cards_text = st.text_input(
            "你的手牌（2 张）",
            value="Ah Ks",
            placeholder="例如：Ah Ks",
            help="必须输入 2 张手牌",
        )
        board_text = st.text_input(
            "公共牌（0–5 张）",
            value="2h 7d Tc",
            placeholder="例如：2h 7d Tc，翻前可留空",
            help="翻前留空；翻牌 3 张；转牌 4 张；河牌 5 张",
        )
        num_opponents = st.number_input(
            "对手人数",
            min_value=1,
            max_value=8,
            value=1,
            step=1,
            help="默认 1 名对手（单挑）",
        )

    with col_right:
        st.subheader("💰 底池与跟注")
        pot_size = st.number_input(
            "底池大小 Pot Size",
            min_value=0.0,
            value=100.0,
            step=1.0,
            format="%.2f",
        )
        call_amount = st.number_input(
            "跟注金额 Call Amount",
            min_value=0.0,
            value=50.0,
            step=1.0,
            format="%.2f",
        )
        iterations = st.slider(
            "模拟次数（越大越准，越慢）",
            min_value=1000,
            max_value=50000,
            value=10000,
            step=1000,
        )

    calculate = st.button("🎯 计算胜率与 EV", type="primary", use_container_width=True)

    if calculate:
        try:
            hero_hand = parse_cards(hole_cards_text)
            board = parse_cards(board_text)

            if len(hero_hand) != 2:
                st.error("请准确输入 2 张手牌，例如：Ah Ks")
                return
            if len(board) > 5:
                st.error("公共牌最多 5 张。")
                return
            if pot_size < 0 or call_amount < 0:
                st.error("底池和跟注金额不能为负数。")
                return

            with st.spinner(f"正在模拟 {iterations:,} 次，请稍候..."):
                result = run_monte_carlo(
                    hero_hand=hero_hand,
                    board=board,
                    num_opponents=int(num_opponents),
                    iterations=int(iterations),
                )
                ev = analyze_call(result, pot_size, call_amount, int(num_opponents))

            st.success(f"模拟完成（共 {result.iterations:,} 次）")

            st.subheader("📊 胜率结果")
            c1, c2, c3 = st.columns(3)
            c1.metric("Win %", f"{result.win_pct:.2f}%")
            c2.metric("Tie %", f"{result.tie_pct:.2f}%")
            c3.metric("Lose %", f"{result.lose_pct:.2f}%")

            st.subheader("📈 EV 分析")
            e1, e2, e3 = st.columns(3)
            e1.metric("Pot Odds", f"{ev.pot_odds:.2f}%")
            e2.metric("Required Equity", f"{ev.required_equity:.2f}%")
            e3.metric("Your Equity", f"{ev.equity:.2f}%")

            st.metric("Call EV", f"{ev.call_ev:+.2f}")

            rec_class = "rec-call" if ev.call_ev >= 0 else "rec-fold"
            st.markdown(
                f'<div class="{rec_class}">建议：{ev.recommendation}</div>',
                unsafe_allow_html=True,
            )

            st.info(
                f"**判断逻辑**：当你的有效胜率（Equity {ev.equity:.2f}%）"
                f"高于所需胜率（Required Equity {ev.required_equity:.2f}%）时，"
                f"跟注 EV 为正，建议 Call。"
            )

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"计算出错：{exc}")


if __name__ == "__main__":
    main()
