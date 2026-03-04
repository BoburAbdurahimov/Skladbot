import os
import re

files = [
    r'bot\states.py',
    r'bot\parser.py',
    r'bot\image.py',
    r'bot\main.py'
]

for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add typing import if not present
    if 'from typing import' not in content:
        content = content.replace('from __future__ import annotations', 'from __future__ import annotations\n\nfrom typing import Optional, Union')
    elif 'Optional' not in content:
        content = content.replace('from typing import', 'from typing import Optional,')

    # Replace specific patterns
    content = content.replace('str | None', 'Optional[str]')
    content = content.replace('tuple[int, int] | None', 'Optional[tuple[int, int]]')
    content = content.replace('tuple[float, float] | None', 'Optional[tuple[float, float]]')
    content = content.replace('ParsedItem | None', 'Optional[ParsedItem]')
    content = content.replace('SkladConfig | None', 'Optional[SkladConfig]')
    content = content.replace('ImageFont.FreeTypeFont | ImageFont.ImageFont', 'Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]')

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Done replacing types!")
