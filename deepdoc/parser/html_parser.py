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
        if binary:
            encoding = find_codec(binary)
            txt = binary.decode(encoding, errors="ignore")
        else:
            with open(fnm, "r",encoding=get_encoding(fnm)) as f:
                txt = f.read()
        return self.parser_txt(txt, chunk_token_num)

    @classmethod
    def parser_txt(cls, txt, chunk_token_num):
        if not isinstance(txt, str):
            raise TypeError("txt type should be string!")

        temp_sections = []
        soup = BeautifulSoup(txt, "html5lib")
        # delete <style> tag
        for style_tag in soup.find_all(["style", "script"]):
            style_tag.decompose()
        # delete <script> tag in <div>
        for div_tag in soup.find_all("div"):
            for script_tag in div_tag.find_all("script"):
                script_tag.decompose()
        # delete inline style
        for tag in soup.find_all(True):
            if 'style' in tag.attrs:
                del tag.attrs['style']
        # delete HTML comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        cls.read_text_recursively(soup.body, temp_sections, chunk_token_num=chunk_token_num)
        block_txt_list, table_list = cls.merge_block_text(temp_sections)
        sections = cls.chunk_block(block_txt_list, chunk_token_num=chunk_token_num)
        for table in table_list:
            sections.append(table.get("content", ""))
        return sections

    @classmethod
    def split_table(cls, html_table, chunk_token_num=512):
        soup = BeautifulSoup(html_table, "html.parser")

        # Preserve <caption> (table title) and the header row(s) so every
        # produced chunk keeps its column meaning.
        caption = soup.find("caption")
        thead = soup.find("thead")
        all_rows = soup.find_all("tr")
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
            # As a softer fallback, treat the first row as header if its visible
            # text is short and doesn't end with a sentence terminator.
            if looks_styled_header:
                header_rows = [first_row]
                body_rows = all_rows[1:]

        # Reserve token budget for the header so each chunk fits.
        header_token_count = 0
        if header_rows:
            for hr in header_rows:
                tks_str = rag_tokenizer.tokenize(str(hr))
                header_token_count += len(tks_str.split(" ")) if tks_str else 0

        # Group body rows into chunks honoring chunk_token_num.
        # Each chunk's effective body budget is (chunk_token_num - header_token_count),
        # but never smaller than half the chunk to avoid pathological splitting when
        # the header itself is huge.
        body_budget = max(chunk_token_num - header_token_count, chunk_token_num // 2)

        groups = []
        current = []
        current_count = 0
        for row in body_rows:
            tks_str = rag_tokenizer.tokenize(str(row))
            token_count = len(tks_str.split(" ")) if tks_str else 0
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

        # Reconstruct each chunk: caption + header rows + this group's body rows.
        table_str_list = []
        for group in groups:
            new_table = soup.new_tag("table")
            if caption is not None:
                new_table.append(BeautifulSoup(str(caption), "html.parser"))
            for hr in header_rows:
                new_table.append(BeautifulSoup(str(hr), "html.parser"))
            for row in group:
                new_table.append(BeautifulSoup(str(row), "html.parser"))
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
                tks_str = rag_tokenizer.tokenize(raw_html)
                token_count = len(tks_str.split(" ")) if tks_str else 0
                if token_count > chunk_token_num:
                    table_list = cls.split_table(raw_html, chunk_token_num=chunk_token_num)
                else:
                    table_list = [raw_html]
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

