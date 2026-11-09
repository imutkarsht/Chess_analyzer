"""Evaluation graph coalescing and direct pointer-to-index mapping."""

from types import SimpleNamespace

from src.gui.components.display.graph_widget import GraphWidget


def _moves():
    return [
        SimpleNamespace(
            eval_after_mate=None,
            eval_after_cp=20 * index,
            classification=None,
        )
        for index in range(1, 6)
    ]


def test_progress_update_draws_once_and_sets_cursor(qapp, monkeypatch):
    graph = GraphWidget()
    draws = []
    monkeypatch.setattr(graph.canvas, "draw_idle", lambda: draws.append(True))

    graph.update_progress(_moves(), up_to_index=3, current_move=2)

    assert draws == [True]
    assert graph.moves_data == [0, 1, 2, 3, 4]
    assert graph.current_move_line.get_visible() is True


def test_hover_and_click_round_directly_to_the_nearest_move(qapp):
    graph = GraphWidget()
    graph.plot_game(SimpleNamespace(moves=_moves()))
    event = SimpleNamespace(inaxes=graph.ax, xdata=1.6)

    graph.on_hover(event)
    assert "Move 2" in graph.annot.get_text()

    clicked = []
    graph.move_clicked.connect(clicked.append)
    graph.on_click(event)
    assert clicked == [1]

    graph.deleteLater()
