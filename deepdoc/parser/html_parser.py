# -*- coding: utf-8 -*-
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from rag.nlp import find_codec, rag_tokenizer
import uuid
import chardet
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
import html
import re

def get_encoding(file):
    with open(file,'rb') as f:
        tmp = chardet.detect(f.read())
        return tmp['encoding']

BLOCK_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "div", "article", "section", "aside",
    "ul", "ol", "li",
    "table", "pre", "code", "blockquote",
    "figure", "figcaption"
]
TITLE_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}


class RAGFlowHtmlParser:
    def __call__(self, fnm, binary=None, chunk_token_num=512):
        return self.parser_txt(self._read(fnm, binary), chunk_token_num)

    def parts(self, fnm, binary=None, chunk_token_num=512, table_token_num=None):
        """Like __call__, but returns (prose_sections, table_html_list).

        ``table_token_num`` is the size above which a table is pre-split
        (default: chunk_token_num). With parent-child retrieval the caller
        passes a larger budget: the whole table then becomes the parent the
        LLM reads, and tokenize_table() cuts it into small row children.
        """
        return self.parser_txt_parts(self._read(fnm, binary), chunk_token_num, table_token_num)

    @classmethod
    def procedure_title(cls, fnm, binary=None):
        """Document title from <title> (or the first <h1>), or "" if none.

        These exports name files by number ("5088.html"), so the filename gives
        title_tks nothing to match. The bank's titles look like
        "מיסוי - שו"ת- בנקאות ונכסים - ניכוי מס מתשלומים לחו"ל או לתושבי חוץ - 5088":
        drop the trailing id and keep the last segment, the procedure name. The
        leading category segments are shared by many documents and would make
        every one of them match generic words.
        """
        try:
            soup = BeautifulSoup(cls._read(fnm, binary), "html.parser")
        except Exception:
            return ""
        node = soup.find("title") or soup.find("h1")
        text = " ".join(node.get_text(" ").split()) if node else ""
        text = re.sub(r"[‎‏‪-‮]", "", text)
        text = re.sub(r"\s*-\s*\d+\s*$", "", text)
        parts = [p.strip() for p in re.split(r"\s+-\s+", text) if p.strip()]
        if len(parts) <= 1:
            return parts[0] if parts else ""
        # "<topic> - <area> - שו"ת- בנקאות ונכסים - <name> [- <sub>] - <id>":
        # the name is everything after the category marker (it may itself
        # contain " - ", e.g. 'אופציות על מדד ת"א - 35'). Without the marker,
        # skip the two leading category segments.
        marker = max((i for i, p in enumerate(parts) if 'שו"ת' in p or "בנקאות ונכסים" in p), default=None)
        tail = parts[marker + 1:] if marker is not None else parts[2:]
        return " - ".join(tail) if tail else parts[-1]

    @staticmethod
    def _read(fnm, binary=None):
        if binary:
            encoding = find_codec(binary)
            return binary.decode(encoding, errors="ignore")
        with open(fnm, "r", encoding=get_encoding(fnm)) as f:
            return f.read()

    @classmethod
    def parser_txt(cls, txt, chunk_token_num):
        if not isinstance(txt, str):
            raise TypeError("txt type should be string!")

        soup = cls._clean_soup(txt)
        prose, tables = cls._parse_parts(soup, chunk_token_num)
        # Backwards-compatible shape: prose followed by tables, all as bare
        # strings. Callers that need tables kept separate (so they can be typed
        # as doc_type_kwd="table" and split into children) use parser_txt_parts.
        return prose + tables

    @classmethod
    def _clean_soup(cls, txt):
        soup = BeautifulSoup(txt, "html5lib")
        # delete <style> tag
        for style_tag in soup.find_all(["style", "script"]):
            style_tag.decompose()
        # delete <script> tag in <div>
        for div_tag in soup.find_all("div"):
            for script_tag in div_tag.find_all("script"):
                script_tag.decompose()
        # delete inline style, except on table cells: split_table() relies on the
        # exporter's background-color/bold styling to detect the header row, and
        # stripping it here would run before that check ever sees it.
        for tag in soup.find_all(True):
            if 'style' in tag.attrs and tag.name not in ("td", "th", "tr"):
                del tag.attrs['style']
        # delete HTML comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        return soup

    @staticmethod
    def _text_tokens(html_fragment):
        """Token count of the VISIBLE text of a fragment.

        Counting raw HTML was dominated by the inline style that is kept on
        td/th/tr until split_table() reads it (width:509.35pt;padding:...): a
        5-row, 233-char fee table counted as >256 tokens, was split one row
        per chunk, and the rows lost their header ("שאר הסניפים 10,000,000 ₪"
        with no column names), so retrieval could not match them.
        """
        text = BeautifulSoup(html_fragment, "html.parser").get_text(" ")
        tks = rag_tokenizer.tokenize(text)
        return len(tks.split(" ")) if tks else 0

    @classmethod
    def _parse_parts(cls, soup, chunk_token_num, table_token_num=None):
        temp_sections = []
        cls.read_text_recursively(soup.body, temp_sections, chunk_token_num=table_token_num or chunk_token_num)
        block_txt_list, table_list = cls.merge_block_text(temp_sections)
        prose = cls.chunk_block(block_txt_list, chunk_token_num=chunk_token_num)
        tables = [t.get("content", "") for t in table_list if t.get("content")]
        return prose, tables

    @classmethod
    def parser_txt_parts(cls, txt, chunk_token_num, table_token_num=None):
        """Same parse as parser_txt, but keeps prose and tables apart.

        parser_txt() flattens tables into the prose list, which loses their
        identity: downstream they reach tokenize_chunks() and never get
        doc_type_kwd="table", so no HTML table is ever recognised as a table or
        split into child chunks. Returns (prose_sections, table_html_list).
        """
        if not isinstance(txt, str):
            raise TypeError("txt type should be string!")
        soup = cls._clean_soup(txt)
        return cls._parse_parts(soup, chunk_token_num, table_token_num)

    @classmethod
    def strip_inline_style(cls, html_fragment):
        """Remove style attributes from a table fragment.

        parser_txt() deliberately keeps inline style on td/th/tr so split_table()
        can read the exporter's header styling, but that CSS must never reach a
        stored chunk. Both table paths funnel through here on the way out.
        """
        frag = BeautifulSoup(html_fragment, "html.parser")
        for tag in frag.find_all(True):
            tag.attrs.pop("style", None)
        return str(frag)

    @classmethod
    def split_table(cls, html_table, chunk_token_num=512):
        soup = BeautifulSoup(html_table, "html.parser")

        # Preserve <caption> (table title) and the header row(s) so every
        # produced chunk keeps its column meaning.
        # Only the OUTER table's own rows: find_all("tr") also returned every
        # row of a nested table, which then appeared twice (inside its outer
        # row and again as a loose row with no header).
        outer = soup.find("table")
        caption = outer.find("caption", recursive=False) if outer else None
        thead = outer.find("thead", recursive=False) if outer else None
        all_rows = [r for r in soup.find_all("tr") if r.find_parent("table") is outer]
        header_rows = []
        body_rows = list(all_rows)
        if thead:
            header_rows = thead.find_all("tr")
            # Drop the header rows from body_rows.
            body_rows = [r for r in all_rows if r not in header_rows]
        elif all_rows and all_rows[0].find("th") is not None:
            # No <thead>, but the first <tr> contains <th> cells — treat as header.
            header_rows = [all_rows[0]]
            body_rows = all_rows[1:]
        elif len(all_rows) >= 3:
            # No semantic <th>/<thead> (common in Aspose-exported HTML).
            # Heuristic: treat the first <tr> as a header if the table has at least
            # 3 rows AND the first row looks "different" from later rows. Specifically:
            #   - styled with a background color or bold (Aspose sentinels), OR
            #   - first cell short and looks like a column label (no period, <40 chars).
            first_row = all_rows[0]
            first_str = str(first_row).lower()
            looks_styled_header = (
                "background-color" in first_str and
                any(color in first_str for color in [
                    "#0070c0",  # blue used by Aspose for the bank's procedure tables
                    "#1f4e78", "#2e74b5", "#5b9bd5",  # blue family
                    "#a9d18e", "#70ad47",  # green family
                    "#f4b083", "#ed7d31",  # orange family
                    "#bf504d", "#c00000",  # red family
                ])
            ) or "font-weight:bold" in first_str
            # Bold markup is the other common way an exporter flags a header row
            # (the bank's HTML wraps header cells in <strong>/<b> with no inline
            # style), so treat a first row whose cells are all bold as a header.
            if not looks_styled_header:
                first_cells = first_row.find_all(["td", "th"])
                if first_cells:
                    bolded = [c for c in first_cells if c.find(["strong", "b"]) is not None]
                    non_empty = [c for c in first_cells if c.get_text(strip=True)]
                    looks_styled_header = bool(non_empty) and len(bolded) >= len(non_empty)
            # NOTE: no "short text" fallback here on purpose. Tables whose first
            # row is genuinely data (e.g. "סניף 0 | 500 | פעיל") also have short,
            # terminator-free cells, so such a rule promotes a data row to a
            # header and duplicates it into every chunk. Only explicit header
            # markup (thead/th) or exporter styling (background/bold) is trusted.
            if looks_styled_header:
                header_rows = [first_row]
                body_rows = all_rows[1:]

        # Reserve token budget for the header so each chunk fits.
        # The NOTE above rejects promoting an unstyled first row in general.
        # But when the table must be cut into several chunks anyway, a chunk
        # without column names is worse than one repeated data row: in the
        # 40-question eval every table miss was a headerless fragment such as
        # "דחוי | מזומן" whose columns the model could not tell apart. So the
        # first row is repeated only when a split is unavoidable.
        if not header_rows and len(all_rows) >= 3 and len(all_rows[0].find_all(["td", "th"])) >= 2:
            if sum(cls._text_tokens(str(r)) for r in all_rows) > chunk_token_num:
                header_rows = [all_rows[0]]
                body_rows = all_rows[1:]

        header_token_count = sum(cls._text_tokens(str(hr)) for hr in header_rows)

        # Group body rows into chunks honoring chunk_token_num.
        # Each chunk's effective body budget is (chunk_token_num - header_token_count),
        # but never smaller than half the chunk to avoid pathological splitting when
        # the header itself is huge.
        body_budget = max(chunk_token_num - header_token_count, chunk_token_num // 2)

        groups = []
        current = []
        current_count = 0
        for row in body_rows:
            token_count = cls._text_tokens(str(row))
            if current and current_count + token_count > body_budget:
                groups.append(current)
                current = []
                current_count = 0
            current.append(row)
            current_count += token_count
        if current:
            groups.append(current)
        if not groups:
            # Header-only table or empty body — emit a single chunk with what we have.
            groups = [[]]

        # The header heuristics above have consumed the styling signal, so drop
        # the attribute now: it must not reach the stored chunk, where CSS like
        # "width:509.35pt; padding:0.75pt 5.4pt" would eat the token budget and
        # be indexed as searchable text.
        def _clean(node):
            frag = BeautifulSoup(str(node), "html.parser")
            for tag in frag.find_all(True):
                tag.attrs.pop("style", None)
            return frag

        # Reconstruct each chunk: caption + header rows + this group's body rows.
        table_str_list = []
        for group in groups:
            new_table = soup.new_tag("table")
            if caption is not None:
                new_table.append(_clean(caption))
            for hr in header_rows:
                new_table.append(_clean(hr))
            for row in group:
                new_table.append(_clean(row))
            table_str_list.append(str(new_table))

        return table_str_list

    @classmethod
    def read_text_recursively(cls, element, parser_result, chunk_token_num=512, parent_name=None, block_id=None):
        if isinstance(element, NavigableString):
            content = element.strip()

            def is_valid_html(content):
                try:
                    soup = BeautifulSoup(content, "html.parser")
                    return bool(soup.find())
                except Exception:
                    return False

            return_info = []
            if content:
                if is_valid_html(content):
                    soup = BeautifulSoup(content, "html.parser")
                    child_info = cls.read_text_recursively(soup, parser_result, chunk_token_num, element.name, block_id)
                    parser_result.extend(child_info)
                else:
                    info = {"content": element.strip(), "tag_name": "inner_text", "metadata": {"block_id": block_id}}
                    if parent_name:
                        info["tag_name"] = parent_name
                    return_info.append(info)
            return return_info
        elif isinstance(element, Tag):

            if str.lower(element.name) == "table":
                table_info_list = []
                table_id = str(uuid.uuid1())
                # Split large tables into chunks of chunk_token_num tokens each.
                # Without this, a single huge table (e.g. Aspose-exported HTML where the
                # entire document body is wrapped in one table) becomes one giant chunk
                # that exceeds the LLM context budget for retrieval-fed generation.
                raw_html = html.unescape(str(element))
                token_count = cls._text_tokens(raw_html)
                if token_count > chunk_token_num:
                    table_list = cls.split_table(raw_html, chunk_token_num=chunk_token_num)
                else:
                    # split_table() strips inline style on its way out; a table
                    # small enough to skip splitting must be cleaned too, or its
                    # CSS ends up indexed as searchable text.
                    table_list = [cls.strip_inline_style(raw_html)]
                for idx, t in enumerate(table_list):
                    table_info_list.append({"content": t, "tag_name": "table",
                                            "metadata": {"table_id": table_id, "index": idx}})
                return table_info_list
            else:
                if str.lower(element.name) in BLOCK_TAGS:
                    block_id = str(uuid.uuid1())
                for child in element.children:
                    child_info = cls.read_text_recursively(child, parser_result, chunk_token_num, element.name,
                                                           block_id)
                    parser_result.extend(child_info)
        return []

    @classmethod
    def merge_block_text(cls, parser_result):
        block_content = []
        current_content = ""
        table_info_list = []
        last_block_id = None
        for item in parser_result:
            content = item.get("content")
            tag_name = item.get("tag_name")
            title_flag = tag_name in TITLE_TAGS
            block_id = item.get("metadata", {}).get("block_id")
            if block_id:
                if title_flag:
                    content = f"{TITLE_TAGS[tag_name]} {content}"
                if last_block_id != block_id:
                    if last_block_id is not None:
                        block_content.append(current_content)
                    current_content = content
                    last_block_id = block_id
                else:
                    current_content += (" " if current_content else "") + content
            else:
                if tag_name == "table":
                    table_info_list.append(item)
                else:
                    current_content += (" " if current_content else "") + content
        if current_content:
            block_content.append(current_content)
        return block_content, table_info_list

    @classmethod
    def chunk_block(cls, block_txt_list, chunk_token_num=512):
        chunks = []
        current_block = ""
        current_token_count = 0

        for block in block_txt_list:
            tks_str = rag_tokenizer.tokenize(block)
            block_token_count = len(tks_str.split(" ")) if tks_str else 0
            if block_token_count > chunk_token_num:
                if current_block:
                    chunks.append(current_block)
                start = 0
                tokens = tks_str.split(" ")
                while start < len(tokens):
                    end = start + chunk_token_num
                    split_tokens = tokens[start:end]
                    chunks.append(" ".join(split_tokens))
                    start = end
                current_block = ""
                current_token_count = 0
            else:
                if current_token_count + block_token_count <= chunk_token_num:
                    current_block += ("\n" if current_block else "") + block
                    current_token_count += block_token_count
                else:
                    chunks.append(current_block)
                    current_block = block
                    current_token_count = block_token_count

        if current_block:
            chunks.append(current_block)

        return chunks

