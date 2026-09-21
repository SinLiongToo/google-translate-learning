#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google 翻譯詞庫互動學習系統 (G-Translate Learning System)
支援英語、法語（法翻英、英翻法、法翻中）等多語系自動辨識、母語口音發音 (TTS)、多維篩選與 3D 翻牌。
參考「工作的管見-書」工作流與架構，自動解析 CSV/試算表、擴充結構化詞庫，
生成高質感自包含互動學習網頁 (index.html)、學習手冊 (Markdown) 與專屬 Antigravity Skill。
"""

import os
import sys
import csv
import json
import re
import datetime
from pathlib import Path

# 設定 UTF-8 輸出
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent
DB_FILE = WORKSPACE_DIR / "vocab_db.json"
OVERRIDES_FILE = WORKSPACE_DIR / "manual_overrides.json"
HTML_OUTPUT = WORKSPACE_DIR / "index.html"
MD_OUTPUT = WORKSPACE_DIR / "單字與片語學習手冊.md"
README_OUTPUT = WORKSPACE_DIR / "README.md"
SKILL_DIR = WORKSPACE_DIR / ".agents" / "skills" / "google-translate-learning-workflow"
SKILL_FILE = SKILL_DIR / "SKILL.md"

# 關鍵字分類啟發式規則
CATEGORY_RULES = [
    ("商業財務", [
        "cash flow", "revenue", "gross margin", "operating", "headcount", "balance sheet", 
        "due diligence", "earnings", "audit", "working capital", "debt", "dividend", 
        "buyback", "capex", "solvency", "income statement", "profit", "fcf", "margin", 
        "equity", "invest", "financial", "asset", "liability", "expense", "valuation",
        "財報", "現金流", "淨利", "營運", "資本", "毛利率", "資產負債", "股利", "護城河", "損益表"
    ]),
    ("科技半導體", [
        "semi", "chip", "wafer", "design", "carbide", "cadence", "code", "boilerplate", 
        "hardware", "software", "algorithm", "fab", "foundry", "transistor", "lithography",
        "packaging", "substrate", "silicon", "gpu", "cpu", "node", "eda", "firmware",
        "半導體", "晶片", "晶圓", "碳化物", "程式碼", "演算法", "架構", "製程", "封裝"
    ]),
    ("職場管理", [
        "rigor", "imperative", "cadence", "drag", "productivity", "evaluation", "execution", 
        "process", "rule", "strategy", "management", "leadership", "organization", "objective",
        "okr", "kpi", "milestone", "stakeholder", "consensus", "alignment", "governance",
        "職場", "管理", "執行力", "組織", "策略", "領導", "專案", "評估", "敏捷", "指標"
    ]),
    ("生活哲思", [
        "eudaimonia", "stoicism", "time", "discipline", "youth", "story", "life", "habit", 
        "calm", "perspective", "philosophy", "wisdom", "mindful", "meaning", "happiness",
        "virtue", "destiny", "courage", "resilience", "existential", "solitude",
        "幸福", "哲學", "自律", "人生", "智慧", "習慣", "心態", "時間", "生命"
    ]),
    ("實用表達", []) # 預設類別
]

def find_input_csv():
    """自動尋找專案目錄中最合適的 CSV/TSV 來源檔"""
    candidates = [
        "g_translate.csv.csv",
        "g_translate.csv",
        "已儲存的翻譯.csv",
        "saved_translations.csv",
        "phrasebook.csv"
    ]
    for c in candidates:
        p = WORKSPACE_DIR / c
        if p.exists() and p.stat().st_size > 0:
            return p
            
    for f in WORKSPACE_DIR.glob("*.csv"):
        if f.name != "translation_db.csv" and f.stat().st_size > 0:
            return f
            
    return None

def clean_text(text: str) -> str:
    """清理文字雜訊與多餘空白"""
    if not text:
        return ""
    text = text.strip()
    if text.startswith('"') and text.endswith('"') and len(text) > 2:
        text = text[1:-1].strip()
    return text

def normalize_lang(name: str, sample_text: str = ""):
    """標準化語言代碼、名稱、TTS 發音代碼與國旗符號"""
    n = name.lower().strip()
    if '法' in n or 'french' in n or n == 'fr':
        return 'fr', '法文', 'fr-FR', '🇫🇷'
    if '中' in n or 'chinese' in n or n in ['zh', 'zh-tw', 'zh-cn']:
        return 'zh', '繁中', 'zh-TW', '🇹🇼'
    if '英' in n or 'english' in n or n == 'en':
        return 'en', '英文', 'en-US', '🇬🇧'
    if '德' in n or 'german' in n or n == 'de':
        return 'de', '德文', 'de-DE', '🇩🇪'
    if re.search(r'[\u4e00-\u9fff]', sample_text):
        return 'zh', '繁中', 'zh-TW', '🇹🇼'
    return 'en', '英文', 'en-US', '🇬🇧'

def infer_category(front_text: str, back_text: str) -> str:
    """依據文本關鍵字自動分類"""
    combined = (front_text + " " + back_text).lower()
    for cat_name, keywords in CATEGORY_RULES[:-1]:
        for kw in keywords:
            if kw.lower() in combined:
                return cat_name
    return "實用表達"

def determine_type(text: str) -> str:
    """判斷項目類型：單字 (word)、片語 (phrase)、實用句型/文章 (sentence)"""
    lines = text.strip().split("\n")
    words = text.strip().split()
    word_count = len(words)
    
    if len(lines) > 1 or word_count > 12 or (word_count > 7 and any(p in text for p in [".", "?", "!", ":", ";"])):
        return "sentence"
    elif word_count > 1:
        return "phrase"
    else:
        return "word"

def parse_csv_items(csv_path: Path):
    """解析 Google 翻譯 CSV 檔案，完整辨別法語、英語與繁中等語言對"""
    items = []
    print(f"📖 正在解析資料來源: {csv_path.name}...")
    
    with open(csv_path, mode='r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row_idx, row in enumerate(reader, 1):
            if not row or len(row) < 4:
                continue
            
            src_raw = clean_text(row[0])
            tgt_raw = clean_text(row[1])
            col_c = clean_text(row[2])
            col_d = clean_text(row[3])
            
            if not col_c or not col_d:
                continue
                
            s_code, s_name, s_voice, s_flag = normalize_lang(src_raw, col_c)
            t_code, t_name, t_voice, t_flag = normalize_lang(tgt_raw, col_d)
            
            # 判斷是否為法語對翻項目
            is_french = (s_code == 'fr' or t_code == 'fr')
            
            # 定義語言對 key 與群組
            raw_pair = f"{s_code}-{t_code}"
            if is_french:
                if (s_code, t_code) in [('fr', 'en'), ('en', 'fr')]:
                    lang_group = "fr-en"
                    lang_pair_name = "法語 ⇄ 英語"
                elif (s_code, t_code) in [('fr', 'zh'), ('zh', 'fr')]:
                    lang_group = "fr-zh"
                    lang_pair_name = "法語 ⇄ 中文"
                else:
                    lang_group = "fr-all"
                    lang_pair_name = "法語對翻"
            elif (s_code, t_code) in [('en', 'zh'), ('zh', 'en')]:
                lang_group = "en-zh"
                lang_pair_name = "英語 ⇄ 中文"
            else:
                lang_group = "other"
                lang_pair_name = f"{s_name} ⇄ {t_name}"

            # 徽章標籤 (例如：🇫🇷 法文 ➔ 🇬🇧 英文)
            lang_badge = f"{s_flag} {s_name} ➔ {t_flag} {t_name}"
            
            item_type = determine_type(col_c)
            category = infer_category(col_c, col_d)
            
            normalized_key = re.sub(r'[^a-zA-Z0-9\s]', '', col_c.lower()).strip()
            if not normalized_key:
                normalized_key = f"item_{row_idx}"
            else:
                normalized_key = "_".join(normalized_key.split()[:5])
                
            items.append({
                "id": f"item_{row_idx:04d}",
                "key": normalized_key,
                # 正反面通用定義
                "front": col_c,
                "back": col_d,
                "front_lang": s_name,
                "front_flag": s_flag,
                "front_voice": s_voice,
                "back_lang": t_name,
                "back_flag": t_flag,
                "back_voice": t_voice,
                "lang_pair": raw_pair,
                "lang_group": lang_group,
                "lang_badge": lang_badge,
                "lang_pair_name": lang_pair_name,
                "is_french": is_french,
                # 向後相容欄位
                "en": col_c,
                "zh": col_d,
                "type": item_type,
                "category": category,
                "notes": "",
                "mastery": "learning"
            })
            
    french_count = len([x for x in items if x["is_french"]])
    print(f"✅ 成功讀取 {len(items)} 筆項目！其中法語對翻共 {french_count} 筆，英語/中文共 {len(items) - french_count} 筆。")
    return items

def load_manual_overrides():
    """載入人工手動覆蓋庫 (最高優先級)"""
    if not OVERRIDES_FILE.exists():
        default_overrides = {
            "_README": "👑 這是最高優先級的人工自訂覆蓋庫。在此設定的條目權重最高，執行更新時絕不會被覆蓋。",
            "overrides": {}
        }
        with open(OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_overrides, f, ensure_ascii=False, indent=2)
        return {}
        
    try:
        with open(OVERRIDES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("overrides", {})
    except Exception as e:
        print(f"⚠️ 讀取 manual_overrides.json 失敗: {e}")
        return {}

def merge_and_cache(items, overrides):
    """合併現有快取資料庫與手動自訂覆蓋庫"""
    cached_db = {}
    if DB_FILE.exists():
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                cached_list = json.load(f)
                for item in cached_list:
                    cached_db[item.get("front", item.get("en", "")).strip().lower()] = item
        except Exception as e:
            print(f"⚠️ 讀取 vocab_db.json 快取失敗: {e}")
            
    final_items = []
    for item in items:
        lookup_key = item["front"].strip().lower()
        
        if lookup_key in cached_db:
            cached_item = cached_db[lookup_key]
            if cached_item.get("mastery"):
                item["mastery"] = cached_item["mastery"]
            if cached_item.get("notes") and not item.get("notes"):
                item["notes"] = cached_item["notes"]
                
        matched_override = None
        for ov_key, ov_val in overrides.items():
            if ov_key.strip().lower() == lookup_key or ov_key.strip().lower() == item["key"]:
                matched_override = ov_val
                break
                
        if matched_override:
            if "back" in matched_override:
                item["back"] = matched_override["back"]
                item["zh"] = matched_override["back"]
            elif "zh" in matched_override:
                item["back"] = matched_override["zh"]
                item["zh"] = matched_override["zh"]
                
            if "front" in matched_override:
                item["front"] = matched_override["front"]
                item["en"] = matched_override["front"]
            elif "en" in matched_override:
                item["front"] = matched_override["en"]
                item["en"] = matched_override["en"]
                
            if "category" in matched_override:
                item["category"] = matched_override["category"]
            if "notes" in matched_override:
                item["notes"] = matched_override["notes"]
            if "mastery" in matched_override:
                item["mastery"] = matched_override["mastery"]
                
        final_items.append(item)
        
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_items, f, ensure_ascii=False, indent=2)
        
    print(f"💾 快取已寫入 {DB_FILE.name} (共 {len(final_items)} 筆)")
    return final_items

def generate_markdown_handbook(items):
    """生成結構精美、分類嚴整的 Markdown 學習手冊，特設法語專章"""
    french_items = [x for x in items if x["is_french"]]
    en_items = [x for x in items if not x["is_french"]]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = [
        "# 📚 Google 翻譯詞庫：結構化學習手冊 (G-Translate Learning Handbook)",
        "",
        f"> 🕒 **最後更新時間**：{now_str}  ",
        f"> 📊 **收錄總量**：{len(items)} 筆（🇬🇧 英語/繁中：{len(en_items)} 筆 | 🇫🇷 法語對翻：{len(french_items)} 筆）  ",
        "> 💡 **搭配互動網頁**：請雙擊開啟同目錄下的 [`index.html`](file:///./index.html) 進行 3D 卡牌抽測、自我評量與知識圖譜探索。",
        "",
        "---",
        "",
        "## 📑 目錄導航 (Table of Contents)",
        f"- [第一部分：🇫🇷 法語對翻專題篇 ({len(french_items)} 則)](#第一部分法語對翻專題篇)",
        f"- [第二部分：🇬🇧 英語 ⇄ 繁中精選篇 ({len(en_items)} 則)](#第二部分英語繁中精選篇)",
        "- [第三部分：核心單字速查 (Words)](#第三部分核心單字速查)",
        "- [第四部分：實用長句與商業分析段落 (Sentences)](#第四部分實用長句與商業分析段落)",
        "",
        "---",
        "",
        f"## 第一部分：🇫🇷 法語對翻專題篇 ({len(french_items)} 則)",
        "",
        "> 本章收錄您自 Google 翻譯儲存之法文對翻詞句（包含法翻英、英翻法、法翻中）。",
        ""
    ]
    
    for idx, f_item in enumerate(french_items, 1):
        note_str = f" *（備註：{f_item['notes']}）*" if f_item.get('notes') else ""
        lines.append(f"**{idx}. [{f_item['lang_badge']}] {f_item['front']}**  ")
        lines.append(f"- 💡 **譯文**：{f_item['back']}{note_str}  ")
        lines.append(f"- 🏷️ **類型**：`{f_item['type']}` | 🆔 `{f_item['id']}`  ")
        lines.append("")
        
    lines.extend([
        "---",
        "",
        f"## 第二部分：🇬🇧 英語 ⇄ 繁中精選篇 ({len(en_items)} 則)",
        ""
    ])
    
    en_categories = {}
    for item in en_items:
        cat = item.get("category", "實用表達")
        en_categories.setdefault(cat, []).append(item)
        
    for cat_name, cat_items in en_categories.items():
        lines.append(f"### 🎯 {cat_name} ({len(cat_items)} 則)")
        lines.append("")
        for idx, item in enumerate(cat_items, 1):
            note_str = f" *（備註：{item['notes']}）*" if item.get('notes') else ""
            lines.append(f"**{idx}. {item['front']}**  ")
            lines.append(f"- 🇹🇼 **中文**：{item['back']}{note_str}  ")
            lines.append(f"- 🏷️ **類型**：`{item['type']}` | 🆔 `{item['id']}`  ")
            lines.append("")
            
    lines.extend([
        "---",
        "",
        "## 第三部分：核心單字速查",
        "",
        "| 編號 | 語言對 | 原文 | 譯文釋義 | 主題 | 掌握度 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ])
    
    words = [x for x in items if x["type"] == "word"]
    for w in words:
        lines.append(f"| `{w['id']}` | {w['lang_badge']} | **{w['front']}** | {w['back']} | {w['category']} | `{w['mastery']}` |")
        
    lines.extend([
        "",
        "---",
        "",
        "## 第四部分：實用長句與商業分析段落",
        ""
    ])
    
    sentences = [x for x in items if x["type"] == "sentence"]
    for s in sentences:
        lines.append(f"#### 📌 [{s['id']}] {s['lang_badge']} · {s['category']}")
        lines.append("```text")
        lines.append(s['front'])
        lines.append("```")
        lines.append(f"> 💡 **譯文解析**：{s['back']}")
        if s.get('notes'):
            lines.append(f"> 📝 **筆記**：{s['notes']}")
        lines.append("")
        
    with open(MD_OUTPUT, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
        
    print(f"📖 學習手冊已生成: {MD_OUTPUT.name}")

def generate_interactive_html(items):
    """
    生成高質感自包含互動學習網頁 (index.html)
    具備：
    1. 🇫🇷 法語專屬篩選與辨別標籤（法翻英、英翻法、法翻中）
    2. 多國母語語音發音（法文自動切換法文發音 fr-FR，英文切換英文發音 en-US）
    3. 3D 翻牌 220ms 疾速響應與主題分類篩選
    4. 獨立欄位顯示開關 (Display Toggles)
    5. 自我評量測驗 (Quiz) 與 力導向關係圖譜 (Canvas)
    """
    items_json = json.dumps(items, ensure_ascii=False)
    
    total_count = len(items)
    french_count = len([x for x in items if x["is_french"]])
    en_zh_count = len([x for x in items if x["lang_group"] == "en-zh"])
    fr_en_count = len([x for x in items if x["lang_group"] == "fr-en"])
    fr_zh_count = len([x for x in items if x["lang_group"] == "fr-zh"])
    
    word_count = len([x for x in items if x["type"] == "word"])
    phrase_count = len([x for x in items if x["type"] == "phrase"])
    sentence_count = len([x for x in items if x["type"] == "sentence"])
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Google 翻譯詞庫互動學習卡牌系統 | G-Translate Learning Hub</title>
  
  <!-- 立即初始化主題，防止畫面閃爍 -->
  <script>
    (function() {{
      const saved = localStorage.getItem('gt_theme_pref_v1');
      if (saved === 'light') {{
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light', 'light-mode');
      }} else {{
        document.documentElement.classList.remove('light', 'light-mode');
        document.documentElement.classList.add('dark');
      }}
    }})();
  </script>

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            brand: {{
              50: '#f0fdf4',
              100: '#dcfce7',
              500: '#22c55e',
              600: '#16a34a',
              700: '#15803d',
              900: '#14532d',
            }}
          }}
        }}
      }}
    }}
  </script>

  <style>
    /* CSS 變數系統：暗黑與明亮模式 (參考「工作的管見」高質感標準) */
    :root {{
      --bg-body: #020617;
      --bg-panel: rgba(15, 23, 42, 0.75);
      --bg-card: #0f172a;
      --bg-subtle: #1e293b;
      --text-main: #f8fafc;
      --text-sub: #94a3b8;
      --border-panel: rgba(255, 255, 255, 0.08);
      --border-sub: #334155;
      --canvas-bg: #020617;
      --canvas-text: #94a3b8;
      --canvas-line: rgba(100, 116, 139, 0.25);
    }}

    html.light, html.light-mode {{
      --bg-body: #f8fafc;
      --bg-panel: rgba(255, 255, 255, 0.9);
      --bg-card: #ffffff;
      --bg-subtle: #f1f5f9;
      --text-main: #0f172a;
      --text-sub: #475569;
      --border-panel: rgba(0, 0, 0, 0.08);
      --border-sub: #cbd5e1;
      --canvas-bg: #f8fafc;
      --canvas-text: #334155;
      --canvas-line: rgba(148, 163, 184, 0.4);
    }}

    body {{
      background-color: var(--bg-body);
      color: var(--text-main);
      transition: background-color 0.25s ease, color 0.25s ease;
    }}

    .glass-panel {{
      background: var(--bg-panel);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-panel);
    }}

    /* 3D 翻牌專用樣式 - 220ms 疾速翻牌體驗 */
    .perspective-1000 {{
      perspective: 1000px;
    }}
    .transform-style-3d {{
      transform-style: preserve-3d;
      transition: transform 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
      will-change: transform;
    }}
    .backface-hidden {{
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
    }}
    .rotate-y-180 {{
      transform: rotateY(180deg);
    }}

    /* 極速高效遮蓋 CSS 規則 (零延遲) */
    body.hide-en .field-en {{
      opacity: 0 !important;
      filter: blur(5px) !important;
      user-select: none !important;
    }}
    body.hide-zh .field-zh {{
      opacity: 0 !important;
      filter: blur(5px) !important;
      user-select: none !important;
    }}
    body.hide-tag .field-tag {{
      display: none !important;
    }}
    body.hide-notes .field-notes {{
      display: none !important;
    }}

    /* 平滑捲軸 */
    ::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    ::-webkit-scrollbar-track {{
      background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
      background: rgba(156, 163, 175, 0.4);
      border-radius: 9999px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: rgba(156, 163, 175, 0.7);
    }}
  </style>
</head>
<body class="min-h-screen font-sans antialiased selection:bg-brand-500 selection:text-white">

  <!-- 頂部導航與標頭 -->
  <header class="sticky top-0 z-40 glass-panel border-b border-slate-200 dark:border-slate-800/80 shadow-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
      
      <!-- 標題與數據徽章 -->
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-white shadow-md shadow-emerald-500/20 text-xl font-bold">
          GT
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="text-lg font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              Google 翻譯多語學習卡牌
            </h1>
            <span class="px-2 py-0.5 text-xs rounded-full font-medium bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30">
              v1.2 多語系
            </span>
          </div>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            總收錄 <span id="stat-total" class="font-semibold text-emerald-600 dark:text-emerald-400">{total_count}</span> 筆（🇬🇧 英中 {en_zh_count} · 🇫🇷 法語對翻 {french_count}）
          </p>
        </div>
      </div>

      <!-- 視角切換器 (4 大檢視模式) -->
      <div class="flex items-center bg-slate-200/80 dark:bg-slate-900/90 p-1 rounded-xl border border-slate-300 dark:border-slate-700/60 shadow-inner">
        <button id="tab-flashcard" onclick="switchTab('flashcard')" class="tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 bg-emerald-600 dark:bg-emerald-500 text-white shadow-md">
          <span>📇</span> 3D 卡牌
        </button>
        <button id="tab-list" onclick="switchTab('list')" class="tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-300/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800">
          <span>📋</span> 詞庫清單
        </button>
        <button id="tab-quiz" onclick="switchTab('quiz')" class="tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-300/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800">
          <span>✍️</span> 自我測驗
        </button>
        <button id="tab-graph" onclick="switchTab('graph')" class="tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-300/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800">
          <span>🕸️</span> 關係圖譜
        </button>
        <button id="tab-help" onclick="switchTab('help')" class="tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-300/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800">
          <span>📖</span> 使用說明
        </button>
      </div>

      <!-- 工具按鈕：發音語速、深淺色切換 -->
      <div class="flex items-center space-x-2.5">
        <div class="flex items-center text-xs text-slate-600 dark:text-slate-400 bg-slate-200/80 dark:bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700/60">
          <span class="mr-1.5">🔊 語速</span>
          <select id="tts-rate" onchange="updateTtsRate(this.value)" class="bg-transparent text-emerald-600 dark:text-emerald-400 font-semibold focus:outline-none cursor-pointer">
            <option value="0.8">0.8x 慢速</option>
            <option value="1.0" selected>1.0x 標準</option>
            <option value="1.2">1.2x 快速</option>
          </select>
        </div>
        
        <!-- 明亮/暗黑模式切換按鈕 -->
        <button onclick="toggleTheme()" id="theme-btn" class="p-2 rounded-lg bg-slate-200/80 hover:bg-slate-300 dark:bg-slate-900/80 dark:hover:bg-slate-800 text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white border border-slate-300 dark:border-slate-700/60 transition-colors" title="切換深淺色主題 (Dark / Light)">
          <span id="theme-icon">🌙</span>
        </button>
      </div>

    </div>

    <!-- 獨立欄位顯示開關 (Display Toggles) -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 border-t border-slate-200 dark:border-slate-800/60 flex flex-wrap items-center justify-between gap-3 text-xs">
      <div class="flex items-center gap-2">
        <span class="text-slate-500 dark:text-slate-400 font-medium">欄位遮蓋開關：</span>
        <button onclick="toggleField('en')" id="toggle-en" class="toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
          🔤 正面原文
        </button>
        <button onclick="toggleField('zh')" id="toggle-zh" class="toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
          🀄 背面釋義
        </button>
        <button onclick="toggleField('tag')" id="toggle-tag" class="toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
          🏷️ 語系/分類標籤
        </button>
        <button onclick="toggleField('notes')" id="toggle-notes" class="toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
          📝 備註例句
        </button>
      </div>

      <div class="flex items-center gap-2">
        <span class="text-slate-500">情境一鍵切換：</span>
        <button onclick="setScenario('all')" class="text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-white underline">全部顯示</button>
        <span class="text-slate-400 dark:text-slate-700">|</span>
        <button onclick="setScenario('hide-zh')" class="text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 underline">遮背面 (測理解)</button>
        <span class="text-slate-400 dark:text-slate-700">|</span>
        <button onclick="setScenario('hide-en')" class="text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 underline">遮正面 (默背原文)</button>
      </div>
    </div>
  </header>

  <!-- 主內容容器 -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">

    <!-- ======================================================== -->
    <!-- 視角一：📇 3D 翻轉卡牌抽測模式 (Flashcards) -->
    <!-- ======================================================== -->
    <section id="view-flashcard" class="space-y-6">
      
      <!-- 卡牌操作與進度條 -->
      <div class="max-w-2xl mx-auto flex items-center justify-between text-sm text-slate-600 dark:text-slate-400">
        <div class="flex items-center gap-2">
          <span>進度：</span>
          <span id="fc-index" class="font-bold text-slate-900 dark:text-white text-base">1</span> / <span id="fc-total">100</span>
        </div>
        
        <!-- 多維篩選列：語系、分類、類型、掌握度 -->
        <div class="flex items-center flex-wrap gap-2">
          <!-- 語言對篩選 (法語專屬選擇器) -->
          <select id="fc-filter-lang" onchange="onFlashcardFilterChange()" class="bg-white dark:bg-slate-900 border border-blue-500/50 dark:border-blue-400/50 text-blue-700 dark:text-blue-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none font-bold">
            <option value="all">🌐 全部語系 ({total_count})</option>
            <option value="en-zh">🇬🇧⇄🇹🇼 英語 ⇄ 中文 ({en_zh_count})</option>
            <option value="fr-all">🇫🇷 所有法語對翻 ({french_count})</option>
            <option value="fr-en">　├ 🇫🇷⇄🇬🇧 法語 ⇄ 英語 ({fr_en_count})</option>
            <option value="fr-zh">　└ 🇫🇷⇄🇹🇼 法語 ⇄ 中文 ({fr_zh_count})</option>
          </select>

          <!-- 詞彙分類主題篩選 -->
          <select id="fc-filter-cat" onchange="onFlashcardFilterChange()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none font-medium">
            <option value="all">所有主題 (全部)</option>
            <option value="商業財務">商業財務</option>
            <option value="科技半導體">科技半導體</option>
            <option value="職場管理">職場管理</option>
            <option value="生活哲思">生活哲思</option>
            <option value="實用表達">實用表達</option>
          </select>

          <!-- 類型篩選 (單字/片語/句型) -->
          <select id="fc-filter-type" onchange="onFlashcardFilterChange()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none">
            <option value="all">所有類型</option>
            <option value="word">單字 (Word)</option>
            <option value="phrase">片語 (Phrase)</option>
            <option value="sentence">長句 (Sentence)</option>
          </select>

          <!-- 掌握度篩選 -->
          <select id="fc-filter-mastery" onchange="onFlashcardFilterChange()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none">
            <option value="all">掌握狀態</option>
            <option value="unlearned">🔴 困難</option>
            <option value="learning">🟡 學習中</option>
            <option value="mastered">🟢 已精熟</option>
          </select>

          <button onclick="shuffleFlashcards()" class="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs rounded-lg border border-slate-300 dark:border-slate-700 flex items-center gap-1 transition active:scale-95" title="隨機洗牌">
            🎲 抽卡
          </button>
        </div>
      </div>

      <!-- 進度條 -->
      <div class="max-w-2xl mx-auto w-full bg-slate-200 dark:bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-300 dark:border-slate-800">
        <div id="fc-progress-bar" class="bg-gradient-to-r from-emerald-500 to-teal-400 h-full transition-all duration-300" style="width: 1%;"></div>
      </div>

      <!-- 3D 翻轉卡片本體 (自適應高寬與捲動保護) -->
      <div class="max-w-2xl mx-auto min-h-[400px] h-[430px] sm:h-[410px] perspective-1000 cursor-pointer select-none" onclick="flipCard()">
        <div id="card-inner" class="relative w-full h-full transform-style-3d shadow-xl rounded-2xl">
          
          <!-- 卡牌正面 (原文面) -->
          <div class="absolute inset-0 w-full h-full rounded-2xl p-6 sm:p-8 flex flex-col justify-between backface-hidden bg-white dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700/60 shadow-lg overflow-hidden">
            <div class="flex items-center justify-between shrink-0">
              <div class="flex items-center gap-2 field-tag">
                <!-- 語言對標籤 (清晰辨別法語/英語) -->
                <span id="fc-lang-badge" class="px-2.5 py-1 text-xs rounded-md font-bold border shadow-sm">
                  🇫🇷 法文 ➔ 🇬🇧 英文
                </span>
                <span id="fc-type-badge" class="px-2 py-0.5 text-[11px] rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 uppercase font-semibold">
                  Phrase
                </span>
                <span id="fc-cat-badge" class="px-2 py-0.5 text-[11px] rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  實用表達
                </span>
              </div>
              <button onclick="event.stopPropagation(); playFrontAudio()" class="w-10 h-10 rounded-full bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center transition shadow-sm" title="朗讀正面母語發音 (快捷鍵: P)">
                🔊
              </button>
            </div>

            <!-- 正面文字內容：自適應滾動保護與動態字級 -->
            <div class="my-auto px-2 overflow-y-auto max-h-[250px] w-full flex flex-col items-center justify-center">
              <div id="fc-front-lang-hint" class="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2 shrink-0">
                [🇫🇷 法文原文]
              </div>
              <div class="w-full flex justify-center">
                <h2 id="fc-front-text" class="field-en tracking-tight break-words whitespace-pre-line transition-all">
                  donner de la confiture aux cochons
                </h2>
              </div>
              <div id="fc-hint" class="text-xs text-slate-400 mt-3 shrink-0">
                （點擊卡牌或按空格鍵翻轉查看釋義）
              </div>
            </div>

            <!-- 底部提示 -->
            <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-800/80 pt-3 shrink-0">
              <span>快捷鍵：Space 翻牌 | ← → 切換卡片</span>
              <span id="fc-mastery-tag" class="text-amber-500 dark:text-amber-400 font-semibold">🟡 學習中</span>
            </div>
          </div>

          <!-- 卡牌背面 (釋義與說明面) -->
          <div class="absolute inset-0 w-full h-full rounded-2xl p-6 sm:p-8 flex flex-col justify-between backface-hidden rotate-y-180 bg-slate-50 dark:bg-slate-900/95 border border-emerald-500/40 shadow-lg overflow-hidden">
            <div class="flex items-center justify-between shrink-0">
              <span id="fc-back-lang-hint" class="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                [🇬🇧 英文釋義]
              </span>
              <button onclick="event.stopPropagation(); playBackAudio()" class="w-9 h-9 rounded-full bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 flex items-center justify-center transition" title="朗讀背面發音">
                🔊
              </button>
            </div>

            <!-- 背面中文/英文/法文釋義與例句內容 -->
            <div class="my-auto px-2 overflow-y-auto max-h-[250px] w-full">
              <div class="w-full flex justify-center">
                <h3 id="fc-back-text" class="field-zh text-emerald-700 dark:text-emerald-300 leading-relaxed break-words whitespace-pre-line transition-all">
                  give jam to the pigs.
                </h3>
              </div>
              <div id="fc-notes-container" class="field-notes mt-3 p-3 rounded-xl bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/50 text-xs text-slate-700 dark:text-slate-300 shadow-sm text-left">
                <p id="fc-notes" class="leading-relaxed whitespace-pre-line">
                  備註與例句解析
                </p>
              </div>
            </div>

            <div class="text-center text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-800/80 pt-3 shrink-0">
              點擊再次翻轉回正面
            </div>
          </div>

        </div>
      </div>

      <!-- 下方控制按鈕區 -->
      <div class="max-w-2xl mx-auto flex flex-wrap items-center justify-between gap-4 pt-2">
        <button onclick="prevCard()" class="px-5 py-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl font-medium border border-slate-300 dark:border-slate-700 transition flex items-center gap-2">
          <span>←</span> 上一張
        </button>

        <!-- 掌握度快速標記按鈕 (1, 2, 3) -->
        <div class="flex items-center gap-2">
          <button onclick="setMastery('unlearned')" class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-500/20 hover:bg-rose-500/30 text-rose-700 dark:text-rose-300 border border-rose-500/30 transition flex items-center gap-1" title="快速鍵: 1">
            🔴 困難 (1)
          </button>
          <button onclick="setMastery('learning')" class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-amber-500/20 hover:bg-amber-500/30 text-amber-700 dark:text-amber-300 border border-amber-500/30 transition flex items-center gap-1" title="快速鍵: 2">
            🟡 學習中 (2)
          </button>
          <button onclick="setMastery('mastered')" class="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 transition flex items-center gap-1" title="快速鍵: 3">
            🟢 已掌握 (3)
          </button>
        </div>

        <!-- 下一張與自動播放按鈕組 -->
        <div class="flex items-center flex-wrap gap-2">
          <!-- 播放模式切換：雙語模式 vs 英文模式 -->
          <div class="flex items-center text-xs bg-slate-200/80 dark:bg-slate-800/80 rounded-xl p-1 border border-slate-300 dark:border-slate-700/60 shadow-inner">
            <span class="pl-2 pr-1 text-slate-500 dark:text-slate-400 font-medium">播報:</span>
            <select id="autoplay-mode-select" onchange="setAutoPlayMode(this.value)" class="bg-transparent text-slate-700 dark:text-slate-200 font-bold focus:outline-none cursor-pointer py-1.5 pr-2">
              <option value="bilingual">🌐 雙語模式 (外語+中文)</option>
              <option value="foreign_only">🔤 英文/純外語模式</option>
            </select>
          </div>

          <button onclick="nextCard()" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-medium shadow-lg shadow-emerald-600/30 transition flex items-center gap-2">
            下一張 <span>→</span>
          </button>
          <button id="btn-autoplay" onclick="toggleAutoPlay()" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium shadow-lg shadow-indigo-600/30 transition flex items-center gap-1.5" title="自動巡迴播放：依據選擇模式自動朗讀與切換 (快捷鍵: A)">
            <span id="autoplay-icon">▶</span>
            <span id="autoplay-text">自動播放</span>
          </button>
        </div>
      </div>

      <!-- 3D 卡牌下方更新時間提示 -->
      <div class="max-w-2xl mx-auto text-center text-xs text-slate-400 dark:text-slate-500 pt-1 pb-2">
        🕒 詞庫最後更新日期時間：<span class="font-medium text-slate-600 dark:text-slate-300">{now_str}</span>
      </div>

    </section>

    <!-- ======================================================== -->
    <!-- 視角二：📋 詞庫清單模式 (Vocabulary List) -->
    <!-- ======================================================== -->
    <section id="view-list" class="space-y-4 hidden">
      
      <!-- 篩選列 -->
      <div class="glass-panel p-4 rounded-2xl border border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <!-- 搜尋輸入框 -->
        <div class="relative flex-1 min-w-[240px]">
          <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">🔍</span>
          <input type="text" id="list-search" oninput="filterList()" placeholder="搜尋原文、釋義、例句或語系..." class="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700/80 rounded-xl text-sm text-slate-900 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-emerald-500">
        </div>

        <!-- 語言對、分類與類型篩選下拉 -->
        <div class="flex items-center flex-wrap gap-2.5 text-xs">
          <select id="filter-lang" onchange="filterList()" class="bg-white dark:bg-slate-900 border border-blue-500/50 dark:border-blue-400/50 text-blue-700 dark:text-blue-300 rounded-xl px-3 py-2 focus:outline-none font-bold">
            <option value="all">🌐 全部語系 ({total_count})</option>
            <option value="en-zh">🇬🇧⇄🇹🇼 英語 ⇄ 中文 ({en_zh_count})</option>
            <option value="fr-all">🇫🇷 所有法語對翻 ({french_count})</option>
            <option value="fr-en">　├ 🇫🇷⇄🇬🇧 法語 ⇄ 英語 ({fr_en_count})</option>
            <option value="fr-zh">　└ 🇫🇷⇄🇹🇼 法語 ⇄ 中文 ({fr_zh_count})</option>
          </select>

          <select id="filter-cat" onchange="filterList()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl px-3 py-2 focus:outline-none">
            <option value="all">所有主題</option>
            <option value="商業財務">商業財務</option>
            <option value="科技半導體">科技半導體</option>
            <option value="職場管理">職場管理</option>
            <option value="生活哲思">生活哲思</option>
            <option value="實用表達">實用表達</option>
          </select>

          <select id="filter-type" onchange="filterList()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl px-3 py-2 focus:outline-none">
            <option value="all">所有類型</option>
            <option value="word">單字 (Word)</option>
            <option value="phrase">片語 (Phrase)</option>
            <option value="sentence">長句 (Sentence)</option>
          </select>

          <select id="filter-mastery" onchange="filterList()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl px-3 py-2 focus:outline-none">
            <option value="all">掌握狀態</option>
            <option value="unlearned">🔴 困難</option>
            <option value="learning">🟡 學習中</option>
            <option value="mastered">🟢 已掌握</option>
          </select>

          <select id="sort-by" onchange="filterList()" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl px-3 py-2 focus:outline-none">
            <option value="default">預設順序</option>
            <option value="az">A-Z 排序</option>
            <option value="za">Z-A 排序</option>
          </select>
        </div>
      </div>

      <!-- 結果統計 -->
      <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 px-1">
        <div>顯示 <span id="list-count" class="font-bold text-emerald-600 dark:text-emerald-400">0</span> 筆結果</div>
      </div>

      <!-- 列表主體容器 -->
      <div id="list-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- JS 動態渲染卡片項目 -->
      </div>

    </section>

    <!-- ======================================================== -->
    <!-- 視角三：✍️ 自我測驗模式 (Interactive Quiz) -->
    <!-- ======================================================== -->
    <section id="view-quiz" class="max-w-2xl mx-auto space-y-6 hidden">
      
      <div class="glass-panel p-6 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-6 bg-white dark:bg-slate-900/90 shadow-md">
        
        <!-- 測驗頂部狀態列 -->
        <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
          <div>
            <span class="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">多語自我評量測驗</span>
            <h3 class="text-lg font-bold text-slate-900 dark:text-white mt-0.5">第 <span id="quiz-curr-q">1</span> 題 / 共 <span id="quiz-total-q">10</span> 題</h3>
          </div>
          <div class="text-right">
            <div class="text-xs text-slate-500 dark:text-slate-400">目前得分</div>
            <div class="text-xl font-extrabold text-emerald-600 dark:text-emerald-400"><span id="quiz-score">0</span> 分</div>
          </div>
        </div>

        <!-- 題幹區 -->
        <div class="text-center py-4">
          <div class="inline-block px-3 py-1 rounded-full text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 mb-3 border border-slate-200 dark:border-slate-700" id="quiz-question-type">
            🇫🇷 法文 ➔ 🇬🇧 英文選擇題
          </div>
          <h2 id="quiz-prompt" class="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Question Prompt
          </h2>
          <button id="quiz-audio-btn" onclick="playQuizPromptAudio()" class="mt-3 px-3.5 py-1.5 rounded-full bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs text-slate-700 dark:text-slate-300 inline-flex items-center gap-1.5 transition font-medium">
            🔊 播放母語發音
          </button>
        </div>

        <!-- 四選一選項區 -->
        <div id="quiz-options" class="grid grid-cols-1 gap-3">
          <!-- JS 動態生成選項 -->
        </div>

        <!-- 答題回饋提示 -->
        <div id="quiz-feedback" class="p-4 rounded-xl text-sm hidden font-medium"></div>

        <!-- 下一題按鈕 -->
        <div class="flex justify-end">
          <button id="quiz-next-btn" onclick="nextQuizQuestion()" class="hidden px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl transition shadow-lg shadow-emerald-600/30">
            下一題 →
          </button>
        </div>

      </div>

      <!-- 錯題回顧紀錄 -->
      <div id="quiz-review-section" class="hidden glass-panel p-6 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-4 bg-white dark:bg-slate-900/90 shadow-md">
        <h4 class="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <span>📝</span> 測驗總結與錯題加強
        </h4>
        <div id="quiz-mistakes-list" class="space-y-2 text-sm text-slate-700 dark:text-slate-300">
          <!-- 錯題列表 -->
        </div>
        <button onclick="startNewQuiz()" class="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl transition shadow-md">
          🔄 重新展開 10 題新測驗
        </button>
      </div>

    </section>

    <!-- ======================================================== -->
    <!-- 視角四：🕸️ 詞彙知識網絡圖 (Canvas Force Graph) -->
    <!-- ======================================================== -->
    <section id="view-graph" class="space-y-4 hidden">
      <div class="glass-panel p-4 rounded-2xl border border-slate-200 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 class="font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span>🕸️</span> 詞彙分類與語系關聯力導向網絡
          </h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            基於原生 HTML5 Canvas 物理引擎：包含 5 大主題 Hub 與 🇫🇷 法語對翻樞紐。支援拖曳、滾輪縮放與點擊抽屜檢視。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="resetGraphView()" class="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs rounded-lg border border-slate-300 dark:border-slate-700 transition">
            🎯 重置視角
          </button>
          <button onclick="toggleGraphSimulation()" id="btn-graph-sim" class="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs rounded-lg border border-slate-300 dark:border-slate-700 transition">
            ⏸️ 暫停物理模擬
          </button>
        </div>
      </div>

      <!-- Canvas 畫布主體 -->
      <div class="relative w-full h-[620px] rounded-2xl overflow-hidden glass-panel border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
        <canvas id="graph-canvas" class="w-full h-full cursor-grab active:cursor-grabbing"></canvas>
        
        <div class="absolute bottom-3 left-3 px-3 py-2 rounded-lg bg-white/80 dark:bg-slate-900/80 backdrop-blur border border-slate-200 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400 pointer-events-none">
          💡 滑鼠滾輪縮放 · 拖曳畫布平移 · 點擊節點查看詳情
        </div>
      </div>
    </section>

    <!-- ======================================================== -->
    <!-- 視角五：📖 使用手冊與系統說明 (Help & User Manual) -->
    <!-- ======================================================== -->
    <section id="view-help" class="space-y-6 hidden max-w-5xl mx-auto">
      
      <!-- 頂部引言橫幅 -->
      <div class="glass-panel p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
        <div class="absolute right-0 top-0 translate-x-8 -translate-y-8 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div class="flex items-center gap-3 mb-2">
          <span class="text-2xl">📖</span>
          <h2 class="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">系統使用說明與操作手冊</h2>
          <span class="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">User Manual</span>
        </div>
        <p class="text-sm text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
          歡迎使用 Google 翻譯詞庫互動學習系統！本系統將您在 Google 翻譯中標記星號儲存的單字與片語，自動轉化為具備 3D 抽認卡、多國語言母語語音、智慧分類與知識圖譜的現代化學習工具。
        </p>
      </div>

      <!-- 核心四大功能快速上手 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        
        <!-- 3D 卡牌 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2.5">
          <div class="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold text-base">
            <span>📇</span> 3D 翻牌抽測模式
          </div>
          <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            模擬實體抽認卡（Flashcards），正面為外語原文，背面為中文釋義。點擊卡牌本體或按 <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono text-[10px]">Space</kbd> 即可在 0.2 秒內平滑 3D 翻轉。
          </p>
          <ul class="text-xs text-slate-500 dark:text-slate-400 list-disc list-inside space-y-1">
            <li>支援 🔊 正反面獨立母語發音（英/法/中自動切換）。</li>
            <li>支援 ▶ 自動播放功能：可自由選擇<strong>「🌐 雙語模式」</strong>（外語 ➔ 自動翻牌 ➔ 中文釋義）或<strong>「🔤 英文/純外語模式」</strong>（純英文/法語沉浸聽力，不朗讀中文）。</li>
            <li>可手動標記 🔴 困難、🟡 學習中、🟢 已精熟。</li>
            <li>點擊 🎲 抽卡 可將現有篩選範圍內的卡片隨機洗牌。</li>
          </ul>
        </div>

        <!-- 詞庫清單 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2.5">
          <div class="flex items-center gap-2 text-blue-600 dark:text-blue-400 font-bold text-base">
            <span>📋</span> 詞庫清單與搜尋
          </div>
          <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            以結構化表格檢視所有已收錄條目，支援毫秒級全域模糊搜尋與多維條件篩選。
          </p>
          <ul class="text-xs text-slate-500 dark:text-slate-400 list-disc list-inside space-y-1">
            <li>輸入關鍵字即時比對原文、釋義或備註。</li>
            <li>可依語系（英中、法英、法中）、分類主題與掌握狀態篩選。</li>
            <li>點擊任一項目右側的 👁️ 按鈕可滑出側邊詳細資訊抽屜。</li>
          </ul>
        </div>

        <!-- 自我測驗 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2.5">
          <div class="flex items-center gap-2 text-purple-600 dark:text-purple-400 font-bold text-base">
            <span>✍️</span> 隨機自我測驗 (Quiz)
          </div>
          <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            隨機抽取 10 題進行四選一測驗，包含「外語選中文」與「中文選外語」雙向題型。
          </p>
          <ul class="text-xs text-slate-500 dark:text-slate-400 list-disc list-inside space-y-1">
            <li>即時反饋答對/答錯，並記錄錯題。</li>
            <li>完成 10 題後即時結算分數並列出租錯題清單方便針對性複習。</li>
          </ul>
        </div>

        <!-- 關係圖譜 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2.5">
          <div class="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-bold text-base">
            <span>🕸️</span> 知識網絡圖譜 (Graph)
          </div>
          <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            基於原生 Canvas 物理引擎的力導向網絡圖，直觀展現各單字與分類主題的聚類關係。
          </p>
          <ul class="text-xs text-slate-500 dark:text-slate-400 list-disc list-inside space-y-1">
            <li>滑鼠滾輪縮放、拖曳畫布自由平移探索。</li>
            <li>點擊任一單字節點直接開啟側邊欄檢視詳細釋義與發音。</li>
          </ul>
        </div>

      </div>

      <!-- 快捷鍵指南與欄位遮蓋開關 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        
        <!-- 鍵盤快捷鍵 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <h3 class="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
            <span>⌨️</span> 鍵盤快捷鍵一覽 (桌面版限定)
          </h3>
          <div class="space-y-2 text-xs">
            <div class="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span class="text-slate-600 dark:text-slate-400">翻轉卡牌正面 / 背面</span>
              <kbd class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono font-bold">Space</kbd>
            </div>
            <div class="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span class="text-slate-600 dark:text-slate-400">切換至上一張 / 下一張卡片</span>
              <div class="flex gap-1 font-mono font-bold">
                <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">←</kbd>
                <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">→</kbd>
              </div>
            </div>
            <div class="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span class="text-slate-600 dark:text-slate-400">播放當前卡面母語語音</span>
              <kbd class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono font-bold">P</kbd>
            </div>
            <div class="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span class="text-slate-600 dark:text-slate-400">啟動 / 停止卡牌自動巡航播放</span>
              <kbd class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 font-mono font-bold">A</kbd>
            </div>
            <div class="flex items-center justify-between py-1">
              <span class="text-slate-600 dark:text-slate-400">標記掌握度（困難 / 學習 / 精熟）</span>
              <div class="flex gap-1 font-mono font-bold">
                <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">1</kbd>
                <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">2</kbd>
                <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700">3</kbd>
              </div>
            </div>
          </div>
        </div>

        <!-- 記憶遮蓋練習情境 -->
        <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
          <h3 class="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
            <span>🎭</span> 欄位遮蓋情境 (主動回想練習)
          </h3>
          <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            透過頂部導航列下方的「欄位遮蓋開關」，可一鍵套用不同自測情境：
          </p>
          <div class="space-y-2 text-xs">
            <div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60">
              <span class="font-bold text-emerald-600 dark:text-emerald-400">遮背面（測理解）</span>
              <p class="text-slate-500 dark:text-slate-400 mt-0.5">隱藏中文翻譯，強迫自己看到英文/法文時在大腦中提取中文意思。</p>
            </div>
            <div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60">
              <span class="font-bold text-blue-600 dark:text-blue-400">遮正面（默背原文）</span>
              <p class="text-slate-500 dark:text-slate-400 mt-0.5">隱藏外語原文，看中文練習拼字或在心裡默唸正確外語單字。</p>
            </div>
          </div>
        </div>

      </div>

      <!-- 🇫🇷 法語專題與多語系說明 -->
      <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
            <span>🌐</span> 語系配對與法語對翻功能說明
          </h3>
          <span class="px-2 py-0.5 text-xs rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold border border-blue-500/30">
            收錄 105 筆法語
          </span>
        </div>
        <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          Google 翻譯匯出檔中若混雜了法語與英語，系統已自動為您精準拆分與辨識，絕不互相混淆：
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 text-xs space-y-1">
            <span class="font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1">🇫🇷 法語原生發音</span>
            <p class="text-slate-500 dark:text-slate-400">點擊法文單字時，自動呼叫瀏覽器原生 <code class="text-slate-700 dark:text-slate-300 font-mono">fr-FR</code> 法語語音引擎朗讀，保留道地法式腔調。</p>
          </div>
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 text-xs space-y-1">
            <span class="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">🇬🇧 英語標準發音</span>
            <p class="text-slate-500 dark:text-slate-400">英語單字調用 <code class="text-slate-700 dark:text-slate-300 font-mono">en-US</code> 發音，繁體中文調用 <code class="text-slate-700 dark:text-slate-300 font-mono">zh-TW</code> 發音。</p>
          </div>
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 text-xs space-y-1">
            <span class="font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1">🎯 專屬下拉篩選</span>
            <p class="text-slate-500 dark:text-slate-400">可一鍵切換「🇫🇷 所有法語對翻」、「🇫🇷⇄🇬🇧 法英對翻」或「🇬🇧⇄🇹🇼 英中對翻」。</p>
          </div>
        </div>
      </div>

      <!-- 📱 手機/平板安裝指南 (PWA體驗) -->
      <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <h3 class="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
          <span>📱</span> 如何安裝到手機 / 平板主畫面（宛如原生 App）
        </h3>
        <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          本系統已具備極速響應式設計，您可以直接將其加到行動裝置桌面，隨點即學：
        </p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 space-y-1.5">
            <div class="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span>🍎</span> iPhone / iPad (Safari)
            </div>
            <ol class="text-slate-500 dark:text-slate-400 list-decimal list-inside space-y-1">
              <li>以 Safari 開啟本線上網址。</li>
              <li>點選底部分享按鈕（方形帶向上箭頭 📤）。</li>
              <li>滑動選單並點擊 <strong>「加入主畫面 (Add to Home Screen)」</strong>。</li>
            </ol>
          </div>
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 space-y-1.5">
            <div class="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span>🤖</span> Android 手機 (Chrome / Edge)
            </div>
            <ol class="text-slate-500 dark:text-slate-400 list-decimal list-inside space-y-1">
              <li>以 Chrome 開啟本線上網址。</li>
              <li>點選右上角三點選單圖示 (⋮)。</li>
              <li>點擊 <strong>「加到主畫面」</strong> 或 <strong>「安裝應用程式」</strong>。</li>
            </ol>
          </div>
        </div>
      </div>

      <!-- 🔄 日後更新 CSV 與部署流程 -->
      <div class="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <h3 class="font-bold text-slate-900 dark:text-white text-sm flex items-center gap-2">
          <span>🔄</span> 詞庫更新與自動發布作業流程 (SOP)
        </h3>
        <p class="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          當您在 Google 翻譯下載了新的 CSV 詞庫檔案時，更新只需 3 步驟：
        </p>
        <div class="space-y-2 text-xs">
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 flex items-start gap-2.5">
            <span class="font-mono font-bold text-emerald-600 dark:text-emerald-400">Step 1</span>
            <div>
              <span class="font-semibold text-slate-800 dark:text-slate-200">放入新 CSV 檔案</span>
              <p class="text-slate-500 dark:text-slate-400">將新匯出的 CSV 覆蓋專案目錄下的 <code class="text-slate-700 dark:text-slate-300 font-mono">g_translate.csv.csv</code>。</p>
            </div>
          </div>
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 flex items-start gap-2.5">
            <span class="font-mono font-bold text-emerald-600 dark:text-emerald-400">Step 2</span>
            <div class="w-full">
              <span class="font-semibold text-slate-800 dark:text-slate-200">執行本地自動化更新腳本</span>
              <p class="text-slate-500 dark:text-slate-400 mb-1">系統將在 1 秒內自動完成去重、多語識別、分類歸納與網頁編譯：</p>
              <pre class="p-2 rounded bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto">python update_learning_app.py</pre>
            </div>
          </div>
          <div class="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 flex items-start gap-2.5">
            <span class="font-mono font-bold text-emerald-600 dark:text-emerald-400">Step 3</span>
            <div class="w-full">
              <span class="font-semibold text-slate-800 dark:text-slate-200">推送到 GitHub 自動發布</span>
              <p class="text-slate-500 dark:text-slate-400 mb-1">推送完成後，GitHub Pages 將在 30 秒內自動更新線上學習網頁：</p>
              <pre class="p-2 rounded bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto">git add .
git commit -m "更新詞庫與學習手冊"
git push</pre>
            </div>
          </div>
        </div>
      </div>

    </section>

  </main>

  <!-- 頁尾：更新時間與系統資訊 -->
  <footer class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 mt-12 border-t border-slate-200 dark:border-slate-800/80 text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
    <div class="flex items-center justify-center flex-wrap gap-2 sm:gap-4">
      <span class="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300">
        <span>🕒</span> 最後更新日期時間：<span class="text-emerald-600 dark:text-emerald-400 font-bold">{now_str}</span>
      </span>
      <span class="text-slate-300 dark:text-slate-700 hidden sm:inline">•</span>
      <span>總收錄 <strong>{total_count}</strong> 筆</span>
      <span class="text-slate-300 dark:text-slate-700 hidden sm:inline">•</span>
      <span>🇫🇷 法語對翻 {french_count} 筆</span>
      <span class="text-slate-300 dark:text-slate-700 hidden sm:inline">•</span>
      <span>🇬🇧 英語/繁中 {en_zh_count} 筆</span>
    </div>
    <p class="text-[11px] text-slate-400 dark:text-slate-500">
      Google 翻譯多語互動學習系統 · <a href="https://sinliongtoo.github.io/google-translate-learning/" target="_blank" class="hover:underline hover:text-emerald-500">GitHub Pages 線上版</a>
    </p>
  </footer>

  <!-- 滑出式單字詳情抽屜 (Side Drawer) -->
  <div id="detail-drawer" class="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl z-50 transform translate-x-full transition-transform duration-300 ease-in-out p-6 flex flex-col justify-between overflow-y-auto">
    <div>
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
        <span id="drawer-id" class="text-xs font-mono text-slate-500">ITEM #0001</span>
        <button onclick="closeDrawer()" class="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
          ✕
        </button>
      </div>

      <div class="py-6 space-y-4">
        <div class="flex items-center gap-2">
          <span id="drawer-lang-badge" class="px-2.5 py-1 text-xs rounded-md font-bold border">
            🇫🇷 法文 ➔ 🇬🇧 英文
          </span>
          <span id="drawer-cat" class="px-2.5 py-1 text-xs rounded-md bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold">商業財務</span>
          <span id="drawer-type" class="px-2.5 py-1 text-xs rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">Word</span>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <h2 id="drawer-front" class="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight">Word</h2>
            <button onclick="playDrawerFrontAudio()" class="w-9 h-9 rounded-full bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center transition" title="朗讀正面發音">
              🔊
            </button>
          </div>
          <span id="drawer-front-lang" class="text-xs text-slate-400">🇫🇷 法文原文</span>
        </div>

        <div class="pt-2">
          <div class="flex items-center justify-between">
            <label id="drawer-back-label" class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">釋義</label>
            <button onclick="playDrawerBackAudio()" class="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
              🔊 朗讀釋義
            </button>
          </div>
          <div id="drawer-back" class="text-lg font-bold text-emerald-700 dark:text-emerald-300 mt-1 leading-relaxed">釋義</div>
        </div>

        <div id="drawer-notes-box" class="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/50">
          <label class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">備註與例句</label>
          <p id="drawer-notes" class="text-sm text-slate-700 dark:text-slate-300 mt-1 leading-relaxed"></p>
        </div>
      </div>
    </div>

    <!-- 抽屜底部：掌握度設定 -->
    <div class="border-t border-slate-200 dark:border-slate-800 pt-4 flex items-center justify-between">
      <span class="text-xs text-slate-500 dark:text-slate-400">掌握度狀態：</span>
      <div class="flex items-center gap-1.5">
        <button onclick="setDrawerMastery('unlearned')" class="px-3 py-1.5 rounded-lg text-xs bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/30 font-medium">
          🔴 困難
        </button>
        <button onclick="setDrawerMastery('learning')" class="px-3 py-1.5 rounded-lg text-xs bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-medium">
          🟡 學習中
        </button>
        <button onclick="setDrawerMastery('mastered')" class="px-3 py-1.5 rounded-lg text-xs bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 font-medium">
          🟢 已掌握
        </button>
      </div>
    </div>
  </div>

  <!-- 資料腳本與核心邏輯 -->
  <script>
    const RAW_ITEMS = {items_json};
    
    // 儲存鍵名
    const STORAGE_KEY = 'gt_learning_progress_v1';
    const DISPLAY_KEY = 'gt_display_prefs_v1';
    const THEME_KEY = 'gt_theme_pref_v1';

    let userProgress = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
    let displayPrefs = JSON.parse(localStorage.getItem(DISPLAY_KEY) || JSON.stringify({{
      en: true,
      zh: true,
      tag: true,
      notes: true
    }}));

    let items = RAW_ITEMS.map(item => ({{
      ...item,
      mastery: userProgress[item.id] || item.mastery || 'learning'
    }}));

    // 狀態變數
    let activeTab = 'flashcard';
    let currentCardIndex = 0;
    let filteredCards = [...items];
    let isFlipped = false;
    let ttsRate = 1.0;
    let drawerActiveItem = null;

    // 測驗狀態
    let quizQuestions = [];
    let currentQuizIndex = 0;
    let quizScore = 0;
    let quizMistakes = [];

    // ==========================================
    // 主題切換與持久化 (Dark / Light Mode)
    // ==========================================
    function initTheme() {{
      const savedTheme = localStorage.getItem(THEME_KEY) || 'dark';
      applyTheme(savedTheme);
    }}

    function applyTheme(theme) {{
      const html = document.documentElement;
      const icon = document.getElementById('theme-icon');
      if (theme === 'light') {{
        html.classList.remove('dark');
        html.classList.add('light', 'light-mode');
        if (icon) icon.innerText = '☀️';
      }} else {{
        html.classList.remove('light', 'light-mode');
        html.classList.add('dark');
        if (icon) icon.innerText = '🌙';
      }}
      localStorage.setItem(THEME_KEY, theme);
      if (activeTab === 'list') filterList();
    }}

    function toggleTheme() {{
      const isDark = document.documentElement.classList.contains('dark');
      applyTheme(isDark ? 'light' : 'dark');
    }}

    // ==========================================
    // 獨立欄位顯示開關 (Display Toggles) - Body 級別極速響應
    // ==========================================
    function applyDisplayPrefs() {{
      const body = document.body;
      const toggles = [
        {{ key: 'en', bodyClass: 'hide-en', btn: 'toggle-en' }},
        {{ key: 'zh', bodyClass: 'hide-zh', btn: 'toggle-zh' }},
        {{ key: 'tag', bodyClass: 'hide-tag', btn: 'toggle-tag' }},
        {{ key: 'notes', bodyClass: 'hide-notes', btn: 'toggle-notes' }}
      ];

      toggles.forEach(t => {{
        const isVisible = displayPrefs[t.key];
        const btn = document.getElementById(t.btn);
        if (btn) {{
          if (isVisible) {{
            btn.className = "toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-emerald-500/40 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300";
          }} else {{
            btn.className = "toggle-pill px-2.5 py-1 rounded-full font-medium transition border border-slate-300 dark:border-slate-700 bg-slate-200 dark:bg-slate-800 text-slate-500 line-through";
          }}
        }}

        if (isVisible) {{
          body.classList.remove(t.bodyClass);
        }} else {{
          body.classList.add(t.bodyClass);
        }}
      }});

      localStorage.setItem(DISPLAY_KEY, JSON.stringify(displayPrefs));
    }}

    function toggleField(key) {{
      displayPrefs[key] = !displayPrefs[key];
      applyDisplayPrefs();
    }}

    function setScenario(type) {{
      if (type === 'all') {{
        displayPrefs = {{ en: true, zh: true, tag: true, notes: true }};
      }} else if (type === 'hide-zh') {{
        displayPrefs = {{ en: true, zh: false, tag: true, notes: false }};
      }} else if (type === 'hide-en') {{
        displayPrefs = {{ en: false, zh: true, tag: true, notes: true }};
      }}
      applyDisplayPrefs();
    }}

    // ==========================================
    // Web Speech API 真人多語發音 (支援法語 fr-FR、英語 en-US、中文 zh-TW)
    // ==========================================
    function playAudio(text, lang = 'en-US', onEnd = null) {{
      if (!('speechSynthesis' in window)) {{
        if (onEnd) setTimeout(onEnd, 1200);
        return;
      }}
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = ttsRate;
      if (onEnd) {{
        let called = false;
        const callbackOnce = () => {{
          if (!called) {{
            called = true;
            onEnd();
          }}
        }};
        utterance.onend = callbackOnce;
        utterance.onerror = callbackOnce;
        // 防呆看門狗計時器，避免特定瀏覽器丟失 onend 事件卡住
        const timeoutMs = Math.max(3000, (text.length * 150) / ttsRate);
        setTimeout(callbackOnce, timeoutMs);
      }}
      window.speechSynthesis.speak(utterance);
    }}

    function updateTtsRate(rate) {{
      ttsRate = parseFloat(rate);
    }}

    function playFrontAudio() {{
      const card = filteredCards[currentCardIndex];
      if (card) playAudio(card.front, card.front_voice || 'en-US');
    }}

    function playBackAudio() {{
      const card = filteredCards[currentCardIndex];
      if (card) playAudio(card.back, card.back_voice || 'zh-TW');
    }}

    // ==========================================
    // 視角切換 (Tabs)
    // ==========================================
    function switchTab(tabId) {{
      if (tabId !== 'flashcard' && isAutoPlaying) {{
        stopAutoPlay();
      }}
      activeTab = tabId;
      ['flashcard', 'list', 'quiz', 'graph', 'help'].forEach(id => {{
        const btn = document.getElementById('tab-' + id);
        const view = document.getElementById('view-' + id);
        if (id === tabId) {{
          btn.className = "tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 bg-emerald-600 dark:bg-emerald-500 text-white shadow-md";
          view.classList.remove('hidden');
        }} else {{
          btn.className = "tab-btn px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-300/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800";
          view.classList.add('hidden');
        }}
      }});

      if (tabId === 'list') filterList();
      if (tabId === 'quiz' && quizQuestions.length === 0) startNewQuiz();
      if (tabId === 'graph') initGraphCanvas();
    }}

    // ==========================================
    // 3D 翻轉卡牌模式 (Flashcards - 極速響應版，支援語系篩選)
    // ==========================================
    function onFlashcardFilterChange() {{
      if (isAutoPlaying) stopAutoPlay();
      const langFilter = document.getElementById('fc-filter-lang') ? document.getElementById('fc-filter-lang').value : 'all';
      const catFilter = document.getElementById('fc-filter-cat') ? document.getElementById('fc-filter-cat').value : 'all';
      const typeFilter = document.getElementById('fc-filter-type') ? document.getElementById('fc-filter-type').value : 'all';
      const masteryFilter = document.getElementById('fc-filter-mastery') ? document.getElementById('fc-filter-mastery').value : 'all';

      filteredCards = items.filter(card => {{
        // 語言篩選
        if (langFilter === 'en-zh' && card.lang_group !== 'en-zh') return false;
        if (langFilter === 'fr-all' && !card.is_french) return false;
        if (langFilter === 'fr-en' && card.lang_group !== 'fr-en') return false;
        if (langFilter === 'fr-zh' && card.lang_group !== 'fr-zh') return false;

        if (catFilter !== 'all' && card.category !== catFilter) return false;
        if (typeFilter !== 'all' && card.type !== typeFilter) return false;
        if (masteryFilter !== 'all' && card.mastery !== masteryFilter) return false;
        return true;
      }});

      if (filteredCards.length === 0) {{
        filteredCards = items;
      }}
      currentCardIndex = 0;
      updateFlashcardUI();
    }}

    function shuffleFlashcards() {{
      for (let i = filteredCards.length - 1; i > 0; i--) {{
        const j = Math.floor(Math.random() * (i + 1));
        [filteredCards[i], filteredCards[j]] = [filteredCards[j], filteredCards[i]];
      }}
      currentCardIndex = 0;
      updateFlashcardUI();
    }}

    function flipCard() {{
      const inner = document.getElementById('card-inner');
      isFlipped = !isFlipped;
      if (isFlipped) {{
        inner.classList.add('rotate-y-180');
      }} else {{
        inner.classList.remove('rotate-y-180');
      }}
    }}

    function updateFlashcardUI() {{
      if (filteredCards.length === 0) return;
      const card = filteredCards[currentCardIndex];
      const inner = document.getElementById('card-inner');
      
      // 切換卡片時瞬間重設為正面 (無反向動畫等待)
      if (isFlipped) {{
        inner.style.transition = 'none';
        inner.classList.remove('rotate-y-180');
        isFlipped = false;
        void inner.offsetHeight;
        inner.style.transition = '';
      }}

      document.getElementById('fc-index').innerText = currentCardIndex + 1;
      document.getElementById('fc-total').innerText = filteredCards.length;
      
      const pct = Math.round(((currentCardIndex + 1) / filteredCards.length) * 100);
      document.getElementById('fc-progress-bar').style.width = pct + '%';

      // 語言對徽章與辨別標籤
      const langBadge = document.getElementById('fc-lang-badge');
      langBadge.innerText = card.lang_badge;
      if (card.is_french) {{
        langBadge.className = "px-2.5 py-1 text-xs rounded-md font-bold bg-blue-500/15 text-blue-700 dark:text-blue-300 border border-blue-500/40 shadow-sm";
      }} else {{
        langBadge.className = "px-2.5 py-1 text-xs rounded-md font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-sm";
      }}

      document.getElementById('fc-front-lang-hint').innerText = `[${{card.front_flag}} ${{card.front_lang}}原文]`;
      document.getElementById('fc-back-lang-hint').innerText = `[${{card.back_flag}} ${{card.back_lang}}釋義]`;

      // 動態自適應字級演算法 (防止長文或多行列表破版超出卡牌)
      const frontText = card.front || "";
      const frontLen = frontText.length;
      const frontLines = frontText.split('\n').length;
      const frontEl = document.getElementById('fc-front-text');
      frontEl.innerText = frontText;

      if (frontLines >= 6 || frontLen > 140) {{
        frontEl.className = "field-en text-sm sm:text-base font-normal leading-relaxed text-slate-800 dark:text-slate-200 text-left w-full";
      }} else if (frontLines >= 3 || frontLen > 65) {{
        frontEl.className = "field-en text-base sm:text-lg font-medium leading-normal text-slate-900 dark:text-white text-center w-full";
      }} else if (frontLen > 30) {{
        frontEl.className = "field-en text-xl sm:text-2xl font-bold leading-snug text-slate-900 dark:text-white text-center w-full";
      }} else {{
        frontEl.className = "field-en text-2xl sm:text-3xl font-extrabold leading-snug text-slate-900 dark:text-white text-center w-full";
      }}

      // 背面文字同樣進行自適應縮放
      const backText = card.back || "";
      const backLen = backText.length;
      const backLines = backText.split('\n').length;
      const backEl = document.getElementById('fc-back-text');
      backEl.innerText = backText;

      if (backLines >= 6 || backLen > 140) {{
        backEl.className = "field-zh text-sm sm:text-base font-normal leading-relaxed text-emerald-700 dark:text-emerald-300 text-left w-full";
      }} else if (backLines >= 3 || backLen > 65) {{
        backEl.className = "field-zh text-base sm:text-lg font-medium leading-normal text-emerald-700 dark:text-emerald-300 text-center w-full";
      }} else if (backLen > 30) {{
        backEl.className = "field-zh text-xl sm:text-2xl font-bold leading-snug text-emerald-700 dark:text-emerald-300 text-center w-full";
      }} else {{
        backEl.className = "field-zh text-2xl sm:text-3xl font-bold leading-relaxed text-emerald-700 dark:text-emerald-300 text-center w-full";
      }}

      document.getElementById('fc-type-badge').innerText = card.type;
      document.getElementById('fc-cat-badge').innerText = card.category;
      
      const notesBox = document.getElementById('fc-notes-container');
      const notesEl = document.getElementById('fc-notes');
      if (card.notes) {{
        notesEl.innerText = card.notes;
        notesBox.classList.remove('hidden');
      }} else {{
        notesBox.classList.add('hidden');
      }}

      const tagEl = document.getElementById('fc-mastery-tag');
      if (card.mastery === 'mastered') {{
        tagEl.innerText = '🟢 已掌握';
        tagEl.className = 'text-emerald-600 dark:text-emerald-400 font-semibold';
      }} else if (card.mastery === 'unlearned') {{
        tagEl.innerText = '🔴 困難';
        tagEl.className = 'text-rose-600 dark:text-rose-400 font-semibold';
      }} else {{
        tagEl.innerText = '🟡 學習中';
        tagEl.className = 'text-amber-600 dark:text-amber-400 font-semibold';
      }}
    }}

    function prevCard() {{
      if (currentCardIndex > 0) {{
        currentCardIndex--;
      }} else {{
        currentCardIndex = filteredCards.length - 1;
      }}
      updateFlashcardUI();
      if (isAutoPlaying) {{
        if (autoPlayTimer) clearTimeout(autoPlayTimer);
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        autoPlayTimer = setTimeout(runAutoPlayStep, 350);
      }}
    }}

    function nextCard() {{
      if (currentCardIndex < filteredCards.length - 1) {{
        currentCardIndex++;
      }} else {{
        currentCardIndex = 0;
      }}
      updateFlashcardUI();
      if (isAutoPlaying) {{
        if (autoPlayTimer) clearTimeout(autoPlayTimer);
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        autoPlayTimer = setTimeout(runAutoPlayStep, 350);
      }}
    }}

    function setMastery(status) {{
      const card = filteredCards[currentCardIndex];
      if (!card) return;
      card.mastery = status;
      userProgress[card.id] = status;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(userProgress));
      nextCard();
    }}

    // ==========================================
    // 3D 卡牌自動連續播放巡航 (Auto-Play System)
    // 支援：雙語模式 (外語+中文) 與 純英文/外語模式
    // ==========================================
    const AUTOPLAY_MODE_KEY = 'gt_autoplay_mode_v1';
    let autoPlayMode = localStorage.getItem(AUTOPLAY_MODE_KEY) || 'bilingual';
    let isAutoPlaying = false;
    let autoPlayTimer = null;

    function setAutoPlayMode(mode) {{
      autoPlayMode = mode;
      localStorage.setItem(AUTOPLAY_MODE_KEY, mode);
      const sel = document.getElementById('autoplay-mode-select');
      if (sel) sel.value = mode;
      if (isAutoPlaying) {{
        if (autoPlayTimer) clearTimeout(autoPlayTimer);
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        autoPlayTimer = setTimeout(runAutoPlayStep, 300);
      }}
    }}

    function toggleAutoPlay() {{
      if (isAutoPlaying) {{
        stopAutoPlay();
      }} else {{
        startAutoPlay();
      }}
    }}

    function startAutoPlay() {{
      if (filteredCards.length === 0) return;
      isAutoPlaying = true;
      updateAutoPlayButtonUI(true);
      runAutoPlayStep();
    }}

    function stopAutoPlay() {{
      isAutoPlaying = false;
      if (autoPlayTimer) {{
        clearTimeout(autoPlayTimer);
        autoPlayTimer = null;
      }}
      if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
      }}
      updateAutoPlayButtonUI(false);
    }}

    function updateAutoPlayButtonUI(playing) {{
      const btn = document.getElementById('btn-autoplay');
      const icon = document.getElementById('autoplay-icon');
      const text = document.getElementById('autoplay-text');
      if (!btn) return;
      if (playing) {{
        btn.className = "px-4 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-medium shadow-lg shadow-rose-600/30 transition flex items-center gap-1.5 animate-pulse";
        if (icon) icon.innerText = '⏸';
        if (text) text.innerText = '停止播放';
      }} else {{
        btn.className = "px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium shadow-lg shadow-indigo-600/30 transition flex items-center gap-1.5";
        if (icon) icon.innerText = '▶';
        if (text) text.innerText = '自動播放';
      }}
    }}

    function runAutoPlayStep() {{
      if (!isAutoPlaying) return;
      const card = filteredCards[currentCardIndex];
      if (!card) {{
        stopAutoPlay();
        return;
      }}

      // 1. 若卡牌處於翻面狀態，先平滑翻回正面
      if (isFlipped) {{
        flipCard();
      }}

      // 稍微給 200ms 等待卡牌翻正後發音
      autoPlayTimer = setTimeout(() => {{
        if (!isAutoPlaying) return;

        // 2. 朗讀正面文字（法文/英文原生口音）
        playAudio(card.front, card.front_voice || 'en-US', () => {{
          if (!isAutoPlaying) return;

          if (autoPlayMode === 'foreign_only') {{
            // ==========================================
            // 純英文 / 純外語模式：專注沉浸外語聽力
            // 朗讀完正面後停留 2.0 秒吸收，直接切換至下一張
            // ==========================================
            autoPlayTimer = setTimeout(() => {{
              if (!isAutoPlaying) return;

              if (currentCardIndex < filteredCards.length - 1) {{
                currentCardIndex++;
              }} else {{
                currentCardIndex = 0; // 循環播放
              }}
              updateFlashcardUI();

              autoPlayTimer = setTimeout(() => {{
                runAutoPlayStep();
              }}, 450);

            }}, 2000);

          }} else {{
            // ==========================================
            // 雙語模式：正面外語 ➔ 翻牌 ➔ 背面中文釋義
            // ==========================================
            // 正面朗讀結束後，停留 1.6 秒讓學習者在心中回想中文
            autoPlayTimer = setTimeout(() => {{
              if (!isAutoPlaying) return;

              // 自動翻轉至背面
              if (!isFlipped) {{
                flipCard();
              }}

              // 等待 300ms 翻轉動畫完成後朗讀背面釋義
              autoPlayTimer = setTimeout(() => {{
                if (!isAutoPlaying) return;

                playAudio(card.back, card.back_voice || 'zh-TW', () => {{
                  if (!isAutoPlaying) return;

                  // 背面朗讀結束後，停留 2.0 秒讓學習者消化
                  autoPlayTimer = setTimeout(() => {{
                    if (!isAutoPlaying) return;

                    if (currentCardIndex < filteredCards.length - 1) {{
                      currentCardIndex++;
                    }} else {{
                      currentCardIndex = 0; // 循環播放
                    }}
                    updateFlashcardUI();

                    // 延遲 400ms 等待切換過渡後開始下一張
                    autoPlayTimer = setTimeout(() => {{
                      runAutoPlayStep();
                    }}, 400);

                  }}, 2000);
                }});

              }}, 300);

            }}, 1600);
          }}
        }});

      }}, 200);
    }}

    // ==========================================
    // 詞庫清單模式 (Vocabulary List - 支援法文多語辨識)
    // ==========================================
    function filterList() {{
      const q = document.getElementById('list-search').value.toLowerCase().trim();
      const langFilter = document.getElementById('filter-lang').value;
      const catFilter = document.getElementById('filter-cat').value;
      const typeFilter = document.getElementById('filter-type').value;
      const masteryFilter = document.getElementById('filter-mastery').value;
      const sortBy = document.getElementById('sort-by').value;

      let result = items.filter(item => {{
        if (q) {{
          const matchFront = item.front.toLowerCase().includes(q);
          const matchBack = item.back.toLowerCase().includes(q);
          const matchCat = item.category.toLowerCase().includes(q);
          const matchLang = item.lang_badge.toLowerCase().includes(q);
          if (!matchFront && !matchBack && !matchCat && !matchLang) return false;
        }}
        if (langFilter === 'en-zh' && item.lang_group !== 'en-zh') return false;
        if (langFilter === 'fr-all' && !item.is_french) return false;
        if (langFilter === 'fr-en' && item.lang_group !== 'fr-en') return false;
        if (langFilter === 'fr-zh' && item.lang_group !== 'fr-zh') return false;

        if (catFilter !== 'all' && item.category !== catFilter) return false;
        if (typeFilter !== 'all' && item.type !== typeFilter) return false;
        if (masteryFilter !== 'all' && item.mastery !== masteryFilter) return false;
        return true;
      }});

      if (sortBy === 'az') {{
        result.sort((a, b) => a.front.localeCompare(b.front));
      }} else if (sortBy === 'za') {{
        result.sort((a, b) => b.front.localeCompare(a.front));
      }}

      document.getElementById('list-count').innerText = result.length;

      const container = document.getElementById('list-container');
      container.innerHTML = '';

      if (result.length === 0) {{
        container.innerHTML = `<div class="col-span-full py-16 text-center text-slate-500">查無相符詞彙</div>`;
        return;
      }}

      result.forEach(item => {{
        const cardEl = document.createElement('div');
        cardEl.className = "p-4 rounded-xl border border-slate-200 dark:border-slate-800/80 hover:border-emerald-500/50 transition hover:shadow-lg flex flex-col justify-between cursor-pointer group bg-white dark:bg-slate-900/80 shadow-sm";
        cardEl.onclick = () => openDrawer(item);

        const masteryIcon = item.mastery === 'mastered' ? '🟢' : (item.mastery === 'unlearned' ? '🔴' : '🟡');
        const badgeColor = item.is_french ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30' : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30';

        cardEl.innerHTML = `
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <div class="flex items-center flex-wrap gap-1.5 field-tag">
                <span class="px-2 py-0.5 text-[11px] rounded border font-bold ${{badgeColor}}">${{item.lang_badge}}</span>
                <span class="px-2 py-0.5 text-[11px] rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold uppercase">${{item.type}}</span>
                <span class="px-2 py-0.5 text-[11px] rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">${{item.category}}</span>
              </div>
              <span class="text-xs" title="掌握度">${{masteryIcon}}</span>
            </div>
            <h3 class="field-en font-bold text-slate-900 dark:text-white text-base group-hover:text-emerald-600 dark:group-hover:text-emerald-300 transition line-clamp-2">
              ${{item.front}}
            </h3>
            <p class="field-zh text-sm text-slate-600 dark:text-slate-300 mt-1.5 line-clamp-2 leading-relaxed">
              ${{item.back}}
            </p>
          </div>
          <div class="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <button onclick="event.stopPropagation(); playAudio('${{item.front.replace(/'/g, "\\\\'") }}', '${{item.front_voice}}')" class="text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 flex items-center gap-1 font-medium">
              🔊 ${{item.front_flag}} 原文發音
            </button>
            <span class="text-[11px] text-slate-400 dark:text-slate-600">${{item.id}}</span>
          </div>
        `;
        container.appendChild(cardEl);
      }});
    }}

    // ==========================================
    // 自我測驗模式 (Interactive Quiz - 多語題目)
    // ==========================================
    function startNewQuiz() {{
      const pool = [...items].sort(() => 0.5 - Math.random());
      quizQuestions = pool.slice(0, 10);
      currentQuizIndex = 0;
      quizScore = 0;
      quizMistakes = [];

      document.getElementById('quiz-review-section').classList.add('hidden');
      document.getElementById('quiz-total-q').innerText = quizQuestions.length;
      document.getElementById('quiz-score').innerText = '0';
      
      renderQuizQuestion();
    }}

    function renderQuizQuestion() {{
      const q = quizQuestions[currentQuizIndex];
      document.getElementById('quiz-curr-q').innerText = currentQuizIndex + 1;
      document.getElementById('quiz-feedback').classList.add('hidden');
      document.getElementById('quiz-next-btn').classList.add('hidden');

      const isFrontPrompt = Math.random() > 0.4;
      document.getElementById('quiz-question-type').innerText = isFrontPrompt ? `${{q.lang_badge}} 選擇題` : `逆向釋義選擇題`;
      document.getElementById('quiz-prompt').innerText = isFrontPrompt ? q.front : q.back;

      const wrongPool = items.filter(x => x.id !== q.id).sort(() => 0.5 - Math.random()).slice(0, 3);
      const options = [q, ...wrongPool].sort(() => 0.5 - Math.random());

      const container = document.getElementById('quiz-options');
      container.innerHTML = '';

      options.forEach(opt => {{
        const btn = document.createElement('button');
        btn.className = "w-full text-left p-4 rounded-xl bg-slate-50 hover:bg-slate-100 dark:bg-slate-900/80 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700/60 text-slate-800 dark:text-slate-200 font-medium transition flex items-center justify-between";
        btn.innerText = isFrontPrompt ? opt.back : opt.front;
        btn.onclick = () => checkQuizAnswer(opt.id === q.id, q, btn, isFrontPrompt);
        container.appendChild(btn);
      }});
    }}

    function checkQuizAnswer(isCorrect, question, clickedBtn, isFrontPrompt) {{
      const allBtns = document.querySelectorAll('#quiz-options button');
      allBtns.forEach(b => b.disabled = true);

      const feedback = document.getElementById('quiz-feedback');
      feedback.classList.remove('hidden');

      if (isCorrect) {{
        quizScore += 10;
        document.getElementById('quiz-score').innerText = quizScore;
        clickedBtn.classList.add('bg-emerald-500/30', 'border-emerald-500', 'text-emerald-700', 'dark:text-emerald-300');
        feedback.className = "p-4 rounded-xl text-sm font-medium bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40";
        feedback.innerText = "🎉 正確！答得太棒了！";
      }} else {{
        quizMistakes.push(question);
        clickedBtn.classList.add('bg-rose-500/30', 'border-rose-500', 'text-rose-700', 'dark:text-rose-300');
        feedback.className = "p-4 rounded-xl text-sm font-medium bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/40";
        feedback.innerHTML = `❌ 答錯囉！正確答案為：<strong class="text-slate-900 dark:text-white">${{isFrontPrompt ? question.back : question.front}}</strong>`;
      }}

      playAudio(question.front, question.front_voice);
      document.getElementById('quiz-next-btn').classList.remove('hidden');
    }}

    function nextQuizQuestion() {{
      if (currentQuizIndex < quizQuestions.length - 1) {{
        currentQuizIndex++;
        renderQuizQuestion();
      }} else {{
        showQuizSummary();
      }}
    }}

    function playQuizPromptAudio() {{
      const q = quizQuestions[currentQuizIndex];
      if (q) playAudio(q.front, q.front_voice);
    }}

    function showQuizSummary() {{
      const reviewSection = document.getElementById('quiz-review-section');
      reviewSection.classList.remove('hidden');

      const mistakesList = document.getElementById('quiz-mistakes-list');
      mistakesList.innerHTML = '';

      if (quizMistakes.length === 0) {{
        mistakesList.innerHTML = '<div class="text-emerald-600 dark:text-emerald-400 font-bold py-2">🏆 滿分！全數正確無錯題！</div>';
      }} else {{
        quizMistakes.forEach(m => {{
          const itemDiv = document.createElement('div');
          itemDiv.className = "p-3 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between";
          itemDiv.innerHTML = `
            <div>
              <span class="text-xs font-bold text-blue-500 mr-2">${{m.lang_badge}}</span>
              <span class="font-bold text-slate-900 dark:text-white">${{m.front}}</span>
              <span class="text-slate-500 dark:text-slate-400 text-xs ml-2">→ ${{m.back}}</span>
            </div>
            <button onclick="playAudio('${{m.front.replace(/'/g, "\\\\'") }}', '${{m.front_voice}}')" class="text-xs text-emerald-600 dark:text-emerald-400">🔊</button>
          `;
          mistakesList.appendChild(itemDiv);
        }});
      }}
    }}

    // ==========================================
    // 詞彙關係圖譜 (Canvas Force Graph)
    // ==========================================
    let canvas, ctx;
    let graphNodes = [];
    let graphLinks = [];
    let graphSimulating = true;
    let graphScale = 1.0;
    let graphPanX = 0, graphPanY = 0;
    let draggedNode = null;
    let isPanning = false;
    let lastMouseX = 0, lastMouseY = 0;

    function initGraphCanvas() {{
      canvas = document.getElementById('graph-canvas');
      if (!canvas) return;
      ctx = canvas.getContext('2d');

      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;

      const categories = ['商業財務', '科技半導體', '職場管理', '生活哲思', '實用表達', '🇫🇷 法語專區'];
      const catColors = {{
        '商業財務': '#10b981',
        '科技半導體': '#06b6d4',
        '職場管理': '#8b5cf6',
        '生活哲思': '#f59e0b',
        '實用表達': '#ec4899',
        '🇫🇷 法語專區': '#3b82f6'
      }};

      graphNodes = [];
      graphLinks = [];

      categories.forEach((cat, i) => {{
        const angle = (i / categories.length) * Math.PI * 2;
        const radius = 190;
        graphNodes.push({{
          id: 'hub_' + cat,
          label: cat,
          isHub: true,
          color: catColors[cat] || '#10b981',
          r: 28,
          x: canvas.width / 2 + Math.cos(angle) * radius,
          y: canvas.height / 2 + Math.sin(angle) * radius,
          vx: 0,
          vy: 0
        }});
      }});

      const sampleItems = items.slice(0, 130);
      sampleItems.forEach(item => {{
        const hubId = item.is_french ? 'hub_🇫🇷 法語專區' : ('hub_' + item.category);
        const hub = graphNodes.find(n => n.id === hubId) || graphNodes[0];
        
        const node = {{
          id: item.id,
          label: item.front,
          itemRef: item,
          isHub: false,
          color: hub.color,
          r: item.type === 'word' ? 8 : (item.type === 'phrase' ? 6 : 4.5),
          x: hub.x + (Math.random() - 0.5) * 80,
          y: hub.y + (Math.random() - 0.5) * 80,
          vx: 0,
          vy: 0
        }};
        graphNodes.push(node);

        graphLinks.push({{
          source: hub,
          target: node,
          length: 70 + Math.random() * 40
        }});
      }});

      canvas.onmousedown = onCanvasMouseDown;
      canvas.onmousemove = onCanvasMouseMove;
      canvas.onmouseup = onCanvasMouseUp;
      canvas.onwheel = onCanvasWheel;

      requestAnimationFrame(renderGraphLoop);
    }}

    function renderGraphLoop() {{
      if (!ctx) return;

      const isDark = document.documentElement.classList.contains('dark');
      const textColor = isDark ? '#94a3b8' : '#334155';
      const lineColor = isDark ? 'rgba(100, 116, 139, 0.25)' : 'rgba(148, 163, 184, 0.4)';

      if (graphSimulating) {{
        for (let i = 0; i < graphNodes.length; i++) {{
          for (let j = i + 1; j < graphNodes.length; j++) {{
            const n1 = graphNodes[i];
            const n2 = graphNodes[j];
            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 180) {{
              const force = (n1.isHub || n2.isHub ? 450 : 120) / (dist * dist);
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              n1.vx -= fx;
              n1.vy -= fy;
              n2.vx += fx;
              n2.vy += fy;
            }}
          }}
        }}

        graphLinks.forEach(link => {{
          const dx = link.target.x - link.source.x;
          const dy = link.target.y - link.source.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const displacement = dist - link.length;
          const force = displacement * 0.04;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          link.source.vx += fx;
          link.source.vy += fy;
          link.target.vx -= fx;
          link.target.vy -= fy;
        }});

        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        graphNodes.forEach(node => {{
          if (node === draggedNode) return;
          node.vx += (cx - node.x) * 0.0006;
          node.vy += (cy - node.y) * 0.0006;
          node.vx *= 0.85;
          node.vy *= 0.85;
          node.x += node.vx;
          node.y += node.vy;
        }});
      }}

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(graphPanX, graphPanY);
      ctx.scale(graphScale, graphScale);

      ctx.strokeStyle = lineColor;
      ctx.lineWidth = 1;
      graphLinks.forEach(l => {{
        ctx.beginPath();
        ctx.moveTo(l.source.x, l.source.y);
        ctx.lineTo(l.target.x, l.target.y);
        ctx.stroke();
      }});

      graphNodes.forEach(n => {{
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.shadowColor = n.color;
        ctx.shadowBlur = n.isHub ? 12 : 4;
        ctx.fill();
        ctx.shadowBlur = 0;

        if (n.isHub) {{
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(n.label, n.x, n.y + 4);
        }} else if (graphScale > 0.8) {{
          ctx.fillStyle = textColor;
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(n.label.substring(0, 16), n.x, n.y + n.r + 10);
        }}
      }});

      ctx.restore();
      requestAnimationFrame(renderGraphLoop);
    }}

    function onCanvasMouseDown(e) {{
      const rect = canvas.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left - graphPanX) / graphScale;
      const mouseY = (e.clientY - rect.top - graphPanY) / graphScale;

      for (let n of graphNodes) {{
        const dist = Math.hypot(n.x - mouseX, n.y - mouseY);
        if (dist <= n.r + 4) {{
          draggedNode = n;
          if (!n.isHub && n.itemRef) {{
            openDrawer(n.itemRef);
          }}
          return;
        }}
      }}
      isPanning = true;
      lastMouseX = e.clientX;
      lastMouseY = e.clientY;
    }}

    function onCanvasMouseMove(e) {{
      if (draggedNode) {{
        const rect = canvas.getBoundingClientRect();
        draggedNode.x = (e.clientX - rect.left - graphPanX) / graphScale;
        draggedNode.y = (e.clientY - rect.top - graphPanY) / graphScale;
      }} else if (isPanning) {{
        graphPanX += e.clientX - lastMouseX;
        graphPanY += e.clientY - lastMouseY;
        lastMouseX = e.clientX;
        lastMouseY = e.clientY;
      }}
    }}

    function onCanvasMouseUp() {{
      draggedNode = null;
      isPanning = false;
    }}

    function onCanvasWheel(e) {{
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      graphScale = Math.min(Math.max(graphScale * zoomFactor, 0.4), 2.5);
    }}

    function resetGraphView() {{
      graphScale = 1.0;
      graphPanX = 0;
      graphPanY = 0;
    }}

    function toggleGraphSimulation() {{
      graphSimulating = !graphSimulating;
      document.getElementById('btn-graph-sim').innerText = graphSimulating ? '⏸️ 暫停物理模擬' : '▶️ 繼續物理模擬';
    }}

    // ==========================================
    // 滑出式抽屜 (Side Drawer)
    // ==========================================
    function openDrawer(item) {{
      drawerActiveItem = item;
      document.getElementById('drawer-id').innerText = item.id;
      document.getElementById('drawer-cat').innerText = item.category;
      document.getElementById('drawer-type').innerText = item.type.toUpperCase();
      document.getElementById('drawer-front').innerText = item.front;
      document.getElementById('drawer-front-lang').innerText = `${{item.front_flag}} ${{item.front_lang}}原文`;
      document.getElementById('drawer-back').innerText = item.back;
      document.getElementById('drawer-back-label').innerText = `${{item.back_flag}} ${{item.back_lang}}釋義`;

      const langBadge = document.getElementById('drawer-lang-badge');
      langBadge.innerText = item.lang_badge;
      if (item.is_french) {{
        langBadge.className = "px-2.5 py-1 text-xs rounded-md font-bold bg-blue-500/15 text-blue-700 dark:text-blue-300 border border-blue-500/40";
      }} else {{
        langBadge.className = "px-2.5 py-1 text-xs rounded-md font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40";
      }}

      const notesBox = document.getElementById('drawer-notes-box');
      const notesEl = document.getElementById('drawer-notes');
      if (item.notes) {{
        notesEl.innerText = item.notes;
        notesBox.classList.remove('hidden');
      }} else {{
        notesBox.classList.add('hidden');
      }}

      document.getElementById('detail-drawer').classList.remove('translate-x-full');
    }}

    function closeDrawer() {{
      document.getElementById('detail-drawer').classList.add('translate-x-full');
      drawerActiveItem = null;
    }}

    function playDrawerFrontAudio() {{
      if (drawerActiveItem) playAudio(drawerActiveItem.front, drawerActiveItem.front_voice);
    }}

    function playDrawerBackAudio() {{
      if (drawerActiveItem) playAudio(drawerActiveItem.back, drawerActiveItem.back_voice);
    }}

    function setDrawerMastery(status) {{
      if (!drawerActiveItem) return;
      drawerActiveItem.mastery = status;
      userProgress[drawerActiveItem.id] = status;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(userProgress));
      filterList();
      closeDrawer();
    }}

    // ==========================================
    // 快捷鍵監聽 (Keyboard Shortcuts)
    // ==========================================
    window.addEventListener('keydown', (e) => {{
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

      if (activeTab === 'flashcard') {{
        if (e.code === 'Space') {{
          e.preventDefault();
          flipCard();
        }} else if (e.code === 'ArrowLeft') {{
          prevCard();
        }} else if (e.code === 'ArrowRight') {{
          nextCard();
        }} else if (e.key === '1') {{
          setMastery('unlearned');
        }} else if (e.key === '2') {{
          setMastery('learning');
        }} else if (e.key === '3') {{
          setMastery('mastered');
        }} else if (e.key.toLowerCase() === 'p') {{
          playFrontAudio();
        }} else if (e.key.toLowerCase() === 'a') {{
          toggleAutoPlay();
        }}
      }}
    }});

    // 初始化啟動
    window.addEventListener('DOMContentLoaded', () => {{
      initTheme();
      applyDisplayPrefs();
      updateFlashcardUI();
      const sel = document.getElementById('autoplay-mode-select');
      if (sel) sel.value = autoPlayMode;
    }});
  </script>
</body>
</html>
"""
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"🌐 互動式網頁已編譯: {HTML_OUTPUT.name}")

def generate_skill_md():
    """生成專屬 Antigravity Skill 檔案"""
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    content = """---
name: google-translate-learning-workflow
description: >-
  Automates parsing Google Translate exported vocabulary/sentences (.csv, .xlsx, Google Sheets), caching trilingual/bilingual data, maintaining custom overrides, generating structured Markdown study handbooks, and compiling interactive 3D flashcard, quiz, and knowledge graph web apps (index.html). Use when the user asks to update vocabulary, review words, practice translations, or customize the learning web app.
---

# Google Translate Learning Workflow & Interactive Card System

本技能提供 Google 翻譯匯出詞庫的端到端自動化處理工作流，完整支援英語、法語（法翻英、英翻法、法翻中）等多語系自動辨識、母語口音發音 (TTS)、多維篩選、3D 翻牌、自動連續巡航播放、防溢出自適應字級排版與 GitHub Pages 一鍵部署。

---

## 一、系統架構與資料流向

```text
[g_translate.csv.csv] (Google 翻譯匯出檔案，含英語、法語等多語對)
         │
         ▼
[update_learning_app.py] ◄───► [manual_overrides.json] (👑 最高優先級：人工手動覆蓋庫)
         │                            │
         ▼                            ▼
   [vocab_db.json] ──────────► [單字與片語學習手冊.md] (特設法語專章與領域分類)
         │
         ▼
    [index.html] (自包含 RWD 互動學習 Web App：含 5 大模組與雙語/純外語自動播放)
         │
         ▼ (git push)
  [GitHub Pages] (https://sinliongtoo.github.io/google-translate-learning/)
```

---

## 二、多語系辨識與選擇機制

1. **語系精確辨別 (Visual Distinction)**：
   - 每張卡片皆有清晰國旗語言徽章（例如：`🇫🇷 法文 ➔ 🇬🇧 英文`、`🇬🇧 英文 ➔ 🇫🇷 法文`、`🇬🇧 英文 ➔ 🇹🇼 繁中`）。
   - 法語卡片採用專屬蔚藍標籤視覺，英語卡片採用經典翠綠視覺。
2. **多語系篩選器 (Language Filter)**：
   - 3D 卡牌與清單列表皆內建語系過濾器：可一鍵切換「🌐 全部語系」、「🇬🇧 英語 ⇄ 中文」、「🇫🇷 所有法語對翻」、「🇫🇷⇄🇬🇧 法英對翻」或「🇫🇷⇄🇹🇼 法中對翻」。
3. **母語真人發音 (Multi-Language TTS)**：
   - 朗讀法語時，自動調用 Web Speech API 法語母語語音引擎 (`fr-FR`)。
   - 朗讀英語時，自動調用美式/英式英語語音引擎 (`en-US`)。
   - 朗讀中文時，自動調用臺灣繁體語音引擎 (`zh-TW`)。
   - 內建超時看門狗機制（Watchdog Timer），確保語音結束事件丟失時仍能穩定自動推進。

---

## 三、3D 卡牌自動播放系統 (Auto-Play System)

位於 3D 卡牌操作區「下一張」按鈕旁，提供無縫的免動手巡航複習體驗：

1. **雙模播報選擇 (Playback Modes)**：
   - **🌐 雙語模式**（預設）：
     - 朗讀正面外語（法語/英語） ➔ 停留 1.6 秒回想 ➔ 3D 翻轉至背面 ➔ 朗讀中文釋義 ➔ 停留 2.0 秒吸收 ➔ 自動跳下一張循環。
   - **🔤 英文/純外語模式**：
     - 專為磨耳朵與沉浸聽力設計：僅朗讀正面外語 ➔ 停留 2.0 秒加深印象 ➔ **不翻牌、不朗讀中文** ➔ 直接前往下一張自動巡航。
2. **記憶保持與即時響應**：
   - 播報模式偏好自動持久化至 `localStorage`，重新整理或重啟後自動保留。
   - 支援鍵盤捷徑：按下鍵盤 `A` 鍵即可隨時切換開關。
   - 手動切換「上一張」或「下一張」時無縫平滑重置計時；切換分頁時自動暫停，防止背景干擾。

---

## 四、長文與多行列表防破版機制 (Dynamic Responsive Typography)

針對包含長段落、論文筆記或多行核取清單（如 10 行以上代碼或清單）之條目：

1. **動態自適應字級演算法**：
   - **短單字/片語**（<= 30 字元，1~2 行）：`text-2xl sm:text-3xl font-extrabold` 置中。
   - **中長句**（30~65 字元）：`text-xl sm:text-2xl font-bold` 置中。
   - **多行段落**（65~140 字元 或 3~5 行）：`text-base sm:text-lg font-medium` 置中。
   - **超長文章或多行清單**（> 140 字元 或 >= 6 行）：自動切換至 `text-sm sm:text-base font-normal text-left`，文字靠左排列，保證列表項目整齊對齊。
2. **卡片內部滾動保護 (Scroll Containment)**：
   - 正反面容器內嵌 `max-h-[250px] overflow-y-auto` 與細緻滾動條，長文滾動閱讀，絕不溢出至按鈕操作區。
   - 卡牌外框嚴格套用 `overflow-hidden`，並將標籤與底部操作列設為 `shrink-0`，防止高度被擠壓變形。
   - 卡牌高度設定為 `min-h-[400px] h-[430px] sm:h-[410px]`，寬敞大氣。

---

## 五、Web 應用程式五大核心模組

1. **📇 3D 翻轉卡牌 (Flashcards)**：
   - 0.2 秒硬體加速 3D 翻轉，正反面母語語音、掌握度標記（🔴困難 / 🟡學習中 / 🟢精熟）、隨機洗牌、自動巡航。
2. **📋 結構化詞庫清單 (Vocabulary List)**：
   - 毫秒級全域模糊搜尋、語系與主題組合篩選、滑出式詳細資訊抽屜 (Side Drawer)。
3. **✍️ 隨堂測驗評量 (Interactive Quiz)**：
   - 隨機 10 題選擇題，外語選中文 / 中文選外語雙向考核，即時回饋與錯題複習。
4. **🕸️ 知識網絡圖譜 (Canvas Force Graph)**：
   - 原生 HTML5 Canvas 物理引力引擎，視覺化呈現 5 大主題 Hub 與法語樞紐的群聚拓撲。
5. **📖 內建使用手冊分頁 (Help & User Manual Tab)**：
   - 線上查閱完整操作說明、桌面鍵盤捷徑表、記憶遮蓋情境與手機安裝指引。

---

## 六、詞庫更新標準作業流程 (SOP)

當使用者在 Google 翻譯匯出新 CSV 詞庫時，只需執行以下 3 個步驟：

```powershell
# 步驟 1：放入新 CSV 檔案（覆蓋 g_translate.csv.csv）
# 步驟 2：執行本地自動化編譯腳本
python update_learning_app.py

# 步驟 3：推送至 GitHub 觸發自動發布
git add .
git commit -m "feat: update vocabulary and learning handbook"
git push
```
> GitHub Actions 將在 30 秒內自動完成部署，線上 GitHub Pages 立即生效！

---

## 七、人工自訂覆蓋庫 (`manual_overrides.json`) 配置

若特定條目需要客製釋義、例句或指定分類，可在 `manual_overrides.json` 中配置，此設定享有最高優先級，執行更新時永遠不會被自動規則覆蓋：

```json
{
  "overrides": {
    "cadence": {
      "front": "cadence",
      "back": "工作節奏；組織常規進展頻率",
      "category": "職場管理",
      "notes": "在敏捷開發與專案管理中指團隊固定產出的循環 (release cadence)",
      "mastery": "mastered"
    }
  }
}
```

---

## 八、桌面鍵盤捷徑快速參考

| 按鍵 | 功能說明 |
| :--- | :--- |
| <kbd>Space</kbd> | 3D 翻轉卡牌正面 / 背面 |
| <kbd>←</kbd> / <kbd>→</kbd> | 切換至上一張 / 下一張卡片 |
| <kbd>P</kbd> | 播放當前卡面之母語語音 |
| <kbd>A</kbd> | 啟動 / 停止卡牌自動連續播放巡航 |
| <kbd>1</kbd> / <kbd>2</kbd> / <kbd>3</kbd> | 快速標記掌握度（1: 🔴困難、2: 🟡學習中、3: 🟢已掌握） |
"""
    with open(SKILL_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"🛠️ 專屬技能已建置: {SKILL_FILE.name}")

def generate_readme(items):
    """生成專案說明文件 README.md"""
    total = len(items)
    french_count = len([x for x in items if x["is_french"]])
    en_count = total - french_count
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content = f"""# Google 翻譯詞庫互動學習卡牌系統 (G-Translate Learning Hub)

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?logo=github)](https://sinliongtoo.github.io/google-translate-learning/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?logo=python)](https://www.python.org/)
[![Multi-Language](https://img.shields.io/badge/Languages-EN%20%7C%20FR%20%7C%20ZH-orange.svg)](#)

> 將 Google 翻譯（Google Translate）星號儲存的單字與片語，自動轉化為具備 **3D 抽認卡**、**多國語言母語語音 (TTS)**、**智慧分類**、**隨堂測驗**、**知識圖譜** 與 **線上使用手冊 (User Manual Tab)** 的現代化自包含學習網頁。

🔗 **線上學習網址 (GitHub Pages)**: [https://sinliongtoo.github.io/google-translate-learning/](https://sinliongtoo.github.io/google-translate-learning/)

---

## 🌟 核心特色

- 📇 **3D 翻牌抽測模式 (3D Flashcards)**：
  - 0.2 秒極速響應翻牌，正反面獨立母語語音發音（法文 `fr-FR`、英文 `en-US`、繁中 `zh-TW`）。
  - **▶ 自動巡航播放**：位於「下一張」按鈕旁，支援切換**「🌐 雙語模式」**（外語 ➔ 翻牌 ➔ 中文釋義）與**「🔤 英文/純外語模式」**（純外語沉浸聽力），支援快捷鍵 `A` 隨時切換開關。
  - 支援鍵盤捷徑操作（`Space` 翻牌、`←`/`→` 切換、`P` 朗讀、`A` 自動播放、`1`/`2`/`3` 掌握度標記）。
  - 隨機抽卡洗牌功能。
- 📋 **全方位詞庫清單 (Vocab List)**：
  - 支援即時關鍵字模糊搜尋、多維度組合過濾（語系、主題、類型、掌握狀態）。
  - 點擊即彈出側邊詳細資訊抽屜 (Side Drawer)。
- ✍️ **自我測驗模式 (Interactive Quiz)**：
  - 隨機 10 題四選一測驗，雙向考題（外語選中文 / 中文選外語）。
  - 即時反饋、記分與錯題統計複習。
- 🕸️ **知識網絡圖譜 (Canvas Force Graph)**：
  - 基於原生 HTML5 Canvas 物理引力引擎，視覺化呈現主題樞紐與單字群聚關聯。
  - 支援拖曳、滾輪縮放與點擊交互。
- 📖 **內建使用手冊分頁 (Help & User Manual Tab)**：
  - 網頁內建獨立說明書分頁，隨時查閱功能說明、快捷鍵與更新指南。
- 🇫🇷 **深度多語系支援 (French & English Recognition)**：
  - 自動辨識法文對翻（法翻英、英翻法、法翻中），視覺醒目標籤與專屬下拉篩選。
- 🌓 **深淺色主題與無依賴設計**：
  - 完美適配 Dark Mode / Light Mode，完全自包含（Single Page Application），支援離線運作與手機「加入主畫面 (PWA)」。

---

## 📊 目前收錄統計

- **最後更新時間**：`{now_str}`
- **總收錄詞條**：{total} 筆
  - 🇬🇧 英語 ⇄ 繁中：{en_count} 筆
  - 🇫🇷 法語對翻專題：{french_count} 筆
- **詞彙類型**：單字 (Word)、片語 (Phrase)、實用例句 (Sentence)
- **領域分類**：商業財務、科技半導體、職場管理、生活哲思、實用表達

---

## 🏗️ 系統架構

```text
[Google 翻譯匯出 CSV] (g_translate.csv.csv)
          │
          ▼
[update_learning_app.py] ◄───► [manual_overrides.json] (👑 人工自訂覆蓋庫，最高優先級)
          │                            │
          ▼                            ▼
   [vocab_db.json] ──────────► [單字與片語學習手冊.md]
          │
          ▼
    [index.html] (自包含 Web App：含 3D 卡牌、清單、測驗、圖譜、使用說明書)
          │
          ▼ (git push)
   [GitHub Pages] (https://sinliongtoo.github.io/google-translate-learning/)
```

---

## 🔄 詞庫更新與發布作業流程 (SOP)

當您在 Google 翻譯累積了新單字並匯出新的 CSV 檔案時，更新僅需 3 個步驟：

### 步驟 1：放入新 CSV 檔
將下載的 CSV 檔覆蓋至專案目錄下的 `g_translate.csv.csv`。

### 步驟 2：執行自動化編譯腳本
在終端機中執行：
```powershell
python update_learning_app.py
```
> 系統將在 1 秒內自動完成：
> 1. 去除重複項與清理雜訊。
> 2. 自動辨識語系（英語、法語、繁體中文）並指派母語語音代碼。
> 3. 自動執行啟發式領域分類（完全本地運算，不需要消耗 LLM Token）。
> 4. 合併 `manual_overrides.json` 自訂設定。
> 5. 重新編譯 `index.html`、`單字與片語學習手冊.md`、`vocab_db.json` 與 `README.md`。

### 步驟 3：推送至 GitHub
```powershell
git add .
git commit -m "feat: update vocabulary and app"
git push
```
推送完成後，GitHub Actions 將在 30 秒內自動將最新內容部署至線上 GitHub Pages！

---

## 👑 人工手動覆蓋設定 (`manual_overrides.json`)

若您對特定詞條的釋義、筆記或分類有專屬客製需求，可在 `manual_overrides.json` 中進行覆寫。此處設定的條目權重最高，更新時絕不會被自動規則覆蓋：

```json
{{
  "overrides": {{
    "cadence": {{
      "front": "cadence",
      "back": "工作節奏；組織常規進展頻率",
      "category": "職場管理",
      "notes": "在專案管理中常指會議或交付的固定節奏 (e.g., release cadence)",
      "mastery": "mastered"
    }}
  }}
}}
```

---

## 📱 手機 / 行動裝置安裝指南

1. 使用手機瀏覽器（iOS Safari 或 Android Chrome）開啟：  
   `https://sinliongtoo.github.io/google-translate-learning/`
2. **iPhone**：點擊底部分享圖示 ➔ 選擇 **「加入主畫面 (Add to Home Screen)」**。
3. **Android**：點擊右上角三點選單 ➔ 選擇 **「加到主畫面」** 或 **「安裝應用程式」**。
4. 即可如同原生 App 般在手機上隨開隨讀，隨時抽認複習！

---

## 📄 授權條款

本專案基於 MIT 授權條款開放開源使用。
"""
    with open(README_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"📝 說明文件已生成: {README_OUTPUT.name}")

def main():
    print("=" * 60)
    print("🚀 啟動 Google 翻譯多語互動學習工作流 (G-Translate Learning)")
    print("=" * 60)
    
    input_csv = find_input_csv()
    if not input_csv:
        print("❌ 錯誤：找不到 CSV 輸入檔！")
        sys.exit(1)
        
    raw_items = parse_csv_items(input_csv)
    overrides = load_manual_overrides()
    items = merge_and_cache(raw_items, overrides)
    
    generate_markdown_handbook(items)
    generate_interactive_html(items)
    generate_skill_md()
    generate_readme(items)
    
    print("=" * 60)
    print("🎉 工作流全部執行完成！多語學習成果已順利產出！")
    print(f"👉 互動網頁：file:///{HTML_OUTPUT.as_posix()}")
    print(f"👉 學習手冊：file:///{MD_OUTPUT.as_posix()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
