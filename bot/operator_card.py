"""One operator message containing the application and OCR results."""
from html import escape

from bot.document_ocr import FIELDS, review_warnings


def render_card(code, applicant_link, entered_name, phone, plate, result=None):
    values = (result or {}).get('values') or {}
    def cell(value):
        return f'<code>{escape(str(value))}</code>' if value else '⚠️ Aniqlanmadi — tekshiring'

    lines = [f'📋 <b>WB SAFAR TAXI · {escape(code)}</b>',
             f'👤 Arizachi: {applicant_link}',
             f'Familiya: {cell(values.get("surname"))}',
             f'Ism: {cell(values.get("given_name"))}',
             f'Telefon: {cell(phone)}',
             f'Avtomobil raqami: {cell(plate)}']
    if entered_name:
        lines.append(f'Arizachi kiritgan ism: {cell(entered_name)}')
        if values.get('surname') and values.get('given_name'):
            actual = {part.casefold() for part in (values['surname'], values['given_name'])}
            entered = {part.casefold() for part in entered_name.split()}
            if not actual.issubset(entered):
                lines.append('⚠️ Kiritilgan ism hujjatdagi ismga mos kelmasligi mumkin.')
    for field, label in FIELDS.items():
        lines.append(f'{label}: {cell(values.get(field))}')
    if result is None:
        lines.append('🔎 Hujjatlar o‘qilmoqda. Operator asl rasmlarni tekshiradi.')
    else:
        if result.get('status') == 'unavailable':
            lines.append('⚠️ OCR ishlamadi — ma’lumotlarni qo‘lda tekshiring.')
        for warning in review_warnings(values):
            lines.append('⚠️ ' + escape(warning))
        lines.append('OCR natijasini asl hujjatlar bilan solishtiring.')
    return '\n'.join(lines)
