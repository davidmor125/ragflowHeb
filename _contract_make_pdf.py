import sys
sys.stdout.reconfigure(encoding='utf-8')
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bidi.algorithm import get_display

pdfmetrics.registerFont(TTFont('Heb', r'C:\Windows\Fonts\arial.ttf'))

W, H = A4
c = canvas.Canvas('_contract_testdoc_vision.pdf', pagesize=A4)

def rtl(line):
    return get_display(line)

def text_block(lines, y, size=12, leading=18):
    c.setFont('Heb', size)
    for ln in lines:
        c.drawRightString(W-50, y, rtl(ln))
        y -= leading
    return y

y = H-60
c.setFont('Heb', 16)
c.drawRightString(W-50, y, rtl('דוח בדיקה גנרי — מערכת RAGFLOW (גרסת PDF)')); y -= 26
y = text_block([
    '[כותרת-ראשית: מסמך-בדיקה-12345-PDF]',
    '',
    'רקע: המערכת מספקת שירותי אחזור מידע מבוסס הקשר ותומכת בעברית מלאה.',
    'עיבוד מסמכים: התהליך כולל זיהוי פריסה, חילוץ טבלאות ותיאור תמונות.',
    'מודל ההטמעה הוא bge-m3 והוא רב-לשוני.',
    'מסמך זה כולל תרשים מכירות רבעוני כתמונה. הקוד הסודי בקובץ זה הוא PDFKEY77.',
    '',
    'תרשים המכירות הרבעוני:',
], y)

img_w, img_h = 420, 235
c.drawImage('_contract_chart.png', W-50-img_w, y-img_h-8, width=img_w, height=img_h)
y = y-img_h-30

y = text_block([
    'התמונה לעיל מציגה נתוני מכירות לפי רבעונים Q1 עד Q4.',
    'סיכום: RAGFLOW הוא שירות RAG גנרי המתאים למגוון סוגי קבצים.',
], y)

c.showPage()
c.save()
import os
print('PDF written:', os.path.getsize('_contract_testdoc_vision.pdf'), 'bytes')
