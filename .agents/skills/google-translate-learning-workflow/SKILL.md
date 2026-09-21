---
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
