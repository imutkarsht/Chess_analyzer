"""
Tests for the Coach card widget (Phase 4).

The card is presentation only: it renders the deterministic offline summary
straight away, offers "Ask Coach" for LLM-worthy classifications, and renders
whatever narrative the owner hands it — ignoring results for a request it is no
longer waiting for (D6).

Buttons are asserted with ``isHidden()`` because the card is never shown in
these tests, so ``isVisible()`` would be False regardless.
"""

from __future__ import annotations

import chess
import pytest
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.backend.analysis.tactics.insight import build_move_insight
from src.backend.storage.models import GameMetadata, MoveAnalysis
from src.gui.analysis.coach_card_widget import CoachCardWidget, CoachState, is_llm_worthy

LEGAL = ["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "Nxe5", "Bxd1"]


def _insight(classification: str = "Blunder", index: int = 8):
    """
    Insight for the move ``LEGAL[index]`` with the (analysed) opponent reply.

    The default is the 5.Nxe5 blunder punished by 5...Bxd1; ``index=4`` builds a
    different move on a different ply, which is what a real selection change is.
    """
    board = chess.Board()
    for san in LEGAL[:index]:
        board.push_san(san)
    fen_before = board.fen()
    # ply is 0-based (chess.Board.ply() before the push) and indexes ``moves``
    ply = index
    played = MoveAnalysis(
        ply // 2 + 1,
        ply,
        LEGAL[index],
        board.parse_san(LEGAL[index]).uci(),
        fen_before,
        classification=classification,
        best_move=board.parse_san("d4").uci(),
    )
    reply_board = chess.Board(fen_before)
    reply_board.push_san(LEGAL[index])
    reply = MoveAnalysis(
        (ply + 1) // 2 + 1,
        ply + 1,
        LEGAL[index + 1],
        reply_board.parse_san(LEGAL[index + 1]).uci(),
        reply_board.fen(),
        classification="Blunder",
        multi_pvs=[{"pv": [reply_board.parse_san(LEGAL[index + 1]).uci()], "cp": 0}],
    )
    meta = GameMetadata(white="A", black="B", white_elo="1600", black_elo="1500")
    return build_move_insight([played, reply], 0, metadata=meta)


@pytest.fixture
def card(qapp):
    widget = CoachCardWidget()
    yield widget
    widget.deleteLater()


class TestOfflineRendering:
    def test_no_selection_shows_a_prompt_and_no_actions(self, card):
        assert card.state == CoachState.EMPTY
        assert card.insight is None
        assert "Select a move" in card.body_text()
        assert card.btn_ask.isHidden()
        assert card.btn_refute.isHidden()
        assert card.btn_best.isHidden()

    def test_offline_state_renders_classification_move_and_eval_swing(self, card):
        insight = _insight()
        card.set_insight(insight)

        assert card.state == CoachState.OFFLINE
        assert card.class_pill.text() == "Blunder"
        assert card.san_label.text() == "5.Nxe5"
        assert "→" in card.eval_label.text()
        assert card.phase_label.text() == insight.phase
        assert card.body_text()  # the offline summary stands on its own

    def test_actions_follow_the_available_facts(self, card):
        card.set_insight(_insight())
        assert not card.btn_ask.isHidden()  # Blunder is LLM-worthy
        assert not card.btn_refute.isHidden()  # a refutation exists
        # the best move is the missed Nxe5-dodging line, which differs from the play
        assert card.refutation_label().startswith("5...")
        assert card.best_move_label()


class TestAskAction:
    def test_ask_is_offered_and_emits_the_request(self, card):
        card.set_insight(_insight("Blunder"))
        assert not card.btn_ask.isHidden()

        requests = []
        card.ask_requested.connect(lambda: requests.append(True))
        card.btn_ask.click()

        assert requests == [True]

    @pytest.mark.parametrize(
        ("classification", "worthy"),
        [("Blunder", True), ("Mistake", True), ("Brilliant", True), ("Best", False), ("", False)],
    )
    def test_is_llm_worthy_matrix(self, classification, worthy):
        """Sound moves are not explained unless the setting opts in (D8)."""
        assert is_llm_worthy(classification) is worthy
        assert is_llm_worthy(classification, allow_trivial=True) is bool(classification)


class TestNarrativeLifecycle:
    def test_loading_then_validated_narrative_renders(self, card):
        card.set_insight(_insight())
        card.begin_loading(seq=3, ply=8)

        assert card.state == CoachState.LOADING
        assert card.btn_ask.isEnabled() is False

        accepted = card.show_narrative(3, 8, "Bxd1 wins the queen because e5 was loose.")

        assert accepted is True
        assert card.state == CoachState.READY
        assert card.body_text() == "Bxd1 wins the queen because e5 was loose."
        assert card.btn_ask.isHidden()  # nothing left to ask

    @pytest.mark.parametrize("seq,ply", [(2, 8), (3, 7), (3, 9)])
    def test_stale_results_are_ignored(self, card, seq, ply):
        card.set_insight(_insight())
        card.begin_loading(seq=3, ply=8)

        assert card.show_narrative(seq, ply, "stale") is False
        assert card.show_fallback(seq, ply, "stale") is False
        assert card.state == CoachState.LOADING
        assert card.body_text() != "stale"


class TestFallback:
    def test_failure_keeps_the_offline_text_and_offers_a_retry(self, card):
        insight = _insight()
        card.set_insight(insight)
        offline = card.body_text()
        card.begin_loading(seq=5, ply=8)

        assert card.show_fallback(5, 8, "Error [APITimeoutError]: timed out") is True

        assert card.state == CoachState.FALLBACK
        assert card.body_text() == offline  # never contradicts the facts
        assert "couldn't respond" in card.caption.text()
        assert card.btn_ask.isEnabled() is True
        assert not card.btn_ask.isHidden()
        assert "APITimeoutError" in card.btn_ask.toolTip()


class TestLayout:
    """The card wraps to the panel width and grows downwards with its text."""

    def test_the_body_height_is_exact(self, card):
        assert card.body_edit.minimumHeight() == card.body_edit.maximumHeight() > 0

    def test_header_badges_are_styled_before_a_move_is_selected(self, card):
        """An unstyled placeholder is shorter, which would jump the header."""
        empty = card.class_pill.sizeHint().height()

        card.set_insight(_insight())

        assert card.class_pill.sizeHint().height() == empty

    def test_a_long_narrative_never_widens_the_card(self, card):
        card.set_insight(_insight())
        short_text = card.minimumSizeHint().width()

        card.begin_loading(seq=1, ply=8)
        card.show_narrative(1, 8, "word " * 400)

        assert card.minimumSizeHint().width() <= short_text


def _card_in_a_host(qtbot, width):
    """
    Put a card inside a host of ``width`` px and return ``(host, card)``.

    In the panel the card is a squeezed child, so the width comes from its
    parent; a top-level card would be clamped to its one-row minimum and would
    never wrap.
    """
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    card = CoachCardWidget()
    layout.addWidget(card)
    qtbot.addWidget(host)  # owns (and deletes) the card with the host
    host.resize(width, 400)
    host.show()
    qtbot.wait(1)
    return host, card


class TestRowWrapping:
    """A narrow panel wraps the actions instead of squeezing their labels."""

    def test_a_wrapped_action_comes_back_when_the_card_grows_again(self, qtbot):
        """Hiding a row also hides its children; the wrap must not stick."""
        host, card = _card_in_a_host(qtbot, 320)
        card.set_insight(_insight())
        assert not card._action_rows[1].isHidden()

        host.resize(1200, 400)
        qtbot.wait(1)

        assert card._action_rows[1].isHidden()
        for button in (card.btn_ask, card.btn_refute, card.btn_best):
            assert not button.isHidden()
