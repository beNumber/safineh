import csv
import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree
from xml.sax.saxutils import escape


MAX_ROWS = 10000


def header_key(value):
    return re.sub(r"[\s\u200c_()（）]+", "", str(value or "").strip().replace("ي", "ی").replace("ك", "ک")).casefold()


def xlsx_rows(upload):
    with zipfile.ZipFile(upload) as archive:
        if sum(item.file_size for item in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError("حجم بازشده فایل Excel بیش از حد مجاز است.")
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relations}
        sheets = [node for node in workbook.iter() if node.tag.endswith("}sheet")]
        sheet = next((item for item in sheets if header_key(item.attrib.get("name")) in {"اعضا", "کاربران", "members"}), sheets[0])
        relation = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
        target = targets[relation]
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        if not path.startswith("xl/"):
            raise ValueError("مسیر شیت Excel معتبر نیست.")
        root = ElementTree.fromstring(archive.read(path))
        for number, row in enumerate((node for node in root.iter() if node.tag.endswith("}row")), 1):
            if number > MAX_ROWS + 1:
                raise ValueError("هر فایل حداکثر می‌تواند ۱۰۰۰۰ ردیف داده داشته باشد.")
            values = []
            for cell in (node for node in row if node.tag.endswith("}c")):
                reference = re.match(r"[A-Za-z]+", cell.attrib.get("r", "A1")).group().upper()
                column = 0
                for letter in reference:
                    column = column * 26 + ord(letter) - 64
                if column > 100:
                    raise ValueError("تعداد ستون‌های فایل بیش از حد مجاز است.")
                values.extend([""] * max(0, column - len(values)))
                value_node = next((node for node in cell if node.tag.endswith("}v")), None)
                value = value_node.text or "" if value_node is not None else ""
                if cell.attrib.get("t") == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                elif cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
                values[column - 1] = value
            yield int(row.attrib.get("r", number)), values


def read_spreadsheet(upload, aliases, required=()):
    upload.seek(0)
    if upload.name.lower().endswith(".xlsx"):
        rows = list(xlsx_rows(upload))
    elif upload.name.lower().endswith(".csv"):
        data = upload.read()
        for encoding in ("utf-8-sig", "utf-16", "cp1256"):
            try:
                content = data.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ValueError("کدگذاری فایل CSV قابل خواندن نیست.")
        try:
            dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(enumerate(csv.reader(io.StringIO(content), dialect), 1))
    else:
        raise ValueError("فقط فایل‌های xlsx و csv قابل قبول هستند.")
    rows = [(number, row) for number, row in rows if any(str(value or "").strip() for value in row)]
    if not rows:
        return []
    if len(rows) > MAX_ROWS + 1:
        raise ValueError("هر فایل حداکثر می‌تواند ۱۰۰۰۰ ردیف داده داشته باشد.")
    lookup = {header_key(key): value for key, value in aliases.items()}
    headers = [lookup.get(header_key(value), str(value or "").strip().lower()) for value in rows[0][1]]
    named = [value for value in headers if value]
    if len(named) != len(set(named)):
        raise ValueError("نام ستون‌های فایل تکراری است.")
    missing = set(required) - set(headers)
    if missing:
        labels = {value: key for key, value in aliases.items()}
        raise ValueError("ستون‌های اصلی فایل ناقص است: " + "، ".join(labels.get(key, key) for key in sorted(missing)))
    return [dict({headers[index]: str(value or "").strip() for index, value in enumerate(row)
                  if index < len(headers) and headers[index]}, _row_number=number) for number, row in rows[1:]]


def build_spreadsheet(headers, rows=()):
    data = [headers, *rows]
    xml_rows = []
    for number, values in enumerate(data, 1):
        cells = []
        for index, value in enumerate(values, 1):
            letters = ""
            while index:
                index, remainder = divmod(index - 1, 26)
                letters = chr(65 + remainder) + letters
            cells.append(f'<c r="{letters}{number}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>')
        xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="داده‌ها" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0" rightToLeft="1"/></sheetViews><sheetData>' + "".join(xml_rows) + '</sheetData></worksheet>')
    return output
