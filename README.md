# Google 翻譯詞庫互動學習卡牌系統 (G-Translate Learning Hub)

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

- **最後更新時間**：`2026-09-22 02:53:04`
- **總收錄詞條**：527 筆
  - 🇬🇧 英語 ⇄ 繁中：422 筆
  - 🇫🇷 法語對翻專題：105 筆
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
{
  "overrides": {
    "cadence": {
      "front": "cadence",
      "back": "工作節奏；組織常規進展頻率",
      "category": "職場管理",
      "notes": "在專案管理中常指會議或交付的固定節奏 (e.g., release cadence)",
      "mastery": "mastered"
    }
  }
}
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
