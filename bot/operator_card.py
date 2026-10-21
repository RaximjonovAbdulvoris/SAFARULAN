"""One operator message containing the application and OCR results."""
from html import escape

from bot.document_ocr import review_warnings


def render_card(code, applicant_link, entered_name, phone, plate, result=None):
    values = (result or {}).get('values') or {}
    def cell(value):
        return f'<code>{escape(str(value))}</code>' if value else '⚠️ Aniqlanmadi — tekshiring'

    lines = ['<b>WB SAFAR TAXI · HAYDOVCHI ARIZASI</b>',
             f'Ariza: {escape(code)}', '',
             '<b>Arizachi</b>', applicant_link, '',
             f'Familiya: {cell(values.get("surname"))}',
             f'Ism: {cell(values.get("given_name"))}',
             f'Tug‘ilgan sana: {cell(values.get("birth_date"))}',
             f'Telefon raqami: {cell(phone)}',
             f'PINFL: {cell(values.get("pinfl"))}',
             f'Tug‘ilgan joy: {cell(values.get("birth_place"))}',
             f'Prava raqami: {cell(values.get("license_number"))}',
             f'Amal qilish muddati: {cell(values.get("license_expiry"))}',
             f'Avtomobil raqami: {cell(plate)}',
             f'Texpasport seriya raqami: {cell(values.get("vehicle_registration"))}']
    if entered_name:
        if values.get('surname') and values.get('given_name'):
            actual = {part.casefold() for part in (values['surname'], values['given_name'])}
            entered = {part.casefold() for part in entered_name.split()}
            if not actual.issubset(entered):
                lines.append('⚠️ Kiritilgan ism hujjatdagi ismga mos kelmasligi mumkin.')
    if result is None:
        lines.append('🔎 Hujjatlar o‘qilmoqda. Operator asl rasmlarni tekshiradi.')
    else:
        if result.get('status') == 'unavailable':
            lines.append('⚠️ OCR ishlamadi — ma’lumotlarni qo‘lda tekshiring.')
        for warning in review_warnings(values):
            lines.append('⚠️ ' + escape(warning))
        lines.append('OCR natijasini hujjat bilan solishtiring.')
    lines.extend(['', '<b>Operator boshqaruvi</b>', 'Quyidagi amallardan birini tanlang.'])
    return '\n'.join(lines)
