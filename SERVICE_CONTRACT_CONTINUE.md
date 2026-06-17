# המשך עבודה — RAGFLOW Service Contract (סעיפים 3–6 + כתיבת ה-deliverable)

מסמך זה ממשיך את [`SERVICE_CONTRACT_BRIEF.md`](SERVICE_CONTRACT_BRIEF.md).
הסשן הקודם נסגר באמצע: **סעיפים 1–2 הושלמו ואומתו**, סעיפים 3–6 וה-deliverable
לא בוצעו. אל תחזור על מה שכבר אומת — תוצרי ההרצה שמורים ב-`_contract_out/`.

## לפני הכול — סביבה

- ייתכן ש-Docker Desktop כבוי. להרים אותו, לוודא שה-stack של RAGFlow רץ
  (`docker ps` — ragflow-server על 9380), ורק אז להתחיל.
- כל הקריאות ב-python/requests או httpx בלבד עם UTF-8 — **לא** shell-curl
  (עברית נשברת). ה-harness הקיים: [`_contract_run.py`](_contract_run.py).
- Base: `http://localhost:9380/api/v1` | המפתח בתוך `_contract_run.py`.

## מה כבר אומת (לא לבדוק שוב — רק לצטט ב-deliverable)

| מה | הוכחה |
|---|---|
| `POST /datasets` עם pipeline ההעשרה — `parser_config: {chunk_token_num:512, layout_recognize:"DeepDOC", auto_keywords:3, auto_questions:2}` | `_contract_out/s1_create_request.json` + `s1_create_response.json` |
| העלאה (multipart) + הפעלת parse דרך `POST /datasets/{id}/chunks` + polling עד `run="3"`/DONE | `s2_upload_response.json`, `s2_doc_final.json` |
| **ההעשרה עובדת**: ה-chunks חוזרים עם `important_keywords` ו-`questions` אוטומטיים בעברית תקינה | `s2_chunks.json` |
| **סימוני inline שורדים** את ה-chunking: עוגן `[כותרת-ראשית: מסמך-בדיקה-12345]` ✔, סוד טבלה `ZX9871` ✔, מפתח mermaid `MERMAIDKEY42` ✔ | `s2_chunks.json` |
| מסמך הבדיקה הגנרי (עברית, ~20 פסקאות, טבלה, mermaid, תמונה) קיים ומוכן | `_contract_testdoc.md` (+ `_contract_chart.png` משובצת בו) |

מלכודות מאומתות (לשמר ב-deliverable): אין `type=empty` בגרסה זו; parse רק דרך
`POST /datasets/{id}/chunks`; עברית רק דרך python.

## מה נשאר — לפי סדר עדיפות

### עדיפות 1 — סעיף 5: Chat assistants וסכמת `reference` (פרויקטי הלקוח חסומים על זה)

1. `POST /api/v1/chats` — יצירת assistant עם `dataset_ids` של dataset הבדיקה
   ו-system prompt **בעברית** שהלקוח מספק. לתעד את הפורמט המחייב של משתני
   התבנית (`{knowledge}` — חובה? איפה?).
2. `POST /chats/{id}/sessions` ואז `POST /chats/{id}/completions` —
   request/response מלאים גם ב-`stream=false` וגם ב-`stream=true`.
3. **הדבר הקריטי ביותר**: לתעד את הסכמה המלאה של `reference` בתשובה —
   כל שדה (content, document_id, dataset_id, positions, similarity...).
   לאמת במפורש: ה-`content` של chunk מצוטט חוזר **כלשונו**, כולל סימוני
   inline כמו העוגן `[כותרת-ראשית: ...]` — לקוחות ממפים מהם חזרה ל-UI.
4. לאמת שהתשובות חוזרות בעברית תקינה.
5. פרמטרי איכות: `similarity_threshold`, `top_n`, `temperature` — ערכים
   מומלצים גנרית + מאיפה נקבעים.

### עדיפות 2 — סעיף 3: VISION (תמונות בתוך מסמכים)

בהרצת הלילה תיאור התמונה **לא נמצא** ב-chunks (`s2_chunks.json` — אין את תוכן
הגרף מ-`_contract_chart.png`). כלומר מודל img2txt כנראה לא מחובר.

1. לבדוק איזה מודל img2txt רשום ל-tenant (זמינים מקומית ב-Ollama:
   qwen2.5vl:7b, minicpm-v). אם לא מחובר — לחבר אחד ברמת השירות (גנרית).
2. לתעד איך לקוח מפעיל VISION לרמת dataset דרך ה-API (`parser_config`? שדה אחר?).
3. להריץ מחדש את parse על `_contract_testdoc.md` ולאמת: ה-chunks כוללים תיאור
   טקסטואלי של הגרף (markers לבדיקה: הערכים שבתמונה — "260", רבעונים Q1–Q4).

### עדיפות 3 — סעיף 4: Rerank

- `qllama/bge-reranker-v2-m3` קיים מקומית. לתעד: מה ה-`rerank_id` המדויק,
  איפה נקבע (dataset / chat / פרמטר `/retrieval`), ולמדוד על שאלה אחת:
  זמן תשובה עם/בלי + האם הדיוק השתפר. המלצה גנרית: כן/לא כברירת מחדל.

### עדיפות 4 — סעיף 6: בדיקת קבלה + זמנים

1. על ה-dataset וה-assistant מהסעיפים הקודמים, לשאול 3 שאלות:
   - עובדה מפסקה רגילה
   - עובדה מהטבלה (התשובה חייבת לכלול `ZX9871`)
   - שאלה שעונים עליה רק מה-mermaid (`MERMAIDKEY42`) או מהתמונה (מבחן VISION)
2. לאמת שה-`reference` בכל תשובה מצביע על ה-chunk הנכון ושסימוני ה-inline
   שרדו בתוכו.
3. **מדידות זמנים** (חסר לגמרי): parse ל-md של ~200KB; ל-PDF עם תמונות;
   ל-dataset של 3–4 קבצים מעורבים. לרשום שניות בפועל — לקוחות צריכים את זה
   ל-UX של "בונה אינדקס".

### לסיום — כתיבת ה-deliverable

מסמך אחד: **`SERVICE_CONTRACT.md`** ("RAGFLOW Service Contract") — בסגנון
`RAGFLOW_API_GUIDE.md` (שאומת בעבר והיה מצוין): כל ה-JSON-ים המאומתים
(request+response), סכמת `reference` המלאה, rerank, זמני parse שנמדדו,
ורשימת "הערות ומלכודות מאומתות". המסמך גנרי — בלי שום אזכור ספציפי
לפרויקט לקוח כלשהו.

## הגדרת "סיום"

- [ ] `SERVICE_CONTRACT.md` קיים בשורש הריפו ומכסה את כל 6 הסעיפים
- [ ] כל טענה בו מגובה בקובץ ב-`_contract_out/` (s3_*, s4_*, s5_*, s6_*)
- [ ] שלוש שאלות הקבלה עברו, כולל שאלת ה-mermaid/תמונה
- [ ] `reference` מתועד במלואו עם דוגמה אמיתית שבה עוגן inline שרד ב-content
