"""Tests for the Polyglot opening book manager."""
import os
import pytest
from unittest.mock import MagicMock, patch
import chess
from src.backend.analysis.polyglot_book import PolyglotBookManager
from src.backend.analysis.local_book import BookResult


def test_polyglot_manager_init():
    mgr = PolyglotBookManager("/fake/path.bin")
    assert mgr.book_path == "/fake/path.bin"
    assert mgr.reader is None
    assert not mgr.is_available()


@patch("os.path.exists")
@patch("os.path.isfile")
@patch("chess.polyglot.open_reader")
def test_polyglot_manager_open_success(mock_open_reader, mock_isfile, mock_exists):
    mock_exists.return_value = True
    mock_isfile.return_value = True
    mock_reader = MagicMock()
    mock_open_reader.return_value = mock_reader

    mgr = PolyglotBookManager("/fake/path.bin")
    assert mgr.open() is True
    assert mgr.reader == mock_reader
    mock_open_reader.assert_called_once_with("/fake/path.bin")


@patch("os.path.exists")
@patch("os.path.isfile")
@patch("chess.polyglot.open_reader")
def test_polyglot_manager_open_failure(mock_open_reader, mock_isfile, mock_exists):
    mock_exists.return_value = True
    mock_isfile.return_value = True
    mock_open_reader.side_effect = Exception("Cannot open file")

    mgr = PolyglotBookManager("/fake/path.bin")
    assert mgr.open() is False
    assert mgr.reader is None


@patch("os.path.exists")
@patch("os.path.isfile")
@patch("chess.polyglot.open_reader")
def test_polyglot_manager_process_move_success(mock_open_reader, mock_isfile, mock_exists):
    mock_exists.return_value = True
    mock_isfile.return_value = True
    mock_reader = MagicMock()
    mock_open_reader.return_value = mock_reader

    # Mock entry responses
    mock_entry1 = MagicMock()
    mock_entry1.move = chess.Move.from_uci("e2e4")
    mock_entry2 = MagicMock()
    mock_entry2.move = chess.Move.from_uci("d2d4")
    mock_reader.find_all.return_value = [mock_entry1, mock_entry2]

    mgr = PolyglotBookManager("/fake/path.bin")
    
    # Process valid book move
    result = mgr.process_move(chess.STARTING_FEN, "e2e4", 1)
    assert result.is_book is True
    assert result.book_move_count == 1
    assert "e2e4" in result.candidate_moves
    assert "d2d4" in result.candidate_moves

    # Reset traversal state
    mgr.reset()
    assert mgr._count == 0
    assert mgr._exited is False


@patch("os.path.exists")
@patch("os.path.isfile")
@patch("chess.polyglot.open_reader")
def test_polyglot_manager_process_move_exit(mock_open_reader, mock_isfile, mock_exists):
    mock_exists.return_value = True
    mock_isfile.return_value = True
    mock_reader = MagicMock()
    mock_open_reader.return_value = mock_reader
    mock_reader.find_all.return_value = []  # No moves found -> exit book

    mgr = PolyglotBookManager("/fake/path.bin")
    
    # Process move leading to non-book position
    result = mgr.process_move(chess.STARTING_FEN, "h2h3", 1)
    assert result.is_book is False
    assert result.book_exit_move == 1

    # Subsequent moves should instantly report exit
    result2 = mgr.process_move(chess.STARTING_FEN, "e2e4", 2)
    assert result2.is_book is False
    assert result2.book_exit_move == 1
