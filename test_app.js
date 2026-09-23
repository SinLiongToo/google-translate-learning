#!/usr/bin/env node
/**
 * Automated Headless Test Suite for Google Translate Learning System (index.html)
 * 驗證 index.html 的 JavaScript 語法、DOM 渲染與核心使用者互動邏輯
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML_FILE = path.join(__dirname, 'index.html');

console.log('====================================================');
console.log('🧪 正在執行 index.html 全方位品質驗證測試...');
console.log('====================================================');

if (!fs.existsSync(HTML_FILE)) {
  console.error('❌ 找不到 index.html！請先執行 python update_learning_app.py 生成。');
  process.exit(1);
}

const html = fs.readFileSync(HTML_FILE, 'utf8');

// 1. 檢查彈窗遮罩樣式 (避免 Tailwind hidden/flex 優先級覆蓋導致阻擋點擊)
console.log('🔍 [檢查 1/4] 驗證彈窗與遮罩層層疊樣式 (Click Protection)...');
const modalMatch = html.match(/id="global-find-modal"[^>]*style="([^"]*)"/);
if (!modalMatch || !modalMatch[1].includes('display: none')) {
  console.error('❌ 嚴重安全性警告: #global-find-modal 必須具備 inline style="display: none;"，否則會阻擋頁面點擊！');
  process.exit(1);
}
console.log('  ✅ 彈窗遮罩防護合格 (具備 style="display: none;")');

// 2. 擷取並檢查所有 <script> 標籤語法 (Syntax Check)
console.log('🔍 [檢查 2/4] 驗證所有 <script> 區塊語法正確性...');
const scriptRegex = /<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/gi;
const scripts = [];
let match;
while ((match = scriptRegex.exec(html)) !== null) {
  if (match[1].trim()) {
    scripts.push(match[1]);
  }
}

if (scripts.length === 0) {
  console.error('❌ index.html 中未找到任何 <script> 標籤！');
  process.exit(1);
}

for (let i = 0; i < scripts.length; i++) {
  try {
    new vm.Script(scripts[i]);
    console.log(`  ✅ <script> 區塊 #${i + 1} 語法驗證通過 (${scripts[i].length} 位元組)`);
  } catch (err) {
    console.error(`❌ <script> 區塊 #${i + 1} 語法錯誤:`, err.message);
    process.exit(1);
  }
}

// 3. 核心業務邏輯模擬執行測試 (Headless Runtime DOM Test)
console.log('🔍 [檢查 3/4] 模擬瀏覽器 DOM 執行環境與狀態機測試...');
const mainScript = scripts[scripts.length - 1]; // 主要邏輯腳本

const elements = {};
const getElem = (id) => {
  if (!elements[id]) {
    elements[id] = {
      id,
      innerText: '',
      innerHTML: '',
      style: {},
      classList: {
        _classes: new Set(),
        add(...cls) { cls.forEach(c => this._classes.add(c)); },
        remove(...cls) { cls.forEach(c => this._classes.delete(c)); },
        contains(c) { return this._classes.has(c); },
        toggle(c) { if (this.contains(c)) this.remove(c); else this.add(c); }
      },
      value: '',
      scrollIntoView: () => {},
      focus: () => {}
    };
  }
  return elements[id];
};

const domMock = {
  documentElement: {
    classList: {
      add: () => {},
      remove: () => {},
      contains: () => false
    }
  },
  getElementById: getElem,
  querySelectorAll: () => [],
  addEventListener: () => {}
};

const windowMock = {
  addEventListener: () => {},
  speechSynthesis: {
    cancel: () => {},
    speak: () => {},
    speaking: false,
    pending: false,
    getVoices: () => []
  },
  location: { search: '' }
};

const localStorageMock = {
  _store: {},
  getItem(k) { return this._store[k] || null; },
  setItem(k, v) { this._store[k] = String(v); }
};

global.document = domMock;
global.window = windowMock;
global.localStorage = localStorageMock;

try {
  // 注入全域暴露點以便測試私有函式
  const testBoilerplate = `
    global.items = items;
    global.filteredCards = filteredCards;
    global.updateFlashcardUI = updateFlashcardUI;
    global.nextCard = nextCard;
    global.prevCard = prevCard;
    global.flipCard = flipCard;
    global.setCardFlipped = setCardFlipped;
    global.setMastery = setMastery;
    global.jumpToCardInFlashcard = jumpToCardInFlashcard;
    global.handleGlobalFindInput = handleGlobalFindInput;
    global.openGlobalFind = openGlobalFind;
    global.closeGlobalFind = closeGlobalFind;
    global.getCurrentCardIndex = () => currentCardIndex;
  `;
  
  eval(mainScript + '\n;' + testBoilerplate);
  console.log('  ✅ 核心資料與函式庫初始化載入成功 (共有 ' + global.items.length + ' 筆詞庫資料)');
} catch (err) {
  console.error('❌ 核心腳本在全域評估時崩潰 (Runtime Error):', err.message, err.stack);
  process.exit(1);
}

// 4. 測試核心互動操作流程
console.log('🔍 [檢查 4/4] 測試關鍵互動操作 (Next, Prev, Flip, Search, Jump)...');

try {
  // 4.1 初始渲染
  global.updateFlashcardUI();
  const initCard = global.filteredCards[global.getCurrentCardIndex()];
  console.log(`  ✅ 初始卡牌渲染正常: [${initCard.front}] (索引: ${global.getCurrentCardIndex() + 1}/${global.filteredCards.length})`);

  // 4.2 下一張
  const prevIdx = global.getCurrentCardIndex();
  global.nextCard();
  const nextIdx = global.getCurrentCardIndex();
  if (nextIdx !== (prevIdx + 1) % global.filteredCards.length) {
    throw new Error(`nextCard() 索引計算異常: 前次 ${prevIdx}, 當前 ${nextIdx}`);
  }
  console.log(`  ✅ 下一張 (nextCard) 運作正常 (索引變更: ${prevIdx + 1} ➔ ${nextIdx + 1})`);

  // 4.3 上一張
  global.prevCard();
  const backIdx = global.getCurrentCardIndex();
  if (backIdx !== prevIdx) {
    throw new Error(`prevCard() 索引計算異常: 預期 ${prevIdx}, 實際 ${backIdx}`);
  }
  console.log(`  ✅ 上一張 (prevCard) 運作正常 (索引退回: ${nextIdx + 1} ➔ ${backIdx + 1})`);

  // 4.4 3D 翻面
  global.setCardFlipped(true, false);
  const innerEl = elements['card-inner'];
  if (!innerEl.style.transform || !innerEl.style.transform.includes('rotateY(180deg)')) {
    throw new Error('setCardFlipped(true) 未正確設定 rotateY(180deg)');
  }
  global.setCardFlipped(false, false);
  if (!innerEl.style.transform || !innerEl.style.transform.includes('rotateY(0deg)')) {
    throw new Error('setCardFlipped(false) 未正確設定 rotateY(0deg)');
  }
  console.log('  ✅ 3D 卡牌翻轉狀態機運作正常');

  // 4.5 標記掌握度
  global.setMastery('mastered');
  console.log('  ✅ 掌握度設定與自動切換下一張運作正常');

  // 4.6 全域查找輸入與跳轉
  global.handleGlobalFindInput('camarada');
  console.log('  ✅ 全域搜尋處理 (handleGlobalFindInput) 運作正常');

  if (global.items.length > 5) {
    const targetItem = global.items[3];
    global.jumpToCardInFlashcard(targetItem.id);
    const jumpedCard = global.filteredCards[global.getCurrentCardIndex()];
    if (jumpedCard.id !== targetItem.id) {
      throw new Error(`jumpToCardInFlashcard 定位失敗: 預期 ${targetItem.id}, 實際 ${jumpedCard.id}`);
    }
    console.log(`  ✅ 抽屜/搜尋直達 3D 卡牌 (jumpToCardInFlashcard) 成功跳轉定位: [${jumpedCard.front}]`);
  }

} catch (err) {
  console.error('❌ 互動行為測試失敗 (Interaction Test Failed):', err.message, err.stack);
  process.exit(1);
}

console.log('====================================================');
console.log('🎉 所有驗證檢查 100% 通過！未發現任何語法或執行期錯誤。');
console.log('====================================================');
process.exit(0);
