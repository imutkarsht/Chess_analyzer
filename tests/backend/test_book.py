import pytest
from unittest.mock import patch, MagicMock
from src.backend.book import BookManager

class TestBookManager:
    @patch('src.backend.book.ConfigManager')
    def test_get_headers_with_token(self, mock_config):
        """Test headers contain Lichess token from ConfigManager."""
        mock_instance = MagicMock()
        mock_instance.get.return_value = "lip_testtoken"
        mock_config.return_value = mock_instance
        
        manager = BookManager()
        headers = manager._get_headers()
        assert headers["Authorization"] == "Bearer lip_testtoken"
        assert "User-Agent" in headers

    @patch('src.backend.book.ConfigManager')
    @patch.dict('os.environ', {}, clear=True)
    def test_get_headers_no_token(self, mock_config):
        """Test headers do not contain Authorization when no token is set."""
        mock_instance = MagicMock()
        mock_instance.get.return_value = None
        mock_config.return_value = mock_instance
        
        manager = BookManager()
        headers = manager._get_headers()
        assert "Authorization" not in headers

    @patch('src.backend.book.ConfigManager')
    def test_get_opening_name_success(self, mock_config):
        """Test get_opening_name with mocked API response."""
        mock_instance = MagicMock()
        mock_instance.get.return_value = "test_token"
        mock_config.return_value = mock_instance
        
        manager = BookManager()
        
        # Mock requests session get
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "opening": {
                "name": "King's Pawn Game"
            }
        }
        manager.session.get = MagicMock(return_value=mock_response)
        
        # Starting FEN: standard initial position
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        opening = manager.get_opening_name(fen, "e2e4")
        
        assert opening == "King's Pawn Game"
        manager.session.get.assert_called_once()
        call_kwargs = manager.session.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test_token"

    @patch('src.backend.book.ConfigManager')
    def test_is_book_move_true(self, mock_config):
        """Test is_book_move returns True if move is in master database."""
        mock_instance = MagicMock()
        mock_instance.get.return_value = "test_token"
        mock_config.return_value = mock_instance
        
        manager = BookManager()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "moves": [
                {"uci": "e2e4", "san": "e4"}
            ]
        }
        manager.session.get = MagicMock(return_value=mock_response)
        
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        is_book = manager.is_book_move(fen, "e2e4")
        
        assert is_book is True
        manager.session.get.assert_called_once()
