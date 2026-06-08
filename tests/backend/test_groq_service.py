import pytest
from unittest.mock import patch, MagicMock
from src.backend.groq_service import GroqService

class TestGroqService:
    @patch('src.backend.groq_service.Groq')
    def test_init_with_key(self, mock_groq):
        """Test initializing GroqService with a key and custom model."""
        service = GroqService(api_key="test_key", model_name="custom-model")
        assert service.api_key == "test_key"
        assert service.model_name == "custom-model"
        mock_groq.assert_called_once_with(api_key="test_key")
        assert service.client is not None

    @patch('src.backend.groq_service.load_dotenv')
    @patch('src.backend.groq_service.Groq')
    @patch.dict('os.environ', {}, clear=True)
    def test_configure(self, mock_groq, mock_load_dotenv):
        """Test configuring GroqService after initialization."""
        service = GroqService(api_key=None)
        assert service.client is None
        
        service.configure(api_key="new_key", model_name="new-model")
        assert service.api_key == "new_key"
        assert service.model_name == "new-model"
        mock_groq.assert_called_once_with(api_key="new_key")
        assert service.client is not None

    @patch('src.backend.groq_service.Groq')
    def test_generate_summary_success(self, mock_groq):
        """Test successful summary generation with mocked Groq client."""
        # Setup mock client structure
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Game Comment: Brilliant\nSummary: Great game."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion
        
        service = GroqService(api_key="test_key", model_name="test-model")
        summary = service.generate_summary("1. e4 e5", "Analysis: standard open")
        
        assert summary == "Game Comment: Brilliant\nSummary: Great game."
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs['model'] == "test-model"
        assert "1. e4 e5" in call_kwargs['messages'][0]['content']

    @patch('src.backend.groq_service.Groq')
    def test_generate_coach_insights_success(self, mock_groq):
        """Test successful coach insights generation with mocked Groq client."""
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="1. Play better.\n2. Good job.\n3. Nice accuracy."))
        ]
        mock_client.chat.completions.create.return_value = mock_completion
        
        service = GroqService(api_key="test_key", model_name="test-model")
        insights = service.generate_coach_insights("Total games: 10, win rate: 50%")
        
        assert insights == "1. Play better.\n2. Good job.\n3. Nice accuracy."
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs['model'] == "test-model"
        assert "Total games: 10, win rate: 50%" in call_kwargs['messages'][0]['content']

    @patch('src.backend.groq_service.load_dotenv')
    @patch.dict('os.environ', {}, clear=True)
    def test_no_client_errors(self, mock_load_dotenv):
        """Test that methods return configuration error messages when client is not configured."""
        service = GroqService(api_key=None)
        assert service.client is None
        
        summary = service.generate_summary("1. e4", "test")
        assert "Groq API key not configured" in summary
        
        insights = service.generate_coach_insights("test")
        assert "Groq API key not configured" in insights


# ---------------------------------------------------------------------------
# _is_placeholder_key — secret template detection
# ---------------------------------------------------------------------------

class TestIsPlaceholderKey:
    """Unit tests for the placeholder secret detection.

    These cover the patterns the previous implementation missed and the
    ones it already handled, so the detection logic is regression-safe.
    """

    @pytest.mark.parametrize("value", [
        "   ",                   # whitespace only
        "${GROQ_API_KEY}",       # docker / shell substitution
        "${input:openai_key}",   # 1Password CLI
        "${{ secrets.GROQ }}",   # GitHub Actions Jinja
        "<YOUR_KEY_HERE>",       # README placeholder
        "<your-api-key>",        # README placeholder, lower case
        "<insert token>",        # README placeholder, generic
        "xxxxxx",                # redaction artifact
        "XXXX",                  # redaction artifact, upper case
    ])
    def test_detects_placeholder(self, value):
        from src.backend.groq_service import GroqService
        assert GroqService._is_placeholder_key(value) is True

    @pytest.mark.parametrize("value", [
        "gsk_abc123",                     # real Groq key
        "sk-proj-abcdefghijklmnop",       # real OpenAI key
        "sk-1234567890ABCDEF",            # another real-style key
        "lm-studio-local-key",            # custom, not a template
        "my-secret-key",                  # plain string
        "gsk_",                           # very short but not a template
        "${not closed",                   # incomplete syntax
        "<not a placeholder>",            # brackets without 'your'/'key'/'token'
        "x",                              # single x is not 'x+' repeated
    ])
    def test_does_not_flag_real_key(self, value):
        from src.backend.groq_service import GroqService
        assert GroqService._is_placeholder_key(value) is False

    def test_strips_whitespace_before_check(self):
        """A real key surrounded by accidental spaces is still real."""
        from src.backend.groq_service import GroqService
        assert GroqService._is_placeholder_key("  gsk_abc  ") is False
        assert GroqService._is_placeholder_key("  ${VAR}  ") is True
