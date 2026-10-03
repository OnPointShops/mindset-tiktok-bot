#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Installiert tiktokautouploader OHNE seine Mega-Dependency "inference"
# (Roboflow Computer-Vision-Paket, wird vom Bot nie benutzt, zieht aber fastapi/
# boto3/opencv/huggingface_hub/imageio etc. mit extrem weiten Versions-Ranges mit
# sich -> pip hängt sich beim normalen "pip install -r requirements.txt" stunden-
# lang im Backtracking auf, sobald sich irgendwas anderes in requirements.txt
# ändert).
#
# --no-deps installiert NUR das Paket selbst, ohne seine Requires-Dist-Liste
# aufzulösen. Die paar echten Laufzeit-Abhängigkeiten (phantomwright, pillow,
# requests, scikit-learn, setuptools) stehen ganz normal in requirements.txt und
# werden dort aufgelöst — die laufen nie in den inference-Konflikt.
#
# Aufruf: bash install_tiktok_uploader.sh
# Wird von setup_mac.sh automatisch aufgerufen. Danach nie wieder "inference"
# oder eine der Versionen davon in Logs — egal was später noch zu requirements.txt
# hinzukommt.
# ══════════════════════════════════════════════════════════════════════════════
set -e
echo "Installiere tiktokautouploader (--no-deps, damit pip 'inference' nie anfasst)..."
pip3 install --break-system-packages --no-deps --upgrade "tiktokautouploader==6.1"
echo "✓ tiktokautouploader fertig (ohne inference-Rattenschwanz)"
