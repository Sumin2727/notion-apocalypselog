# notion_export.py
import os, json, time, requests

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
NOTION_VERSION = "2025-09-03"

S = requests.Session()
S.headers.update({
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
})

def list_children(block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    out, cursor = [], None
    while True:
        params = {"start_cursor": cursor} if cursor else {}
        r = S.get(url, params=params)
        if r.status_code == 429:
            time.sleep(1.0); continue
        r.raise_for_status()
        data = r.json()
        out += data.get("results", [])
        cursor = data.get("next_cursor")
        if not cursor: break
    return out

def fetch_tree(root_id):
    kids = list_children(root_id)
    tree = []
    for b in kids:
        node = {"id": b["id"], "type": b["type"], "raw": b}
        if b.get("has_children"):
            node["children"] = fetch_tree(b["id"])
        tree.append(node)
    return tree

def rich_text(rt): 
    return "".join(span.get("plain_text","") for span in (rt or []))

def to_text(node, depth=0):
    b, t = node["raw"], node["raw"]["type"]
    ind = "  " * depth
    line = ""
    try:
        if t == "paragraph":
            line = rich_text(b[t]["rich_text"])
        elif t.startswith("heading_"):
            level = {"heading_1":1,"heading_2":2,"heading_3":3}[t]
            line = ("#"*level) + " " + rich_text(b[t]["rich_text"])
        elif t in ("bulleted_list_item","numbered_list_item"):
            bullet = "-" if t=="bulleted_list_item" else "1."
            line = f"{bullet} " + rich_text(b[t]["rich_text"])
        elif t == "to_do":
            chk = "[x]" if b[t]["checked"] else "[ ]"
            line = f"{chk} " + rich_text(b[t]["rich_text"])
        elif t == "quote":
            line = "> " + rich_text(b[t]["rich_text"])
        elif t == "code":
            lang = b[t].get("language","")
            line = f"```{lang}\n{rich_text(b[t]['rich_text'])}\n```"
        elif t == "callout":
            line = "💡 " + rich_text(b[t]["rich_text"])
        elif t == "image":
            line = "[image]"
        else:
            line = f"[{t}]"
    except Exception:
        line = "[unparsed]"
    for c in node.get("children", []):
        line += "\n" + to_text(c, depth+1)
    return (ind + line).rstrip()

if __name__ == "__main__":
    assert NOTION_TOKEN and PAGE_ID, "Set NOTION_TOKEN & PAGE_ID."
    tree = fetch_tree(PAGE_ID)

    with open("notion_export.json","w",encoding="utf-8") as f:
        json.dump(tree,f,ensure_ascii=False,indent=2)

    txt = "\n".join(to_text(n) for n in tree)
    with open("notion_export.txt","w",encoding="utf-8") as f:
        f.write(txt)

    # summary.md 생성 (예쁘게 정리된 마크다운)
    def pretty_md(node, depth=0):
        t = node["raw"]["type"]
        b = node["raw"]
        text = ""
        if t.startswith("heading_"):
            level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[t]
            text = f"{level} {rich_text(b[t]['rich_text'])}"
        elif t in ("bulleted_list_item", "numbered_list_item"):
            bullet = "-" if t=="bulleted_list_item" else "1."
            text = f"{'  '*depth}{bullet} {rich_text(b[t]['rich_text'])}"
        elif t == "to_do":
            check = "x" if b[t]["checked"] else " "
            text = f"{'  '*depth}- [{check}] {rich_text(b[t]['rich_text'])}"
        elif t == "quote":
            text = f"> {rich_text(b[t]['rich_text'])}"
        elif t == "callout":
            text = f"> 💡 {rich_text(b[t]['rich_text'])}"
        elif t == "code":
            lang = b[t].get("language","")
            text = f"```{lang}\n{rich_text(b[t]['rich_text'])}\n```"
        elif t == "paragraph":
            content = rich_text(b[t]['rich_text'])
            if content.strip():
                text = content
        elif t == "image":
            text = "![이미지](image.png)"  # 간단 대체
        else:
            text = f"[{t}]"

        # 자식 노드 처리
        children = [pretty_md(c, depth+1) for c in node.get("children",[])]
        return "\n".join([text]+[c for c in children if c])

    md_text = "# 📒 Notion Export Summary\n\n"
    md_text += f"업데이트 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_text += "\n".join(pretty_md(n) for n in tree)

    with open("summary.md","w",encoding="utf-8") as f:
        f.write(md_text)


    print("✅ Exported: notion_export.json, notion_export.txt, summary.md")
