# Build a generic Hebrew acceptance doc: ~20 paragraphs + table + mermaid + image ref
import base64
img_b64 = base64.b64encode(open('_contract_chart.png','rb').read()).decode()
lines = []
lines.append("# דוח בדיקה גנרי — מערכת RAGFLOW\n")
lines.append("[כותרת-ראשית: מסמך-בדיקה-12345]\n")  # inline anchor marker (client-style) to test survival
topics = [
 ("רקע","המערכת מספקת שירותי אחזור מידע מבוסס הקשר. היא תומכת בעברית מלאה."),
 ("ארכיטקטורה","הרכיב המרכזי מחלק מסמכים למקטעים, מחשב embedding, ומאחסן באינדקס וקטורי."),
 ("עיבוד מסמכים","תהליך העיבוד כולל זיהוי פריסה, חילוץ טבלאות, ותיאור תמונות."),
 ("הטמעות","מודל ההטמעה הוא bge-m3 והוא רב-לשוני."),
 ("אחזור","בעת שאילתה, המערכת מאחזרת את המקטעים הרלוונטיים ביותר לפי דמיון וקטורי."),
 ("דירוג-מחדש","שכבת דירוג-מחדש משפרת את הדיוק על ידי מיון מקטעים מועמדים."),
 ("ניסוח-תשובה","מודל שפה גדול מנסח תשובה על בסיס המקטעים שאוחזרו בלבד."),
 ("ציטוטים","כל תשובה כוללת הפניות למקורות שמהם חולצה."),
 ("העשרה","המערכת מייצרת מילות מפתח ושאלות אוטומטיות לכל מקטע."),
 ("סיכומים","שכבת raptor בונה סיכומים היררכיים של אשכולות מקטעים."),
 ("מטא-דאטה","ניתן לחלץ מטא-דאטה מובנית כגון נושא ותאריך."),
 ("ראייה-ממוחשבת","תמונות בתוך מסמכים מתוארות אוטומטית למלל."),
 ("ביצועים","זמן העיבוד תלוי בגודל הקובץ ובמספר התמונות."),
 ("אבטחה","הגישה מאובטחת באמצעות מפתח API ייחודי לכל דייר."),
 ("רב-דיירות","כל דייר מבודד עם אינדקס ומודלים משלו."),
 ("תאימות","השירות נגיש דרך HTTP API סטנדרטי בפורמט JSON."),
 ("שפות","המערכת תומכת בעברית, אנגלית, וערבית."),
 ("מגבלות","גודל מקטע מרבי הוא 2048 אסימונים."),
 ("תחזוקה","יש לנטר את תור המשימות של מעבדי הרקע."),
 ("סיכום","RAGFLOW הוא שירות RAG גנרי המתאים למגוון פרויקטים."),
]
for i,(t,b) in enumerate(topics,1):
    lines.append(f"## {i}. {t}\n\n{b}\n")
# table
lines.append("## טבלת מפרט טכני\n")
lines.append("| רכיב | ערך | יחידה |")
lines.append("|---|---|---|")
lines.append("| גודל מקטע מרבי | 2048 | אסימונים |")
lines.append("| מודל הטמעה | bge-m3 | - |")
lines.append("| מספר דיירים נתמך | 500 | דיירים |")
lines.append("| זמן תגובה ממוצע | 850 | מילישניות |")
lines.append("| קוד-סודי-בטבלה | ZX9871 | מזהה |\n")  # unique fact only in table
# mermaid diagram
lines.append("## תרשים זרימה\n")
lines.append("```mermaid")
lines.append("graph TD")
lines.append("  A[קובץ נכנס] --> B[חלוקה למקטעים]")
lines.append("  B --> C[חישוב הטמעה]")
lines.append("  C --> D[אחזור ודירוג]")
lines.append("  D --> E[ניסוח תשובה עם MERMAIDKEY42]")  # unique fact only in diagram
lines.append("```\n")
# image
lines.append("## תרשים מכירות רבעוני\n")
lines.append(f"![תרשים מכירות](data:image/png;base64,{img_b64})\n")
lines.append("התמונה לעיל מציגה נתוני מכירות רבעוניים.\n")
open('_contract_testdoc.md','w',encoding='utf-8').write("\n".join(lines))
print("testdoc created: _contract_testdoc.md (%d KB)" % (len("\n".join(lines))//1024))
print("hidden facts: table=ZX9871, mermaid=MERMAIDKEY42, image=Q4/260, anchor=[כותרת-ראשית: מסמך-בדיקה-12345]")
