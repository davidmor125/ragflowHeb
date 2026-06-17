# RAGFLOW — חוזה שירות גנרי ללקוחות-פרויקטים (API Service Contract)

מסמך זה מיועד ל-Claude שעובד על פרויקט RAGFLOW. **RAGFLOW הוא שירות RAG גנרי**
שמשרת פרויקטים רבים. שום דבר במסמך הזה לא דורש קוד או קונפיג ספציפי לפרויקט
כלשהו — המטרה היא **לתעד ולאמת את היכולות הגנריות** של השירות דרך ה-HTTP API,
כך שכל פרויקט-לקוח (QUESTIONER הוא רק אחד מהם) יוכל לצרוך אותן בעצמו, עם
הפרמטרים שלו.

## העיקרון

```
לקוח (כל פרויקט):                   RAGFLOW (שירות גנרי):
  שולח קבצים פעם אחת        →        dataset: chunking, embedding,
  (מסמכים, PDF, תמונות)              העשרה (Summary/Keyword/Question/
                                      Metadata), VISION, אינדוקס
  שואל שאלות               →        chat completions: retrieval + rerank
  (עם prompt משלו שהועבר              + ניסוח תשובה + references
   ביצירת ה-assistant)
```

כל מה שייחודי ללקוח — מבנה הקבצים, עוגני ציטוט בתוך הטקסט, ה-system prompt,
בחירת המודל — עובר **כנתונים/פרמטרים ב-API**, לא כהתאמה בצד השירות.

## מה לתעד ולאמת (העבודה)

לכל סעיף: לאמת בקריאה חיה מול השרת הרץ (v0.25.0, port 9380) ולתעד request +
response מדויקים, בסגנון המסמך המאומת הקודם שנכתב כאן ("RAGFlow API — הנחיה
ל-Claude") — הוא היה מצוין.

### 1. יצירת dataset עם ה-pipeline המלא — דרך API בלבד
- ה-JSON המדויק של `POST /api/v1/datasets` שמפעיל את יכולות העיבוד המלאות:
  `chunk_method`, `parser_config`, והפעלת צינור ההעשרה החדש
  (Summary + Keyword + Question + Metadata) — אם הוא נשלט מ-API; אם חלקו נשלט
  רק מ-UI, לתעד בדיוק מה ואיך, ומה ברירת המחדל.
- אילו ערכי `chunk_method` מתאימים לאילו סוגי תוכן (markdown עם טבלאות, PDF,
  תמונות), ומה ההמלצה הגנרית למסמכים טקסטואליים בעברית.
- לוודא עיקרון גנרי: ה-chunking משמר את טקסט המקור כלשונו בתוך `content`
  של ה-chunks (לא מסנן/משכתב שורות) — לקוחות מסתמכים על סימונים inline
  שלהם בתוך הטקסט.

### 2. העלאת קבצים מרובים ו-parsing
- `POST /datasets/{id}/documents` — כמה קבצים בבקשה אחת (multipart), סוגי
  קבצים נתמכים (md, txt, pdf, docx, png/jpg).
- הפעלת parsing: `POST /datasets/{id}/chunks {document_ids}` (אומת: זו הדרך;
  `/documents/parse` מחזיר 405).
- מעקב: `GET /datasets/{id}/documents` — שדות run/progress/chunk_count.
- **מדידת זמנים** (חשוב לכל לקוח, ל-UX של "בונה אינדקס"): קובץ md של ~200KB;
  PDF עם תמונות; dataset של 3-4 קבצים מעורבים.

### 3. VISION — תמונות בתוך מסמכים
- איזה מודל img2txt מחובר לשירות (זמינים מקומית: qwen2.5vl:7b, minicpm-v,
  gemma4:26b/e4b) ואיך לקוח מפעיל אותו לרמת dataset דרך ה-API.
- אם לא מחובר — לחבר אחד (גנרית, ברמת השירות) ולהדגים: PDF/md עם תמונה →
  ה-chunks כוללים תיאור טקסטואלי של התמונה.

### 4. Rerank
- קיים מקומית `qllama/bge-reranker-v2-m3`. לתעד: מה ה-`rerank_id`, איפה הוא
  נקבע (dataset / chat assistant / פרמטר retrieval), והאם מומלץ כברירת מחדל
  (עלות זמן מול שיפור דיוק — למדוד על דוגמה).

### 5. Chat assistants — ייצור תשובות
- `POST /api/v1/chats` — יצירת assistant גנרי: `dataset_ids`, בחירת מודל
  (מה זמין: gpt-oss:20b, gemma4:26b...), ו-**system prompt שהלקוח מספק**
  (כולל משתני התבנית כמו {knowledge} אם נדרשים — לתעד את הפורמט המחייב).
- פרמטרי איכות: similarity_threshold, top_n, temperature — ערכים מומלצים גנרית.
- `POST /chats/{id}/sessions` + `POST /chats/{id}/completions` — request/response
  מלאים ב-stream=false וב-stream=true, ובמיוחד **הסכמה המלאה של `reference`**
  (ה-chunks שצוטטו: content, document_id, positions...) — זה מה שלקוחות
  ממפים חזרה ל-UI שלהם.
- עברית: לוודא ולתעד שהתשובות חוזרות בעברית תקינה כשה-prompt בעברית.

### 6. בדיקת קבלה גנרית (להריץ ולתעד תוצאות)
מסמך בדיקה עברי גנרי (לא של פרויקט מסוים): ~20 פסקאות, טבלה, בלוק קוד/תרשים
(mermaid), ותמונה. דרך ה-API בלבד:
1. צור dataset עם הקונפיג מסעיף 1 → העלה את הקובץ → parse → המתן ל-run="3".
2. צור chat assistant עם prompt עברי בסיסי.
3. שאל 3 שאלות: עובדה מפסקה, עובדה מטבלה, ושאלה שעונים עליה רק מבלוק
   התרשים/התמונה (מבחן ההעשרה/VISION).
4. אמת שה-references מחזירים את ה-chunks הנכונים ושסימוני טקסט inline
   (למשל שורת כותרת בסוגריים מרובעים) שרדו בתוך content.

## Deliverable

מסמך markdown אחד: **"RAGFLOW Service Contract"** — חוזה גנרי שכל פרויקט-לקוח
יכול לעבוד מולו: כל ה-JSON-ים המאומתים, סכמת references, rerank, זמני parse
שנמדדו, ורשימת "הערות ומלכודות מאומתות" (כמו במסמך הקודם).

## פרטי גישה (לאימותים)

- Base: `http://localhost:9380/api/v1` | LAN: `http://10.100.102.7:9380/api/v1`
- Auth: Bearer key (קיים אצל דוד; נמצא גם ב-QUESTIONER backend/.env כ-RAGFLOW_API_KEY)
- גרסה: RAGFlow v0.25.0 (docker) | Embedding: `bge-m3@Ollama`
- מלכודות שכבר אומתו ע"י לקוח: אין `type=empty` בגרסה זו; parse רק דרך
  `POST /datasets/{id}/chunks`; עברית דרך shell-curl נשברת — python/httpx בלבד.
