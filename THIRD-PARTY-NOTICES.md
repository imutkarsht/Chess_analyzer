# Third-Party Notices

Chess Analyzer Pro
Copyright (C) 2025-2026 Utkarsh Tiwari and Chess Analyzer Pro contributors

Licensed under **GNU GPL version 3 only**; the section 7 additional terms are
recorded in [`LICENSE`](LICENSE).

This file records the third-party material committed to this repository and the
libraries bundled into packaged builds. Full licence texts for the bundled
Python packages are copied into the packaged application at build time (see
`build.spec`) — they are not vendored here.

Versions below reflect the 2.6.0 release environment. Run
`pip freeze` for the exact set in a given build.

---

## Bundled Python packages

| Package | Version | Licence | Upstream |
|---|---|---|---|
| annotated-types | 0.7.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.13.0 | MIT | https://github.com/agronholm/anyio |
| certifi | 2026.5.20 | MPL-2.0 | https://github.com/certifi/python-certifi |
| charset-normalizer | 3.4.7 | MIT | https://github.com/jawah/charset_normalizer |
| colorama | 0.4.6 | BSD-3-Clause | https://github.com/tartley/colorama |
| contourpy | 1.3.3 | BSD-3-Clause | https://github.com/contourpy/contourpy |
| cycler | 0.12.1 | BSD-3-Clause | https://github.com/matplotlib/cycler |
| defusedxml | 0.7.1 | PSF-2.0 | https://github.com/tiran/defusedxml |
| distro | 1.9.0 | Apache-2.0 | https://github.com/python-distro/distro |
| fonttools | 4.63.0 | MIT | https://github.com/fonttools/fonttools |
| groq | 1.4.0 | Apache-2.0 | https://github.com/groq/groq-python |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://github.com/encode/httpcore |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| idna | 3.18 | BSD-3-Clause | https://github.com/kjd/idna |
| jaraco.classes | 3.4.0 | MIT | https://github.com/jaraco/jaraco.classes |
| jaraco.context | 6.1.2 | MIT | https://github.com/jaraco/jaraco.context |
| jaraco.functools | 4.6.0 | MIT | https://github.com/jaraco/jaraco.functools |
| jiter | 0.15.0 | MIT | https://github.com/pydantic/jiter |
| keyring | 25.7.0 | MIT | https://github.com/jaraco/keyring |
| kiwisolver | 1.5.0 | BSD-3-Clause | https://github.com/nucleic/kiwi |
| matplotlib | 3.10.9 | Matplotlib License (PSF-based) | https://github.com/matplotlib/matplotlib |
| more-itertools | 11.2.1 | MIT | https://github.com/more-itertools/more-itertools |
| numpy | 2.4.6 | BSD-3-Clause | https://github.com/numpy/numpy |
| openai | 2.41.0 | Apache-2.0 | https://github.com/openai/openai-python |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pillow | 12.2.0 | MIT-CMU | https://github.com/python-pillow/Pillow |
| pydantic | 2.13.4 | MIT | https://github.com/pydantic/pydantic |
| pydantic-core | 2.46.4 | MIT | https://github.com/pydantic/pydantic |
| pyparsing | 3.3.2 | MIT | https://github.com/pyparsing/pyparsing |
| PyQt6 | 6.11.0 | GPL-3.0-only or commercial | https://www.riverbankcomputing.com/software/pyqt |
| PyQt6-Qt6 | 6.11.1 | GPLv3 / LGPLv3 | https://www.riverbankcomputing.com/software/pyqt |
| PyQt6-sip | 13.11.1 | BSD-2-Clause | https://github.com/Python-SIP/sip |
| python-chess | 1.999 | GPL-3.0+ | https://github.com/niklasf/python-chess |
| python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause | https://github.com/dateutil/dateutil |
| python-dotenv | 1.2.2 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| QtAwesome | 1.4.2 | MIT | https://github.com/spyder-ide/qtawesome |
| QtPy | 2.4.3 | MIT | https://github.com/spyder-ide/qtpy |
| requests | 2.34.2 | Apache-2.0 | https://github.com/psf/requests |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| sniffio | 1.3.1 | MIT OR Apache-2.0 | https://github.com/python-trio/sniffio |
| tqdm | 4.68.1 | MPL-2.0 AND MIT | https://github.com/tqdm/tqdm |
| typing_extensions | 4.15.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| typing-inspection | 0.4.2 | MIT | https://github.com/pydantic/typing-inspection |
| urllib3 | 2.7.0 | MIT | https://github.com/urllib3/urllib3 |

PyQt6 and python-chess are GPL-3.0; this project is distributed under the same
licence family, so the combination is permitted. Qt itself is used under its
GPLv3 option, which the GPLv3 text in [`LICENSE`](LICENSE) covers.

---

## Committed assets

### Chess piece graphics — Cburnett

`assets/pieces/*.svg` — by Colin M.L. Burnett, via Wikimedia Commons. Upstream
dual-licensed under **GPLv2+** and CC BY-SA 3.0; this project uses the GPLv2+
option, which combines with GPLv3.

> Chess piece graphics by Colin M.L. Burnett, distributed via Wikimedia
> Commons and used in the Lichess project.
> <https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces>

This attribution must be preserved with any redistribution of those files. See
[`assets/pieces/THIRD-PARTY-README.md`](assets/pieces/THIRD-PARTY-README.md).

### Chess openings database — Lichess

`assets/openings/*.tsv` — compiled from
[lichess-org/chess-openings](https://github.com/lichess-org/chess-openings),
dedicated to the public domain under **CC0 1.0**. See
[`assets/openings/THIRD-PARTY-README.md`](assets/openings/THIRD-PARTY-README.md).

### Icon fonts — via QtAwesome

Bundled font files retain their upstream licences:

| Pack | Icons | Fonts | Code |
|---|---|---|---|
| Font Awesome Free 5.15.4 | CC BY 4.0 | SIL OFL 1.1 | MIT |
| Codicon | MIT | — | MIT |
| Elusive Icons 2.0 | — | SIL OFL 1.1 | MIT |
| Material Design Icons | Apache-2.0 | SIL OFL 1.1 | Apache-2.0 |

Sources: <https://fontawesome.com/license/free>,
<https://github.com/microsoft/vscode-codicons>,
<https://github.com/dovy/elusive-icons>,
<https://github.com/google/material-design-icons>.

### Fonts — via Matplotlib

Matplotlib bundles the DejaVu font family, derived from Bitstream Vera and
distributed under the Bitstream Vera Fonts licence (permissive, notice
required): <https://dejavu-fonts.github.io/License.html>.

### Original assets

Sound effects (`assets/sounds/`) are generated by this project and dedicated to
the public domain under CC0 1.0. Application icons and illustrations were
created for this project and are covered by its GPL-3.0 licence.

Chess.com and Lichess logos are trademarks of their respective owners and are
used nominatively to identify the source of imported games. No affiliation or
endorsement is implied.

---

## Separate programs — not distributed with this application

**Stockfish** (GPLv3) is a separate chess engine. It is not bundled: it is
supplied by the user or downloaded at runtime, and invoked as a separate process
over the UCI protocol. Its licence does not extend to this work.