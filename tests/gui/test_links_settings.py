# SPDX-License-Identifier: GPL-3.0-only
"""The About card is the app's legal-notice surface.

GPLv3 §5(d) requires modified versions with interactive interfaces to display
Appropriate Legal Notices, and the §7 additional terms in
LICENSE-ADDITIONAL-TERMS.md require the copyright and licence to stay visible
there. These tests keep that surface wired to the canonical URLs.
"""

from src.constants import GITHUB_REPO_URL, LICENSE_URL, NOTICES_URL


def test_about_card_shows_copyright_and_licence(qapp, qtbot):
    from src.gui.views.settings.links_settings import LinksSettings

    card = LinksSettings()
    qtbot.addWidget(card)

    text = card.license_note.text()
    assert "GPL-3.0" in text
    assert "Utkarsh Tiwari" in text
    assert "contributors" in text


def test_about_card_links_to_licence_and_notices(qapp, qtbot, mocker):
    from src.gui.views.settings.links_settings import LinksSettings

    card = LinksSettings()
    qtbot.addWidget(card)
    open_mock = mocker.patch.object(card, "_open")

    card.open_license()
    card.open_notices()

    opened = [call.args[0] for call in open_mock.call_args_list]
    assert opened == [LICENSE_URL, NOTICES_URL]
    assert LICENSE_URL.startswith(GITHUB_REPO_URL)
