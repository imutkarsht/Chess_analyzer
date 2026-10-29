"""Query building and SQL-backed paging for the history list."""

import pytest

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.game_query import (
    GameQuery,
    build_filters,
    build_order_by,
)


def _row(index: int, **overrides) -> dict:
    row = {
        "id": f"g{index}",
        "white": "PlayerA",
        "black": f"Rival{index}",
        "result": "1-0",
        "date": "2026.10.01",
        "event": "Ranked",
        "time_control": "300+3",
        "speed_category": "Blitz",
        "eco": "C60",
        "opening": "Ruy Lopez",
        "source": "chesscom",
        "pgn": "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0",
        "timestamp": 1_700_000_000 + index,
    }
    row.update(overrides)
    return row


@pytest.fixture()
def manager(tmp_path):
    return GameHistoryManager(str(tmp_path / "query.db"))


class TestFilterSql:
    def test_empty_query_matches_everything(self):
        where, params = build_filters(GameQuery())
        assert where == ""
        assert params == {}

    def test_search_lowercases_and_binds(self):
        where, params = build_filters(GameQuery(search="  Ruy  "))
        assert "LOWER(white) LIKE :q" in where
        assert params == {"q": "%ruy%"}

    def test_search_escapes_like_wildcards(self):
        where, params = build_filters(GameQuery(search="50%_a"))
        assert "ESCAPE" in where
        assert params == {"q": "%50\\%\\_a%"}

    def test_win_needs_a_username(self):
        where, _ = build_filters(GameQuery(result="win"))
        assert where.strip() == "WHERE 0"

    def test_win_is_user_relative(self):
        where, params = build_filters(GameQuery(result="win", usernames=("PlayerA",)))
        assert "result = '1-0' AND LOWER(white) IN (:user0)" in where
        assert "result = '0-1' AND LOWER(black) IN (:user0)" in where
        assert params["user0"] == "playera"

    def test_draw_ignores_users(self):
        where, params = build_filters(GameQuery(result="draw"))
        assert "result = '1/2-1/2'" in where
        assert params == {}

    def test_speed_and_source_are_exact_lowercase(self):
        where, params = build_filters(GameQuery(speed="Rapid", source="Lichess"))
        assert "LOWER(speed_category) = :speed" in where
        assert "LOWER(COALESCE(source, 'file')) = :source" in where
        assert params == {"speed": "rapid", "source": "lichess"}

    @pytest.mark.parametrize(
        "sort_option, expected",
        [
            ("most_moves", "COALESCE(move_count, 0) DESC"),
            ("fewest_moves", "COALESCE(move_count, 0) ASC"),
            ("oldest", "timestamp ASC"),
            ("newest", "timestamp DESC"),
        ],
    )
    def test_order_by_whitelist(self, sort_option, expected):
        assert expected in build_order_by(GameQuery(sort=sort_option))

    def test_unknown_sort_falls_back_to_newest(self):
        assert build_order_by(GameQuery(sort="'; DROP TABLE games; --")) == (
            "timestamp DESC, id DESC"
        )


class TestPaging:
    def test_count_and_pages(self, manager):
        manager.save_games_bulk([_row(i) for i in range(30)])

        assert manager.count_games(GameQuery()) == 30

        first = manager.fetch_games_page(GameQuery(limit=25))
        second = manager.fetch_games_page(GameQuery(limit=25, offset=25))

        assert len(first) == 25
        assert len(second) == 5
        assert {row["id"] for row in first}.isdisjoint({row["id"] for row in second})

    def test_page_rows_never_carry_heavy_payloads(self, manager):
        manager.save_games_bulk([_row(1)])

        row = manager.fetch_games_page(GameQuery())[0]

        assert "pgn" not in row
        assert "moves_json" not in row
        assert row["move_count"] == 3

    def test_sort_by_move_count_uses_the_stored_column(self, manager):
        manager.save_games_bulk(
            [
                _row(1, pgn="1. e4 e5 1-0"),
                _row(2, pgn="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"),
            ]
        )

        shortest = manager.fetch_games_page(GameQuery(sort="fewest_moves"))[0]

        assert shortest["id"] == "g1"

    def test_user_result_filter(self, manager):
        manager.save_games_bulk(
            [
                _row(1, white="PlayerA", black="X", result="1-0"),
                _row(2, white="X", black="PlayerA", result="1-0"),
                _row(3, white="PlayerA", black="X", result="1/2-1/2"),
            ]
        )

        assert manager.count_games(GameQuery(result="win", usernames=("playera",))) == 1
        assert manager.count_games(GameQuery(result="loss", usernames=("playera",))) == 1
        assert manager.count_games(GameQuery(result="draw")) == 1

    def test_export_reads_the_whole_table_not_a_page(self, manager):
        manager.save_games_bulk([_row(i) for i in range(40)])

        # The paged query the list uses is deliberately narrower than export.
        assert len(manager.fetch_games_page(GameQuery(limit=25))) == 25
        assert len(manager.get_all_games(limit=None)) == 40
