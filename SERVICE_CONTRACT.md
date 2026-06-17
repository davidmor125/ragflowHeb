# RAGFLOW Service Contract — חוזה שירות גנרי ללקוחות-פרויקטים

מסמך זה מתעד את היכולות הגנריות של שירות RAGFLOW דרך ה-HTTP API בלבד, עבור כל
פרויקט-לקוח שצורך את השירות. **כל קריאה במסמך אומתה בהרצה חיה** מול השרת
(v0.25.0, Docker), והראיות שמורות כקבצי JSON בתיקיית `_contract_out/`
(שם הקובץ מצוין ליד כל סעיף). המסמך גנרי — מתאים לכל סוגי הקבצים והתכנים.

---

## פרטי חיבור

| פרמטר | ערך |
|---|---|
| Base URL | `http://localhost:9380/api/v1` (LAN: `http://10.100.102.7:9380/api/v1`) |
| Auth | `Authorization: Bearer <API_KEY>` |
| גרסה | RAGFlow v0.25.0 (Docker) |
| Embedding | `bge-m3@Ollama` (רב-לשוני) |
| VISION (img2txt) | `qwen2.5vl:7b@Ollama` — ברירת מחדל ברמת ה-tenant |
| Rerank | `BAAI/bge-reranker-v2-m3@HuggingFace` (שרת TEI) |

הצלחה = `"code": 0` בגוף התשובה. כל ערך אחר — שגיאה, פירוט ב-`"message"`.
**כל הקריאות עם תוכן עברי — דרך python/httpx/requests בלבד עם UTF-8. לא shell-curl** (העברית נשברת).

### הזרימה מקצה לקצה

```
1. POST /datasets                      → יצירת dataset      (פעם אחת לפרויקט)
2. POST /datasets/{id}/documents       → העלאת קבצים        (multipart, כמה file בבקשה)
3. POST /datasets/{id}/chunks          → הפעלת parsing      (אסינכרוני; polling על המסמך)
4. POST /chats                         → יצירת assistant    (פעם אחת)
5. POST /chats/{id}/sessions           → פתיחת שיחה
6. POST /chats/{id}/completions        → שאלות ותשובות עם references
```

---

## סעיף 1 — יצירת Dataset עם צינור העיבוד המלא

`POST /datasets` · הבקשה המלאה שאומתה (ראיה: `s1_create_request.json`, `s1_create_response.json`):

```json
{
  "name": "my_dataset",
  "embedding_model": "bge-m3@Ollama",
  "chunk_method": "naive",
  "parser_config": {
    "chunk_token_num": 512,
    "delimiter": "\\n!?;。;！？",
    "layout_recognize": "DeepDOC",
    "auto_keywords": 3,
    "auto_questions": 2,
    "raptor": {"use_raptor": true},
    "graphrag": {"use_graphrag": false},
    "html4excel": false
  },
  "auto_metadata_config": {
    "enabled": true,
    "fields": [
      {"name": "topic", "type": "string", "description": "נושא המסמך"},
      {"name": "doc_date", "type": "time", "description": "תאריך המסמך"}
    ]
  }
}
```

- **צינור ההעשרה נשלט מ-API**: `auto_keywords` (מס' מילות מפתח לכל chunk),
  `auto_questions` (מס' שאלות לכל chunk), `auto_metadata_config` (חילוץ מטא-דאטה מובנית),
  `raptor` (סיכומים היררכיים), `graphrag`. אומת שה-chunks חוזרים עם
  `important_keywords` ו-`questions` בעברית תקינה (ראיה: `s2_chunks.json`).
- **`chunk_method` מומלץ**: `naive` לכל מסמך טקסטואלי (md/txt/docx/pdf — כולל עברית).
  טבלאות בתוך markdown/docx הופכות ל-chunk נפרד בפורמט HTML (`<table>...`).
- **`chunk_token_num` נאכף גם ב-markdown** (תוקן בצד השירות, ראו "הקשחות שירות"
  בהמשך): סקציית `##` ארוכה מתפצלת לכמה chunks על גבולות שורה. אומת על מסמך
  לקוח אמיתי של 148K תווים / 140 סקציות: ‏147 chunks, המקסימלי 1014 טוקנים
  (תקרה 1024), אפס חריגות (ראיה: `offload_r1_run1_verify.json`).
- **שימור טקסט המקור**: ה-chunking משמר את שורות המקור כלשונן בתוך `content` —
  עוגן inline בעברית כמו `[כותרת-ראשית: מסמך-בדיקה-12345]` שרד אימות מלא וחזר
  כלשונו גם ב-chunks וגם ב-references של תשובות (ראיות: `s2_chunks.json`,
  `s5_completion_response.json`).

---

## סעיף 2 — העלאת קבצים ו-Parsing

- העלאה: `POST /datasets/{id}/documents` — multipart/form-data, שדה `file`
  (אפשר כמה קבצים בבקשה אחת). סוגים שאומתו: md, txt, pdf. נתמכים גם docx/pptx/xlsx/תמונות.
- **הפעלת parsing: `POST /datasets/{id}/chunks` עם `{"document_ids": [...]}` בלבד.**
  הנתיב `/documents/parse` מחזיר 405 בגרסה זו.
- מעקב: `GET /datasets/{id}/documents?id={doc_id}` — שדות `run`
  (`RUNNING`→`DONE`, או `FAIL`), `progress` (0–1), `progress_msg`, `chunk_count`,
  `process_duration` (שניות, מדווח ע"י השרת).
- שליפת chunks: `GET /datasets/{id}/documents/{doc_id}/chunks?page=1&page_size=200`.

---

## סעיף 3 — VISION: תמונות בתוך מסמכים

**מה מחובר ואיך זה עובד**: מודל ה-img2txt נקבע ברמת ה-tenant (במסך
Model Providers ב-UI; נשמר ב-`tenant.img2txt_id`). כאשר הוא מוגדר, ה-parsing
של PDF/DOCX מזהה אזורי תמונה (DeepDOC layout), שולח אותם למודל הראייה, ומוסיף
**chunk תיאור נפרד** עם `image_id` (התמונה החתוכה נשמרת ב-MinIO וזמינה ל-UI).

**אומת חי על PDF עם גרף עמודות** (ראיות: `s3_pdf_chunks.json`, `s3_pdf_doc_final.json`):

```
Type: bar chart
Title: QUARTERLY SALES CHART
Data: Q1 = 120 units, Q2 = 200 units, Q3 = 90 units, Q4 = 260 units. Peak quarter: Q4 = 260 units.
```

ה-chunk הזה אוחזר ושימש לתשובה נכונה בשאלת קבלה (סעיף 6, q4).

**מלכודות VISION מאומתות (קריטי)**:

1. **Markdown עם תמונת data-URI (base64 מוטמע) — התמונה מדולגת בשקט**, וטקסט
   ה-base64 הגולמי נשאר בתוך ה-chunk (מזהם אחזור ותוקע rerank). אל תטמיעו
   base64 ב-md.
2. **Markdown עם תמונת URL (http) — ה-parse קורס** בשגיאת
   `sequence item 0: expected str instance, list found` (באג בנתיב ההעשרה
   החזותית של markdown בגרסה זו; ראיה: `s3_doc_final.json` — `run=FAIL`).
3. **מסקנה גנרית: מסמכים עם תמונות — להעלות כ-PDF (או DOCX), לא כ-markdown.**
   נתיב ה-PDF אומת ועובד מצוין.
4. **תיאורי התמונות נוצרים באנגלית** גם כשהמסמך בעברית. לכן לשאלות בשפה אחרת
   חובה `cross_languages` (ראו סעיף 5) — בלעדיו ה-chunk לא יאוחזר כלל לשאלה בעברית
   (אומת: ראיות `s4_crosslang_hebrew.json` מול `s4_crosslang_enabled.json`).
5. PDF עם טקסט דו-כיווני: עוגן inline מעורב (`12345-PDF` בתוך עברית) עלול לחזור
   בהיפוך סדר רכיבים (`PDF-12345`). עוגנים חד-כיווניים (כמו `ZX9871` או עברית
   בלבד) שורדים כלשונם. ב-markdown אין את הבעיה — הכול חוזר כלשונו.

---

## סעיף 4 — Rerank

| היבט | ערך מאומת |
|---|---|
| מזהה | `rerank_id: "BAAI/bge-reranker-v2-m3@HuggingFace"` (פורמט: `שם@ספק`) |
| איפה נקבע | ברמת ה-chat assistant (שדה `rerank_id`) **או** פר-קריאה ב-`POST /retrieval` (פרמטר `rerank_id`). אין rerank ברמת dataset |
| זמן בלי rerank | ‎0.6s לקריאת retrieval (ראיה: `s4_rerank_summary.json`) |
| זמן עם rerank (TEI על CPU) | קריאה ראשונה ~22s, אחר כך 3–4s |
| שיפור דיוק | על מאגר הבדיקה לא שינה את הסדר (top-1 זהה) |

**המלצה גנרית**: בפריסת CPU — **לא להפעיל כברירת מחדל** (פי 5–30 בזמן תשובה,
ללא שיפור מובהק כשהמאגר קטן/מובחן). להפעיל נקודתית כשיש הרבה מועמדים דומים
(מאות chunks קרובים) או על GPU.

**מלכודת מאומתת**: הקריאה ל-TEI נשלחת **בלי timeout** ב-batches של 8; chunk
ארוך חריג (כמו base64 שדלף לתוכן) תוקע את כל הקריאה לדקות. לשמור על תוכן chunks נקי.

---

## סעיף 5 — Chat Assistants וייצור תשובות

### ⚠️ המלכודת המרכזית של הגרסה: שני פורמטים ל-prompt/llm

ה-shape המתועד בדוקומנטציה הרשמית (`"llm": {...}, "prompt": {...}`) **מתקבל עם
code=0 אבל נבלע בשקט** — נשמרות ברירות המחדל (מודל ברירת המחדל של ה-tenant,
prompt אנגלי גנרי, top_n=6, similarity_threshold=0.1). אומת גם ב-POST וגם ב-PUT
(ראיות: `s5_chat_create_request.json` מול `s5_chat_create_response.json`,
`s5_chat_update_request.json`).

**הפורמט שעובד (db-style, אומת ב-POST וב-PUT)** — ראיות:
`s5_chat_create_dbstyle_response.json`, `s5_chat_after_update.json`:

```json
POST /chats
{
  "name": "my_assistant",
  "dataset_ids": ["<dataset_id>"],
  "llm_id": "gpt-oss:20b@Ollama",
  "llm_setting": {"temperature": 0.1},
  "similarity_threshold": 0.1,
  "top_n": 8,
  "rerank_id": "",
  "prompt_config": {
    "system": "אתה עוזר ידע מדויק. ענה בעברית בלבד, אך ורק על סמך המידע במאגר הידע שלהלן:\n{knowledge}\nאם התשובה אינה נמצאת במאגר — אמור במפורש שאינך יודע. אל תמציא מידע.",
    "parameters": [{"key": "knowledge", "optional": false}],
    "empty_response": "",
    "prologue": "שלום!",
    "quote": true,
    "refine_multiturn": false,
    "tts": false,
    "keyword": true,
    "cross_languages": ["Hebrew", "English"]
  }
}
```

- **`{knowledge}` חובה בתוך `prompt_config.system`** — לשם מוזרק תוכן ה-chunks
  שאוחזרו. בלעדיו המודל לא רואה את המאגר. (יצירה בלי `{knowledge}` לא נחסמת —
  `code=0` — אבל האסיסטנט יענה בלי ידע; ראיה: `s5_chat_create_no_knowledge.json`.)
- אימות חי שה-prompt העברי אכן הוחל: שדה `prompt` בתשובת completion מציג את
  ה-system prompt בפועל (ראיה: `s5_completion_after_update.json`).

### שני המתגים שהופכים אחזור רב-לשוני לאמין (אומתו בסעיף 6)

| מתג | מה עושה | עלות | מתי |
|---|---|---|---|
| `prompt_config.keyword: true` | חילוץ מילות מפתח מהשאלה והוספתן לשאילתה (קריאת LLM נוספת) | ~1–3s לשאלה | תמיד מומלץ; פותר פספוסי ניסוח/פיסוק-מקפים |
| `prompt_config.cross_languages: ["Hebrew","English"]` | תרגום השאילתה לשפות הרשומות לפני אחזור (קריאת LLM נוספת) | ~2–4s לשאלה | חובה כשבמאגר יש תוכן בכמה שפות (כולל תיאורי VISION באנגלית) |

**חשוב**: התאמת מילים טקסטואלית ב-ES היא תנאי סף למועמדות chunk — דמיון וקטורי
לבדו לא מכניס chunk לתוצאות בגרסה זו. לכן שאלה בעברית לעולם לא תאחזר chunk
שכולו אנגלית בלי `cross_languages` (אומת: `s4_crosslang_*.json`).
ב-`POST /retrieval` הפרמטרים המקבילים: `keyword: true`, `cross_languages: [...]`.

### Sessions ו-Completions

```json
POST /chats/{chat_id}/sessions          {"name": "session_1"}     → data.id
POST /chats/{chat_id}/completions       {"question": "...", "stream": false, "session_id": "<id>"}
```

**stream=false** (ראיה: `s5_completion_response.json`) — `data` מכיל:
`answer` (כולל סימוני ציטוט `[ID:n]`), `reference`, `prompt` (ה-prompt בפועל +
פירוט זמנים), `id`, `session_id`, `created_at`, `audio_binary`.

**stream=true** (ראיה: `s5_completion_stream_sample.json`) — SSE
(`text/event-stream`), כל אירוע `data:{"code":0,"data":{...}}`:
- `answer` **מצטבר** (לא דלתא) בכל אירוע.
- אירוע ראשון עשוי לכלול `start_to_think: true` (מודלי reasoning); אירוע אחרון
  מסומן `final: true` ומכיל את התשובה המלאה + `reference` מלא + `prompt`.
- סוגר את הזרם אירוע סנטינל: `data:{"code": 0, "data": true}`.
- במודלי reasoning ייתכנו תגי `<think>...</think>` בתוך ה-answer בזרימה — לסנן בצד הלקוח.

### סכמת `reference` — מלאה ומאומתת

```
reference = {
  "total": int,                  // מס' מועמדים
  "chunks": [ ... ],             // ה-chunks שצוטטו (ראו טבלה)
  "doc_aggs": [                  // אגרגציה פר-מסמך
    {"doc_name": str, "doc_id": str, "count": int}
  ]
}
```

שדות כל אובייקט ב-`chunks` (ראיה: `s5_reference_chunk_schema.json` + דוגמה
אמיתית מלאה ב-`s5_completion_response.json`):

| שדה | טיפוס | משמעות |
|---|---|---|
| `id` | str | מזהה ה-chunk באינדקס |
| `content` | str | **תוכן ה-chunk כלשונו** — כולל סימוני inline של הלקוח |
| `document_id` / `document_name` | str | המסמך המקורי |
| `dataset_id` | str | ה-dataset |
| `image_id` | str | לא-ריק כש-chunk הוא תיאור תמונה (לשליפת התמונה ל-UI) |
| `positions` | list | מיקומים במסמך `[page, x0, x1, y0, y1]` |
| `similarity` | float | ציון משוקלל (טקסט+וקטור) |
| `vector_similarity` / `term_similarity` | float | רכיבי הציון |
| `doc_type` | str | `""` רגיל, `"image"` לתמונות |
| `url`, `row_id` | nullable | למקורות חיצוניים/טבלאיים |

- **מיפוי ציטוטים**: סימון `[ID:n]` בתוך `answer` מפנה לאינדקס n ברשימת ה-chunks
  כפי שהוזרקה ל-prompt — זהה לסדר `reference.chunks`.
- **אומת מפורשות**: `content` של chunk מצוטט חוזר **כלשונו** — העוגן
  `[כותרת-ראשית: מסמך-בדיקה-12345]` חזר בשלמותו בתוך `reference.chunks[0].content`,
  והתשובות חוזרות בעברית תקינה (ראיות: `s5_completion_response.json`,
  `s6_acceptance_summary.json`).

### פרמטרי איכות — ערכים מומלצים גנרית

| פרמטר | ברירת מחדל | מומלץ | הערה |
|---|---|---|---|
| `similarity_threshold` | 0.1 | **0.1** | 0.2 ומעלה מפיל תשובות-גבול אמיתיות (אומת בסעיף 6) |
| `top_n` | 6 | **8** | כמה chunks נכנסים ל-prompt |
| `top_k` | 1024 | 1024 | מועמדי וקטור לפני סינון |
| `vector_similarity_weight` | 0.3 | 0.3 | משקל הווקטור בציון המשוקלל |
| `llm_setting.temperature` | — | **0.1** | תשובות עובדתיות |
| `rerank_id` | `""` | `""` (כבוי) | ראו סעיף 4 |

נקבעים ברמת ה-assistant (db-style) או נדרסים פר-קריאה ב-`POST /retrieval`.

---

## סעיף 6 — בדיקת קבלה (הורצה ותועדה) + זמנים

מסמך בדיקה גנרי בעברית: ~20 פסקאות + טבלה (עם קוד `ZX9871`) + תרשים mermaid
(עם `MERMAIDKEY42`) ב-md, ותרשים מכירות כתמונה ב-PDF נלווה. אסיסטנט בתצורה
המומלצת לעיל (gpt-oss:20b@Ollama מקומי). **תוצאה: 4/4 עברו** (ראיה:
`s6_acceptance_summary.json`, תשובות מלאות ב-`s6_q*_response.json`):

| שאלה | סוג | תשובה | זמן | reference מכיל את הסמן |
|---|---|---|---|---|
| מודל ההטמעה ומאפיינו | פסקה | ✅ "bge-m3... רב-לשוני" | 26s | ✅ (כולל העוגן השלם) |
| הקוד הסודי בטבלה | טבלה | ✅ "ZX9871" | 10s | ✅ |
| המפתח בתרשים הזרימה | mermaid | ✅ "MERMAIDKEY42" | 9s | ✅ |
| רבעון השיא בתרשים | **תמונה (VISION)** | ✅ "Q4, 260 יחידות" | 13s | ✅ |

### זמני עיבוד שנמדדו (ל-UX של "בונה אינדקס")

ראיה: `s6_timing_summary.json`. חומרה: CPU בלבד (Docker), embedding מקומי ב-Ollama.

| תרחיש | זמן | פירוט |
|---|---|---|
| md ‎200KB (ללא העשרה) | **56s** (60s כולל polling) | 394 chunks ⇒ ~7 chunks/שנייה |
| md ‎148KB **עם העשרה מלאה** (keywords+questions) | **436s** ראשון, **74s** ריצה חוזרת | 147 chunks; הריצה החוזרת מהירה בזכות LLM cache של ההעשרה (ראיה: `offload_r1_run*_doc_final.json`) |
| PDF עם תמונה + VISION + העשרה | **20s** | כולל תיאור תמונה ב-qwen2.5vl |
| batch מעורב: md+pdf+txt יחד | **15s** | מעובדים במקביל ע"י ה-executors |
| md קטן (3KB) עם העשרה מלאה | **19–20s** | ה-LLM הוא צוואר הבקבוק, לא הגודל |
| תוספת העשרה | ~1.0s/chunk מילות מפתח + ~1.8s/chunk שאלות | תלוי-LLM; מצטבר על מאות chunks |

**כלל אצבע ללקוחות**: ללא העשרה — שניות עד דקה גם לקבצים גדולים; עם
`auto_keywords`/`auto_questions` — להכפיל לפי ~3s לכל chunk (כ-100 chunks ל-50KB
עברית). קבצים מרובים כדאי לשלוח ב-parse אחד — הם רצים במקביל.

---

## הקשחות שירות (client-offload, 2026-06-12)

אחרי צריכה אמיתית ראשונה של החוזה ע"י פרויקט-לקוח הוחלו שלושה תיקונים **בצד
השירות** (בקונטיינר הרץ ובעץ המקור; בבנייה מחדש של הקונטיינר יש להחיל מחדש
מהעץ). העיקרון: הלקוח שולח קבצים ושואל שאלות — בלי שום עקיפה בצד הלקוח.

| תיקון | קובץ | מה השתנה |
|---|---|---|
| אכיפת `chunk_token_num` ב-markdown | `rag/app/naive.py` | סקציה (בלוק `##` או טקסט בין delimiters) שגדולה מהתקרה מפוצלת על גבולות שורה לפני המיזוג; קודם נוצרו chunks של עד 65K תווים |
| מקביליות העשרה | `rag/graphrag/utils.py` | ברירת המחדל של `MAX_CONCURRENT_CHATS` ‏10→3 (נשלט env). קודם הצפת ה-LLM המקומי החזירה "too many concurrent requests" והפילה את כל המסמך |
| חסינות embedding | `rag/llm/embedding_model.py` (`OllamaEmbed.encode`) | ‏4 ניסיונות עם backoff מעריכי לכל טקסט + הודעת השגיאה האמיתית של הספק (קודם: כשל מיידי עם הודעה מטעה על "context length") |

**אימות קבלה** (ראיות: `offload_r1_*.json`): מסמך לקוח אמיתי — ‏148K תווים
עברית, 140 סקציות, 138 עוגני `[S#:]` — עם הקונפיג המלא כולל העשרה:
- ‏run=DONE פעמיים ברצף (מחיקה והעלאה מחדש בין הריצות), בלי קריסות.
- ‏147 chunks; טוקנים: median ‏855, מקסימום ‏1014 ≤ תקרת 1024; אפס חריגות.
- ‏138/138 עוגני inline שרדו כלשונם בשתי הריצות.
- העשרה מלאה על כל ה-chunks ‏(147/147 keywords ו-questions).

## הערות ומלכודות מאומתות — סיכום

1. **parse מפעילים רק דרך `POST /datasets/{id}/chunks`**; `/documents/parse` → 405.
2. אין `type=empty` ביצירת dataset בגרסה זו.
3. עברית רק דרך python/httpx — shell-curl שובר UTF-8.
4. **`POST/PUT /chats` בולע בשקט את `llm`/`prompt` המתועדים** — להשתמש ב-db-style:
   `llm_id`, `llm_setting`, `prompt_config`, `similarity_threshold`, `top_n`, `rerank_id`.
5. **`{knowledge}` חובה ב-`prompt_config.system`** — והיעדרו לא מייצר שגיאה.
6. **התאמת מילים היא תנאי סף לאחזור** — chunk בשפה שונה מהשאלה לא יוחזר בלי
   `cross_languages`; `keyword: true` מומלץ תמיד.
7. **תמונות במסמכים — דרך PDF/DOCX בלבד**: ב-markdown, data-URI מדולג בשקט
   (וה-base64 מזהם את ה-chunk) ותמונת http מפילה את ה-parse (באג גרסה).
8. תיאורי VISION נוצרים באנגלית — עוד סיבה ל-`cross_languages`.
9. ב-PDF, עוגן inline מעורב-כיוונים (עברית+לטינית+ספרות) עלול לחזור בסדר רכיבים
   הפוך; עוגנים חד-כיווניים שורדים כלשונם. ב-md הכול שורד כלשונו.
10. rerank על CPU איטי (3–22s) וללא timeout מובנה — לא כברירת מחדל.
11. מודלי reasoning בזרימה מדליפים `<think>` — לסנן בצד הלקוח; ב-stream=false
    התשובה נקייה.
12. `process_duration` על המסמך נותן את זמן העיבוד האמיתי בצד השרת — להשתמש בו
    ולא בזמן ה-polling.
13. **קריאת chunks מיד אחרי `run=DONE` עלולה להחזיר רשימה חלקית** (רענון אינדקס
    near-real-time): נצפו 81/147 מיד אחרי DONE ו-147/147 שניות אחר כך. להשוות את
    מספר התוצאות ל-`chunk_count` של המסמך ולנסות שוב אם חסר
    (ראיה: `offload_r1_run2_verify_late.json`).
14. בפריסות RAGFlow לא-מתוקנות (image v0.25.0 מקורי): ה-chunker של markdown
    מתעלם מ-`chunk_token_num` (פיצול לפי כותרות בלבד) — בפריסה הזו זה תוקן
    (ראו "הקשחות שירות").

## מפת ראיות (`_contract_out/`)

| סעיף | קבצים |
|---|---|
| 1 | `s1_create_request.json`, `s1_create_response.json`, `s1_readback.json` |
| 2 | `s2_upload_response.json`, `s2_doc_final.json`, `s2_chunks.json` |
| 3 | `s3_doc_final.json` (כשל md), `s3_pdf_chunks.json`, `s3_pdf_doc_final.json` |
| 4 | `s4_rerank_summary.json`, `s4_retrieval_*.json`, `s4_crosslang_*.json` |
| 5 | `s5_chat_create_*.json`, `s5_chat_after_update.json`, `s5_session_response.json`, `s5_completion_response.json`, `s5_completion_stream_sample.json`, `s5_reference_chunk_schema.json` |
| 6 | `s6_acceptance_summary.json`, `s6_q*_response.json`, `s6_timing_summary.json`, `s6_chat_final_config.json`, `s6_retrieval_keyword_true.json` |
| הקשחות שירות | `offload_r1_dataset.json`, `offload_r1_run1_doc_final.json`, `offload_r1_run1_verify.json`, `offload_r1_run2_doc_final.json`, `offload_r1_run2_verify.json`, `offload_r1_run2_verify_late.json` |
