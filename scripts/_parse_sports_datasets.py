import html
import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "体育开源数据集调研" / "图片和附件" / (
    "%E4%BD%93%E8%82%B2AI_CV_112%E9%A1%B9_%E6%8C%89%E8%BF%90%E5%8A%A8%E5%88%86%E7%B1%BB_"
    "%E4%BA%A4%E4%BA%92%E5%AF%BC%E8%88%AA%E4%B8%8E%E7%BB%9F%E8%AE%A1%E7%89%88.html"
)
text = path.read_text(encoding="utf-8")
arts = re.findall(r'<article class="dataset"([^>]*)>(.*?)</article>', text, flags=re.S)

items = []
for attrs, body in arts:
    name_m = re.search(r"<strong>([^<]+)</strong>", body)
    cn_m = re.search(r'<div class="cn">([^<]*)</div>', body)
    urls = re.findall(r'href="(https?://[^"]+)"', body)

    def data_attr(key):
        m = re.search(rf'data-{key}="([^"]*)"', attrs)
        return html.unescape(m.group(1)) if m else ""

    items.append(
        {
            "name": name_m.group(1) if name_m else "",
            "cn": cn_m.group(1) if cn_m else "",
            "cat": data_attr("cat"),
            "sub": data_attr("sub"),
            "modal": data_attr("modal"),
            "task": data_attr("task"),
            "keywords": data_attr("keywords"),
            "urls": urls,
        }
    )

keys = [
    "squat", "深蹲", "fitness", "健身", "yoga", "瑜伽", "rehab", "康复",
    "workout", "exercise", "rep", "重复", "prmd", "kinect", "plank", "平板",
    "gympose", "lunge", "开合", "jumping",
]

out_path = Path(__file__).resolve().parent / "_sports_datasets_fitness.txt"
lines = [f"TOTAL {len(items)}\n"]

for it in items:
    blob = " ".join([it["name"], it["cn"], it["keywords"], it["cat"], it["sub"]]).lower()
    fitness_cat = it["cat"] == "健身与其他运动"
    hit = any(k in blob for k in keys)
    has_video = "视频" in it["modal"]
    if not has_video:
        continue
    if not (fitness_cat or hit):
        continue
    lines.append("---")
    lines.append(f"{it['name']} | {it['cn']}")
    lines.append(f"{it['cat']} / {it['sub']}")
    lines.append(f"模态: {it['modal']} | 任务: {it['task']}")
    for u in it["urls"][:2]:
        lines.append(u)
    lines.append("")

# pose quality section
lines.append("\n=== 跨项目人体姿态与动作质量（含视频）===\n")
for it in items:
    if "姿态" in it["sub"] and "质量" in it["sub"] and "视频" in it["modal"]:
        lines.append(f"{it['name']} -> {it['urls'][0] if it['urls'] else ''}")

out_path.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out_path)
