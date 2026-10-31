"""Shared navigation toolbar behaviour for both page variants."""

from src.gui.analysis.move_controls import MoveControls


def test_analysis_variant_exposes_flip_and_emits_signals(qapp):
    controls = MoveControls(variant="analysis")
    emitted = []
    controls.first_clicked.connect(lambda: emitted.append("first"))
    controls.prev_clicked.connect(lambda: emitted.append("prev"))
    controls.next_clicked.connect(lambda: emitted.append("next"))
    controls.last_clicked.connect(lambda: emitted.append("last"))
    controls.flip_clicked.connect(lambda: emitted.append("flip"))

    controls.btn_first.click()
    controls.btn_prev.click()
    controls.btn_next.click()
    controls.btn_last.click()
    controls.btn_flip.click()

    assert emitted == ["first", "prev", "next", "last", "flip"]


def test_explorer_variant_has_no_flip_and_tracks_navigation_bounds(qapp):
    controls = MoveControls(variant="explorer")

    assert controls.btn_flip is None

    controls.set_navigation_state(-1, 0)
    assert all(
        not button.isEnabled()
        for button in (
            controls.btn_first,
            controls.btn_prev,
            controls.btn_next,
            controls.btn_last,
        )
    )

    controls.set_navigation_state(-1, 3)
    assert not controls.btn_first.isEnabled()
    assert not controls.btn_prev.isEnabled()
    assert controls.btn_next.isEnabled()
    assert controls.btn_last.isEnabled()

    controls.set_navigation_state(2, 3)
    assert controls.btn_first.isEnabled()
    assert controls.btn_prev.isEnabled()
    assert not controls.btn_next.isEnabled()
    assert not controls.btn_last.isEnabled()
