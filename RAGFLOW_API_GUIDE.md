# RAGFlow API — הנחיה ל-Claude (מכונה מרוחקת)

מסמך זה נותן ל-Claude את כל מה שצריך כדי לעבוד מול שרת RAGFlow מרוחק:
יצירת dataset, העלאת קבצים, והפעלת parsing — דרך ה-HTTP API בלבד.
כל ה-endpoints כאן **אומתו בקריאה חיה** מול השרת (לא תיעוד תיאורטי).

---

## פרטי חיבור

| פרמטר | ערך |
|---|---|
| **Base URL (LAN)** | `http://10.100.102.7:9380` |
| **Base URL (אותה מכונה)** | `http://localhost:9380` |
| **API prefix** | `/api/v1` |
| **API Key (Bearer)** | `ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI` |
| **Embedding model** | `bge-m3@Ollama` |
| **גרסת שרת** | RAGFlow v0.25.0 (Docker) |

כל בקשה נושאת header:
```
Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI
```

תשובת הצלחה תמיד מחזירה JSON עם `"code": 0`. כל code אחר = שגיאה, הסבר ב-`"message"`.

---

## הזרימה: 3 קריאות מקצה לקצה

```
1. POST /api/v1/datasets                   → יוצר KB,    מחזיר dataset_id
2. POST /api/v1/datasets/{id}/documents    → מעלה קובץ,  מחזיר document_id   (multipart, -F file)
3. POST /api/v1/datasets/{id}/chunks       → מפעיל parsing+embedding         (JSON: document_ids)
```

ה-parsing (chunking + embedding) רץ **אסינכרונית** ברקע ע"י task-executor. שלב 3 רק מפעיל אותו ומחזיר מיד;
כדי לדעת שהסתיים, סקור את סטטוס המסמך (ראה "מעקב התקדמות").

---

## 1. יצירת Dataset

`POST /api/v1/datasets`  ·  Content-Type: application/json

```bash
curl -X POST "http://10.100.102.7:9380/api/v1/datasets" \
  -H "Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI" \
  -H "Content-Type: application/json" \
  -d '{"name":"my_dataset","embedding_model":"bge-m3@Ollama","chunk_method":"naive"}'
```

| שדה | חובה | ברירת מחדל |
|---|---|---|
| `name` | ✅ כן (ייחודי) | — |
| `embedding_model` | לא | ברירת המחדל של ה-tenant |
| `chunk_method` | לא | `naive` |

תשובה: `data.id` = ה-`dataset_id`.

## 2. העלאת קובץ

`POST /api/v1/datasets/{dataset_id}/documents`  ·  multipart/form-data, שדה `file`
(אפשר לצרף כמה `file` בבקשה אחת)

```bash
curl -X POST "http://10.100.102.7:9380/api/v1/datasets/<DATASET_ID>/documents" \
  -H "Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI" \
  -F "file=@/path/to/file.pdf"
```
תשובה: `data` הוא מערך; `data[0].id` = ה-`document_id`.

## 3. הפעלת Parsing

`POST /api/v1/datasets/{dataset_id}/chunks`  ·  Content-Type: application/json

```bash
curl -X POST "http://10.100.102.7:9380/api/v1/datasets/<DATASET_ID>/chunks" \
  -H "Authorization: Bearer ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["<DOCUMENT_ID>"]}'
```

---

## מעקב התקדמות parsing

`GET /api/v1/datasets/{dataset_id}/documents` — מחזיר רשימת מסמכים עם השדות:
- `run`  — `"0"`=ממתין, `"1"`=רץ, `"3"`=הסתיים, `"4"`=נכשל
- `progress` — 0.0 עד 1.0
- `chunk_count` — מספר ה-chunks שנוצרו

---

## סקריפט Python מלא (create → upload תיקייה → parse → המתנה)

```python
import requests, time, sys, os, glob

BASE = "http://10.100.102.7:9380/api/v1"
KEY  = "ragflow-D7SXwThLiLjXWvjtE8KjhhBYuAelBl5R57l69V4NNaI"
H    = {"Authorization": f"Bearer {KEY}"}
HJ   = {**H, "Content-Type": "application/json"}

def create_dataset(name):
    r = requests.post(f"{BASE}/datasets", headers=HJ,
                      json={"name": name, "embedding_model": "bge-m3@Ollama", "chunk_method": "naive"})
    j = r.json(); assert j["code"] == 0, j
    return j["data"]["id"]

def upload(dataset_id, path):
    with open(path, "rb") as fh:
        r = requests.post(f"{BASE}/datasets/{dataset_id}/documents", headers=H,
                          files={"file": (os.path.basename(path), fh)})
    j = r.json(); assert j["code"] == 0, j
    return j["data"][0]["id"]

def parse(dataset_id, doc_ids):
    r = requests.post(f"{BASE}/datasets/{dataset_id}/chunks", headers=HJ,
                      json={"document_ids": doc_ids})
    assert r.json()["code"] == 0, r.json()

def wait_done(dataset_id, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{BASE}/datasets/{dataset_id}/documents", headers=H)
        docs = r.json()["data"]["docs"]
        runs = {d["name"]: (d["run"], round(d.get("progress", 0), 2)) for d in docs}
        print(runs)
        if all(d["run"] in ("3", "4") for d in docs):
            return runs
        time.sleep(8)

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    ds = create_dataset("api_upload_" + str(int(time.time())))
    print("dataset:", ds)
    ids = []
    for f in glob.glob(os.path.join(folder, "*")):
        if os.path.isfile(f):
            ids.append(upload(ds, f)); print("uploaded:", f)
    parse(ds, ids)
    wait_done(ds)
    print("DONE")
```

הרצה: `python upload.py /path/to/folder`

---

## הערות ומלכודות (מאומתות)

1. **אל תשתמש ב-`POST /api/v1/datasets/{id}/documents/parse`** — מחזיר 405 בגרסה הזו.
   ה-parsing מופעל דרך `POST .../chunks` עם `document_ids` (כפי שמתועד למעלה).
2. ה-parsing אסינכרוני — שלב 3 חוזר מיד; המתן בעזרת ה-GET של המסמכים.
3. שמות dataset חייבים להיות ייחודיים ל-tenant; שם כפול מחזיר code שגיאה.
4. אם הקריאה ממכונה מרוחקת נכשלת ב-connection: ודא שפורט 9380 פתוח בחומת האש של מכונת השרת.
5. ה-API פועל ב-HTTP לא מוצפן — הטוקן חשוף ברשת. בסדר ל-LAN מבודד, לא לרשת ציבורית.

## Datasets קיימים בשרת זה (לעיון)

| שם | dataset_id |
|---|---|
| hozrim | `dc0091ca46e211f196f633ac796a3d7a` |
| hebrew-test | `3e76c53642bf11f1a6bba9e87ac7a32c` |
| test_five_files | `<query via GET /api/v1/datasets>` |
