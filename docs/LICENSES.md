# Dependency licensing

Upstream license references (verify again before redistribution; transitive dependencies and bundled binaries also require review):

| Component                                                          | License                                  | Upstream                                                                   |
| ------------------------------------------------------------------ | ---------------------------------------- | -------------------------------------------------------------------------- |
| PyMuPDF                                                            | AGPL-3.0 / commercial dual license       | https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright  |
| FastAPI, python-docx, React, Vite, Tailwind, lucide-react, dnd-kit | MIT                                      | Respective installed package metadata / upstream LICENSE                   |
| Uvicorn, pytesseract                                               | BSD-3-Clause / Apache-2.0 respectively   | https://github.com/encode/uvicorn / https://github.com/madmaze/pytesseract |
| Pillow                                                             | MIT-CMU / HPND                           | https://pillow.readthedocs.io/en/stable/about.html#license                 |
| Tesseract                                                          | Apache-2.0                               | https://github.com/tesseract-ocr/tesseract                                 |
| LibreOffice                                                        | MPL-2.0 (other included components vary) | https://www.libreoffice.org/about-us/licenses/                             |

External binaries are installed separately, not bundled by this project. No paid API is required. PyMuPDF's AGPL obligations are material; see ARCHITECTURE.md. Signature drawings are visual marks, not cryptographic signatures.

- pypdf 5.9.0: BSD-3-Clause (installed metadata verified).
- Bundled DejaVu Sans font: Bitstream Vera / DejaVu license; full notice in backend/app/fonts/LICENSE.txt.

Package metadata was inspected locally. The upstream documentation host was blocked by network policy; PyMuPDF wheel metadata confirms the dual AGPL/commercial license.
