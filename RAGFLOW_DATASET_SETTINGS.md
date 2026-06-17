# RAGFlow — הגדרות Dataset מומלצות (עברית / נהלים בנקאיים)

מדריך שליפה: כל ההגדרות שהגדרנו ל-dataset איכותי בעברית, מבוססות על בדיקות
חיות. בכל פעם שיוצרים dataset חדש — להעתיק מכאן.

עדכון אחרון: 2026-06-14 · נבדק על קורפוס נהלים בנקאיים עברית (HOZRIM).

---

## TL;DR — הקונפיג המלא בשליפה

### ברמת ה-Dataset (מסך Configuration / API `parser_config`)

| הגדרה | ערך מומלץ | שדה API | שם בממשק |
|---|---|---|---|
| **Embedding model** | `qwen3-embedding:4b@Ollama` | `embedding_model` | Embedding model |
| **Chunk size** | **512** | `parser_config.chunk_token_num` | Recommended chunk size |
| **Child chunk (parent-child)** | מופעל | `parser_config.parent_child.use_parent_child=true` | Child chunk are used for retrieval |
| **Children delimiter** | `\n` | `parser_config.children_delimiter` | (Delimiter תחת Child chunk) |
| **Delimiter** | `\n` | `parser_config.delimiter` | Delimiter for text |
| **Auto-keyword (metadata עשיר)** | **3** | `parser_config.auto_keywords` | Auto-keyword |
| **Auto-question (Smart Question)** | **2** | `parser_config.auto_questions` | Auto-question |
| **Enrichment LLM** | מקומי בלבד* | `parser_config.llm_id` | Indexing model |
| **GraphRAG** | **כבוי** (כבד) | `parser_config.graphrag.use_graphrag=false` | — |
| **RAPTOR** | **כבוי** | `parser_config.raptor.use_raptor=false` | — |
| **PDF parser** | `DeepDOC` | `parser_config.layout_recognize` | PDF parser |

### ברמת ה-Chat Assistant (מסך Chat → App Settings)

| הגדרה | ערך מומלץ | שדה API | שם בממשק |
|---|---|---|---|
| **Answer LLM** | `gemma4:31b-cloud@Ollama`** | `llm_id` | Model |
| **Reranker** | `Qwen3-Reranker-4B@HuggingFace` | `rerank_id` | Rerank model |
| **Top N** | **8** | `top_n` | Top N |
| **Similarity threshold** | **0.1** | `similarity_threshold` | Similarity threshold |
| **Keyword analysis** | מופעל | `prompt_config.keyword=true` | — |
| **Cross-languages** | `["Hebrew","English"]` | `prompt_config.cross_languages` | — |
| **`{knowledge}` ב-system prompt** | חובה | `prompt_config.system` | System prompt |

> \* **Enrichment LLM (Indexing model)**: ה-Auto-keyword/Auto-question מריצים LLM
> על כל chunk. **חובה מודל מקומי** — מודלי `*-cloud` נחסמים על מכסה שבועית
> ופוסלים את כל הפרסור. בחירה: `gpt-oss:20b@Ollama` (מהיר, נכנס ל-GPU) או
> `gemma4:26b@Ollama`. **לא** `gpt-oss:120b@Ollama` (61GB, גדול מ-VRAM 24GB →
> זוחל על CPU). **לא** שום `*-cloud`.
>
> \** **Answer LLM**: `gemma4:31b-cloud` הכי טוב לעברית — אבל cloud (תלוי מכסה).
> חלופה מקומית: `gpt-oss:20b@Ollama`.

---

## JSON מוכן ל-`POST /api/v1/datasets`

```json
{
  "name": "MY_DATASET_NAME",
  "embedding_model": "qwen3-embedding:4b@Ollama",
  "chunk_method": "naive",
  "parser_config": {
    "chunk_token_num": 512,
    "delimiter": "\n",
    "layout_recognize": "DeepDOC",
    "auto_keywords": 3,
    "auto_questions": 2,
    "llm_id": "gpt-oss:20b@Ollama",
    "raptor": {"use_raptor": false},
    "graphrag": {"use_graphrag": false},
    "parent_child": {"use_parent_child": true, "children_delimiter": "\n"}
  }
}
```

## JSON מוכן ל-`POST /api/v1/chats` (db-style — הפורמט שעובד)

```json
{
  "name": "MY_ASSISTANT",
  "dataset_ids": ["<DATASET_ID>"],
  "llm_id": "gemma4:31b-cloud@Ollama",
  "llm_setting": {"temperature": 0.1},
  "similarity_threshold": 0.1,
  "top_n": 8,
  "rerank_id": "Qwen3-Reranker-4B@HuggingFace",
  "prompt_config": {
    "system": "אתה עוזר שעונה על שאלות... ענה אך ורק על סמך:\n{knowledge}\nאם המידע אינו קיים — אמור 'המידע אינו קיים במאגר'.",
    "parameters": [{"key": "knowledge", "optional": false}],
    "empty_response": "המידע אינו קיים במאגר",
    "quote": true,
    "keyword": true,
    "cross_languages": ["Hebrew", "English"]
  }
}
```

---

## הסבר: למה כל הגדרה (מה היא פותרת)

| הגדרה | הבעיה שהיא פותרת (נמדד) |
|---|---|
| **Qwen embedding (2560 dim, 40K ctx)** | bge-m3 דרך Ollama קורס בעברית מעל ~3000 טוקן (וקטור חתוך). Qwen מטמיע עד 44K טוקן עברית בלי חיתוך |
| **Chunk 512 (לא 256)** | 256 מפצל את ההקשר מהתשובה. אומת: שאלה "מתי תקין?" + תשובה "אינה חייבת דיווח" — ב-512 באותו chunk → המודל ענה נכון; ב-256 נכשל |
| **Child chunk (parent-child)** | בנים קטנים לאחזור מדויק + אב שלם לציטוט. מונע צ'אנקים ענקיים |
| **Auto-keyword** | מטא-דאטה עשיר — מילות מפתח לכל chunk, משפר התאמה טקסטואלית |
| **Auto-question (Smart Question)** | מקשר שאלות אפשריות לכל chunk — עוזר כשהשאלה לא חולקת מילים עם התשובה |
| **Qwen reranker** | ממיין 64 מועמדים, דוחף את הרלוונטי לראש. מהיר על GPU (20 docs / 0.28s) |
| **Top N = 8** | עם reranker, 64 מועמדים נשלחים ל-rerank ו-top_n קובע כמה נכנסים ל-prompt. 8 = איזון הקשר/רעש |
| **keyword + cross_languages** | התאמת מילים היא תנאי סף לאחזור ב-ES; chunk בשפה אחרת לא יוחזר בלי cross_languages |
| **GraphRAG/RAPTOR כבוי** | כבדים מאוד (graphrag הפיל פרסור). לא נדרשים ל-naive chunking |

---

## מלכודות מאומתות — לקרוא לפני יצירת dataset

1. **אי אפשר לשנות Embedding על dataset קיים עם chunks** — שגיאה
   `dimension 2560 != 1024` / `code 102`. ליצור **dataset חדש** עם Qwen מההתחלה,
   או למחוק chunks קודם.
2. **`parser_config.llm_id` חייב מודל מקומי** — `*-cloud` נחסם על מכסה ופוסל פרסור.
3. **שינוי config ב-API לא מחלחל למסמכים קיימים** — `deep_merge` שומר ערכים ישנים,
   וה-`llm_id` נשמר גם ברמת ה-document. אחרי שינוי — למחוק+להעלות מחדש, או
   לעדכן document-level. ה-task_executor קורא `llm_id` מה-**document**, לא מה-kb.
4. **`gpt-oss:120b@Ollama` (מקומי) גדול מ-VRAM** (61GB > 24GB) → זוחל על CPU. להשתמש ב-20b/26b.
5. **`{knowledge}` חובה ב-system prompt** — בלעדיו המודל לא רואה את המאגר.
6. **חיבור Reranker הוא ברמת Chat, לא Dataset** — מופיע ב-dropdown ב-Chat → Settings.
7. **טבלאות/בלוקי-list ארוכים בלי `\n`** לא מתפצלים יפה — Qwen-embed (40K) מטפל
   בהם בזכות ההקשר הארוך.

---

## מודלים זמינים (Ollama, מקומי)

| תפקיד | מקומי (מומלץ) | cloud (תלוי מכסה) |
|---|---|---|
| Embedding | `qwen3-embedding:4b` (2560d) / `bge-m3` (1024d) | — |
| Reranker | `Qwen3-Reranker-4B` (קונטיינר FastAPI מקומי, GPU) / `bge-reranker-v2-m3` (TEI) | — |
| Enrichment / Answer | `gpt-oss:20b`, `gemma4:26b`, `qwen3:14b` | `gemma4:31b-cloud`, `gpt-oss:120b-cloud` |

**Qwen3-Reranker** רץ כקונטיינר FastAPI מקומי (`qwen-reranker:80`, רשת
`docker_ragflow`, GPU), מוגדר ב-RAGFlow תחת factory `HuggingFace`. ראו
`qwen_reranker/` בשורש הריפו.
