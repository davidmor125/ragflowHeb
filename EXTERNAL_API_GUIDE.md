# פנייה ל-RAGFlow מפרויקט חיצוני — מדריך אינטגרציה

מדריך מעשי לחיבור פרויקט/אתר חיצוני אל שירות ה-RAGFlow, כדי **לשאול שאלה ולקבל
תשובה** מתוך מאגר הידע. כל הערכים והקריאות במסמך **אומתו חי** מול השרת הרץ
(v0.25.0, Docker) ב-2026-06-22.

---

> **הפרויקט הצורך רץ על אותה תחנה (local).** לכן משתמשים ב-`localhost` — אין צורך
> ב-IP חיצוני או בפתיחת חומת אש.

## 1. פרטי חיבור

| פרמטר | ערך |
|---|---|
| Base URL | `http://localhost:9380/api/v1` |
| אימות | כותרת `Authorization: Bearer <API_KEY>` |
| הצלחה | `code: 0` בגוף ה-JSON. כל ערך אחר = שגיאה, פירוט ב-`message` |
| Content-Type | `application/json; charset=utf-8` |

**API key מאומת (של המאגר הזה):**
```
ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI
```
> זהו סוד — לא להטמיע בקוד צד-לקוח (דפדפן). מאחר שהפרויקט רץ מקומית, להחזיק אותו
> בצד-שרת/קונפיג של הפרויקט. אפשר להנפיק מפתח נוסף ב-UI: ⚙️ → **API** → *Create API key*.

---

## 2. המשאבים המוכנים (כבר נוצרו ואומתו)

| משאב | מזהה | פרטים |
|---|---|---|
| **Dataset** | `d8658da46e1511f180f0f150c7111c57` | שם `TestVoicecCedit` · מסמך אחד (`אשראי מובטח 44.doc`) · 668 chunks · embedding `qwen3-embedding:4b@Ollama` |
| **Chat Assistant** | `3d42d9026e1b11f180f0f150c7111c57` | שם `external_api_assistant` · LLM `gpt-oss:20b@Ollama` · עברית · `keyword`+`cross_languages` פעילים |

> ה-chat assistant כבר מחובר ל-dataset ומוגדר נכון (כולל `{knowledge}` ב-prompt,
> סף דמיון 0.1, top_n=8). **הפרויקט החיצוני צריך רק לקרוא ל-completions** — אין צורך
> ליצור שום דבר.

---

## 3. הזרימה — שתי קריאות בלבד

```
1. POST /chats/{chat_id}/sessions      → פותח שיחה, מחזיר session_id   (פעם אחת לשיחה)
2. POST /chats/{chat_id}/completions   → שולח שאלה, מקבל answer + references
```

ניתן לשמור את ה-`session_id` ולשלוח אליו כמה שאלות (שיחה רב-תורית), או לפתוח
session חדש לכל שאלה.

### קריאה 1 — פתיחת session
```
POST http://localhost:9380/api/v1/chats/3d42d9026e1b11f180f0f150c7111c57/sessions
Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI
Content-Type: application/json; charset=utf-8

{ "name": "web_user_1" }
```
תשובה: `data.id` = ה-`session_id`.

### קריאה 2 — שאלה ותשובה
```
POST http://localhost:9380/api/v1/chats/3d42d9026e1b11f180f0f150c7111c57/completions
Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI
Content-Type: application/json; charset=utf-8

{ "question": "על מה המסמך הזה?", "stream": false, "session_id": "<session_id>" }
```

---

## 4. מבנה התשובה (`stream: false`)

```jsonc
{
  "code": 0,
  "data": {
    "answer": "טקסט התשובה בעברית, עם סימוני ציטוט כמו [ID:0][ID:1] ...",
    "reference": {
      "total": 8,
      "chunks": [
        {
          "id": "...",
          "content": "תוכן ה-chunk כלשונו",
          "document_name": "אשראי מובטח 44.doc",
          "document_id": "...",
          "dataset_id": "d8658da4...",
          "similarity": 0.78,
          "image_id": "",          // לא ריק כש-chunk הוא תיאור תמונה
          "positions": [[page, x0, x1, y0, y1]]
        }
      ],
      "doc_aggs": [ { "doc_name": "...", "doc_id": "...", "count": 3 } ]
    },
    "id": "...", "session_id": "...", "created_at": 169...
  }
}
```

- **`data.answer`** — התשובה להצגה למשתמש. סימוני `[ID:n]` מפנים ל-`reference.chunks[n]`.
- **`data.reference.chunks`** — המקורות שעליהם התבססה התשובה (להצגת "מקורות"/ציטוטים).
- אם תרצו להסתיר את סימוני `[ID:n]` מהמשתמש — להסיר בצד-לקוח עם regex `\[ID:\d+\]`.

---

## 5. דוגמת קוד מלאה — Node.js (צד-שרת)

```javascript
const BASE    = "http://localhost:9380/api/v1";
const API_KEY = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI";
const CHAT_ID = "3d42d9026e1b11f180f0f150c7111c57";
const H = {
  "Authorization": `Bearer ${API_KEY}`,
  "Content-Type": "application/json; charset=utf-8",
};

async function ask(question) {
  // 1. פתיחת session
  const s = await fetch(`${BASE}/chats/${CHAT_ID}/sessions`, {
    method: "POST", headers: H, body: JSON.stringify({ name: "web_user" }),
  }).then(r => r.json());
  if (s.code !== 0) throw new Error("session failed: " + s.message);
  const sessionId = s.data.id;

  // 2. שאלה
  const c = await fetch(`${BASE}/chats/${CHAT_ID}/completions`, {
    method: "POST", headers: H,
    body: JSON.stringify({ question, stream: false, session_id: sessionId }),
  }).then(r => r.json());
  if (c.code !== 0) throw new Error("completion failed: " + c.message);

  return {
    answer:  c.data.answer.replace(/\[ID:\d+\]/g, "").trim(),
    sources: (c.data.reference?.chunks ?? []).map(ch => ({
      text: ch.content, doc: ch.document_name, score: ch.similarity,
    })),
  };
}

// שימוש:
ask("על מה המסמך הזה? תן סיכום קצר.")
  .then(r => { console.log(r.answer); console.log(r.sources.length, "מקורות"); })
  .catch(console.error);
```

## 5א. דוגמה — Python (httpx)

```python
import httpx

BASE    = "http://localhost:9380/api/v1"
API_KEY = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
CHAT_ID = "3d42d9026e1b11f180f0f150c7111c57"
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json; charset=utf-8"}

def ask(question: str):
    with httpx.Client(timeout=120) as cli:
        s = cli.post(f"{BASE}/chats/{CHAT_ID}/sessions", headers=H, json={"name": "web_user"}).json()
        assert s["code"] == 0, s.get("message")
        sid = s["data"]["id"]

        c = cli.post(f"{BASE}/chats/{CHAT_ID}/completions", headers=H,
                     json={"question": question, "stream": False, "session_id": sid}).json()
        assert c["code"] == 0, c.get("message")
        return c["data"]["answer"], c["data"].get("reference", {}).get("chunks", [])

answer, sources = ask("על מה המסמך הזה?")
print(answer)
```

---

## 6. תשובה בזרימה (`stream: true`) — אופציונלי

לשליחת תשובה מילה-אחר-מילה (UX של "מקליד"), שלחו `"stream": true`. התגובה היא
**SSE** (`text/event-stream`), כל אירוע בפורמט `data:{"code":0,"data":{...}}`:
- `data.answer` **מצטבר** בכל אירוע (לא דלתא) — להחליף את הטקסט, לא להוסיף.
- האירוע האחרון מסומן `"final": true` ומכיל `reference` מלא.
- הזרם נסגר באירוע סנטינל: `data:{"code": 0, "data": true}`.
- מודלי reasoning עלולים לשלב תגי `<think>...</think>` — לסנן בצד-לקוח.

---

## 7. חלופה — אחזור chunks בלבד (בלי LLM)

אם הפרויקט החיצוני רוצה רק את הקטעים הרלוונטיים (לבנות תשובה בעצמו / חיפוש):

```
POST /api/v1/retrieval
{
  "question": "השאלה",
  "dataset_ids": ["d8658da46e1511f180f0f150c7111c57"],
  "keyword": true,
  "cross_languages": ["Hebrew", "English"],
  "top_k": 1024,
  "similarity_threshold": 0.1
}
```
מחזיר `data.chunks` עם `content`, `similarity`, `document_name`. מהיר יותר (אין שלב
LLM) — אבל מחזיר קטעים, לא תשובה מנוסחת.

---

## 8. מלכודות מאומתות (לקרוא לפני אינטגרציה)

1. **תוכן עברי — דרך httpx/fetch/axios עם UTF-8 בלבד.** `curl` בשורת פקודה שובר
   את הקידוד. בקוד (Node/Python) הכל תקין.
2. **לא להטמיע את ה-API key בקוד צד-לקוח (דפדפן).** הקריאות צריכות לצאת מצד-שרת.
3. **התשובה תמיד עם `code`** — לבדוק `code === 0` לפני קריאת `data`. שגיאה מפורטת
   ב-`message`.
4. **שאלה ראשונה אחרי שהשרת היה במנוחה עשויה לקחת 20–30 שניות** (טעינת המודל
   המקומי ב-Ollama). אחר כך 5–15 שניות. להגדיר timeout נדיב (≥120s) ב-completions.
5. **תיאורי תמונות במאגר נוצרים באנגלית** — לכן ה-assistant מוגדר עם
   `cross_languages: ["Hebrew","English"]` כדי ששאלה בעברית תאחזר גם אותם.
   (כבר מוגדר — לא צריך לעשות כלום.)

---

## 9. אם צריך assistant נוסף / על dataset אחר

ליצירת chat assistant חדש (db-style — **הפורמט המתועד הרשמי נבלע בשקט**, להשתמש בזה):
```
POST /api/v1/chats
{
  "name": "my_assistant",
  "dataset_ids": ["<dataset_id>"],
  "llm_id": "gpt-oss:20b@Ollama",
  "llm_setting": { "temperature": 0.1 },
  "similarity_threshold": 0.1,
  "top_n": 8,
  "prompt_config": {
    "system": "אתה עוזר ידע מדויק. ענה בעברית על סמך המידע:\n{knowledge}\nאם אינך יודע — אמור זאת.",
    "parameters": [{ "key": "knowledge", "optional": false }],
    "keyword": true,
    "cross_languages": ["Hebrew", "English"]
  }
}
```
- **`{knowledge}` חייב להופיע ב-`prompt_config.system`** — לשם מוזרק תוכן המאגר.
  בלעדיו המודל לא רואה את ה-chunks (וה-API לא יחזיר שגיאה על כך).
