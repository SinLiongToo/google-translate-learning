---
name: google-translate-learning-workflow
description: >-
  Automates parsing Google Translate exported vocabulary/sentences (.csv, .xlsx, Google Sheets), caching trilingual/bilingual data, maintaining custom overrides, generating structured Markdown study handbooks, and compiling interactive 3D flashcard, quiz, and knowledge graph web apps (index.html). Use when the user asks to update vocabulary, review words, practice translations, or customize the learning web app.
---

# Google Translate Learning Workflow & Interactive Card System

本技能提供 Google 翻譯匯出詞庫的端到端自動化處理工作流，完整支援英語、法語（法翻英、英翻法、法翻中）等多語系自動辨識、母語口音發音 (TTS)、多維篩選與 3D 翻牌。

---

## 一、系統架構與多語對照

```text
[g_translate.csv.csv] (Google 翻譯匯出檔案，含英語、法語等多語對)
         │
         ▼
[update_learning_app.py] ◄───► [manual_overrides.json] (👑 最高優先級：人工手動覆蓋庫)
         ▲                            │
         │                            ▼
         │ ◄─────────────────► [vocab_db.json] (快取資料庫)
         │
         ├───► [單字與片語學習手冊.md] (特設「🇫🇷 法語對翻專題篇」與「🇬🇧 英中分類篇」)
         └───► [index.html] (自包含 RWD 互動學習 Web App：法語/英語獨立篩選 + 原生發音)
                     │
                     ▼
           [GitHub Pages 線上發布] (支援完全靜態離線運作)
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
