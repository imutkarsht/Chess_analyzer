import chess
from PyQt6.QtCore import QPoint, Qt

from src.backend.analysis.tactics import TACTICS_VERSION
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.analysis_panel import AnalysisPanel
from src.gui.analysis.think_time_chart import ThinkTimeChart


def _move(
    ply: int,
    *,
    time_left: float | None = None,
    time_spent: float | None = None,
    classification: str = "",
    raw_clk: str | None = None,
) -> MoveAnalysis:
    return MoveAnalysis(
        move_number=ply // 2 + 1,
        ply=ply,
        san="e4",
        uci="e2e4",
        fen_before=chess.STARTING_FEN,
        time_left=time_left,
        time_spent=time_spent,
        classification=classification,
        raw_clk=raw_clk,
    )


def test_chart_visibility_selection_and_current_ply(qtbot):
    chart = ThinkTimeChart()
    qtbot.addWidget(chart)
    chart.show()
    chart.resize(320, 90)
    chart.set_moves(
        [
            _move(0, time_left=120, time_spent=3),
            _move(1, time_left=90, time_spent=8),
            _move(2, time_left=45, time_spent=5),
        ],
        starting_clock=600,
    )
    selected = []
    chart.move_selected.connect(selected.append)

    chart.set_current_move(1)
    qtbot.mouseClick(chart, Qt.MouseButton.LeftButton, pos=QPoint(240, 40))

    assert not chart.isHidden()
    assert chart.current_move == 1
    assert selected == [2]

    chart.set_moves([_move(0)])
    assert chart.isHidden()


def test_analysis_panel_shows_clock_summary_and_hides_it_without_clock_data(qtbot):
    panel = AnalysisPanel()
    qtbot.addWidget(panel)
    panel.move_requested.connect(panel.set_selected_move)
    panel.current_game = GameAnalysis(
        game_id="clocked",
        metadata=GameMetadata(time_control="600+5", headers={}),
        moves=[
            _move(0, time_left=20, time_spent=200, classification="Blunder"),
            _move(1, time_left=80, time_spent=100, classification="Best"),
        ],
        summary={
            "white": {
                "tactics": {
                    "tactics_version": TACTICS_VERSION,
                    "clock_metrics": {
                        "total_timed_moves": 1,
                        "total_time_spent": 400,
                        "quality_time_spent": {"blunder": 90},
                        "quality_timed_moves": {"blunder": 1},
                        "trouble_blunders": 1,
                    },
                }
            },
            "black": {
                "tactics": {
                    "tactics_version": TACTICS_VERSION,
                    "clock_metrics": {
                        "total_timed_moves": 1,
                        "total_time_spent": 200,
                        "quality_time_spent": {"best": 70},
                        "quality_timed_moves": {"best": 1},
                        "trouble_blunders": 0,
                    },
                }
            },
        },
    )

    panel._update_time_management()
    panel.think_time_chart.move_selected.emit(1)

    assert not panel.think_time_checkbox.isHidden()
    assert not panel.think_time_chart.isHidden()
    assert not panel.time_management_frame.isHidden()
    assert "Average think time: 300.0s" in panel.time_management_values.text()
    assert "Blunders: 90.0s" in panel.time_management_values.text()
    assert "Best moves: 70.0s" in panel.time_management_values.text()
    assert "Time-trouble blunders: 1" in panel.time_management_values.text()
    assert panel.think_time_chart.current_move == 1

    panel.think_time_checkbox.setChecked(False)
    assert panel.think_time_chart.isHidden()

    panel.current_game = GameAnalysis(
        game_id="unclocked",
        metadata=GameMetadata(headers={}),
        moves=[_move(0, time_spent=12)],
    )
    panel._update_time_management()
    assert panel.think_time_checkbox.isHidden()
    assert panel.think_time_chart.isHidden()
    assert panel.time_management_frame.isHidden()
