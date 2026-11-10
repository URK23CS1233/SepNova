import zipfile
import xml.etree.ElementTree as ET

docx_path = r'B.Tech Honors Program (2023-2027 Batch)_Zeroth Review FORM.docx'

with zipfile.ZipFile(docx_path, 'r') as z:
    with z.open('word/document.xml') as f:
        tree = ET.parse(f)
        root = tree.getroot()

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

paragraphs = root.findall('.//w:p', ns)
for i, p in enumerate(paragraphs):
    texts = p.findall('.//w:t', ns)
    line = ''.join([t.text for t in texts if t.text])
    if line.strip():
        print(f'P{i}: {line}')

tables = root.findall('.//w:tbl', ns)
print(f'\n=== Found {len(tables)} tables ===')
for ti, table in enumerate(tables):
    rows = table.findall('.//w:tr', ns)
    print(f'\nTable {ti}: {len(rows)} rows')
    for ri, row in enumerate(rows):
        cells = row.findall('.//w:tc', ns)
        cell_texts = []
        for cell in cells:
            texts = cell.findall('.//w:t', ns)
            cell_text = ''.join([t.text for t in texts if t.text])
            cell_texts.append(cell_text)
        joined = ' | '.join(cell_texts)
        print(f'  Row {ri}: {joined}')
