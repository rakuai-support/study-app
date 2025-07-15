// APIキー管理システム
class APIKeyManager {
    constructor() {
        this.storageKey = 'gemini_api_key';
        this.init();
    }

    init() {
        // 登録・ログインページではAPI管理を無効化
        const currentPath = window.location.pathname;
        if (currentPath.includes('/register') || currentPath.includes('/login')) {
            console.log('📝 登録・ログインページのため、API管理を無効化します。');
            return;
        }

        this.setupEventListeners();
        this.updateAPIStatus();
        this.loadSavedAPIKey();
    }

    setupEventListeners() {
        // API設定ボタン
        const apiSettingsBtn = document.getElementById('apiSettingsBtn');
        if (apiSettingsBtn) {
            apiSettingsBtn.addEventListener('click', () => {
                this.openApiModal();
            });
        }

        // APIキー表示切り替え
        const toggleApiKey = document.getElementById('toggleApiKey');
        if (toggleApiKey) {
            toggleApiKey.addEventListener('click', () => {
                this.toggleAPIKeyVisibility();
            });
        }

        // APIキーテスト
        const testApiKey = document.getElementById('testApiKey');
        if (testApiKey) {
            testApiKey.addEventListener('click', () => {
                this.testAPIKey();
            });
        }

        // APIキー保存
        const saveApiKey = document.getElementById('saveApiKey');
        if (saveApiKey) {
            saveApiKey.addEventListener('click', () => {
                this.saveAPIKey();
            });
        }

        // APIキークリア
        const clearApiKey = document.getElementById('clearApiKey');
        if (clearApiKey) {
            clearApiKey.addEventListener('click', () => {
                this.clearAPIKey();
            });
        }

        // モーダル外クリックで閉じる
        window.addEventListener('click', (event) => {
            if (event.target.classList.contains('api-modal')) {
                this.closeApiModal();
            }
            if (event.target.classList.contains('ai-modal')) {
                this.closeAiModal();
            }
        });
    }

    // APIキーを暗号化してlocalStorageに保存
    saveAPIKeyToStorage(apiKey) {
        try {
            const encrypted = btoa(apiKey); // 簡易暗号化
            localStorage.setItem(this.storageKey, encrypted);
            return true;
        } catch (error) {
            console.error('APIキー保存エラー:', error);
            return false;
        }
    }

    // APIキーを復号化してlocalStorageから取得
    getAPIKeyFromStorage() {
        try {
            const encrypted = localStorage.getItem(this.storageKey);
            return encrypted ? atob(encrypted) : null;
        } catch (error) {
            console.error('APIキー取得エラー:', error);
            return null;
        }
    }

    // APIキーをストレージから削除
    removeAPIKeyFromStorage() {
        localStorage.removeItem(this.storageKey);
    }

    // APIキーの有効性をテスト
    async testAPIKey() {
        const apiKey = document.getElementById('apiKeyInput').value.trim();
        
        if (!apiKey) {
            this.showTestResult('APIキーを入力してください', 'error');
            return;
        }

        this.showTestResult('テスト中...', 'loading');
        
        try {
            const response = await fetch('/api/test-api-key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: apiKey
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showTestResult('✅ APIキーは有効です', 'success');
            } else {
                this.showTestResult(`❌ ${data.error}`, 'error');
            }
        } catch (error) {
            this.showTestResult('❌ テストに失敗しました', 'error');
            console.error('APIキーテストエラー:', error);
        }
    }

    // APIキーを保存
    saveAPIKey() {
        const apiKey = document.getElementById('apiKeyInput').value.trim();
        
        if (!apiKey) {
            this.showTestResult('APIキーを入力してください', 'error');
            return;
        }

        if (this.saveAPIKeyToStorage(apiKey)) {
            this.showTestResult('✅ APIキーを保存しました', 'success');
            this.updateAPIStatus();
            
            // 2秒後にモーダルを閉じる
            setTimeout(() => {
                this.closeApiModal();
            }, 1500);
        } else {
            this.showTestResult('❌ 保存に失敗しました', 'error');
        }
    }

    // APIキーをクリア
    clearAPIKey() {
        if (confirm('保存されたAPIキーを削除しますか？')) {
            this.removeAPIKeyFromStorage();
            document.getElementById('apiKeyInput').value = '';
            this.showTestResult('🗑️ APIキーを削除しました', 'info');
            this.updateAPIStatus();
        }
    }

    // 保存されたAPIキーを読み込み
    loadSavedAPIKey() {
        const apiKeyInput = document.getElementById('apiKeyInput');
        if (!apiKeyInput) {
            console.log('⚠️ apiKeyInput要素が見つかりません');
            return;
        }
        
        const savedKey = this.getAPIKeyFromStorage();
        if (savedKey) {
            apiKeyInput.value = savedKey;
        }
    }

    // APIキーの表示/非表示を切り替え
    toggleAPIKeyVisibility() {
        const input = document.getElementById('apiKeyInput');
        const icon = document.querySelector('#toggleApiKey i');
        
        if (input.type === 'password') {
            input.type = 'text';
            icon.className = 'fas fa-eye-slash';
        } else {
            input.type = 'password';
            icon.className = 'fas fa-eye';
        }
    }

    // テスト結果を表示
    showTestResult(message, type) {
        const resultDiv = document.getElementById('apiTestResult');
        resultDiv.textContent = message;
        resultDiv.className = `api-test-result ${type}`;
        
        // 成功またはエラーメッセージは5秒後に消去
        if (type === 'success' || type === 'error') {
            setTimeout(() => {
                resultDiv.textContent = '';
                resultDiv.className = 'api-test-result';
            }, 5000);
        }
    }

    // APIステータスを更新
    updateAPIStatus() {
        const statusSpan = document.getElementById('apiStatus');
        if (!statusSpan) {
            console.log('⚠️ apiStatus要素が見つかりません');
            return;
        }
        
        const hasKey = this.getAPIKeyFromStorage() !== null;
        
        statusSpan.textContent = hasKey ? '✅' : '❌';
        statusSpan.title = hasKey ? 'APIキー設定済み' : 'APIキー未設定';
    }

    // API設定モーダルを開く
    openApiModal() {
        document.getElementById('apiModal').style.display = 'flex';
        this.loadSavedAPIKey();
    }

    // API設定モーダルを閉じる
    closeApiModal() {
        document.getElementById('apiModal').style.display = 'none';
        document.getElementById('apiTestResult').textContent = '';
        document.getElementById('apiTestResult').className = 'api-test-result';
    }

    // AIプロンプトモーダルを開く
    openAiModal(contentType, prompt) {
        const modal = document.getElementById('aiPromptModal');
        const promptTextarea = document.getElementById('promptText');
        const contentTypeBadge = document.getElementById('currentContentType');
        
        promptTextarea.value = prompt;
        contentTypeBadge.textContent = contentType;
        modal.style.display = 'flex';
        
        // コンテキスト情報を保存（content画面の場合）
        this.saveCurrentContext();
    }

    // 現在のコンテキスト情報を保存
    saveCurrentContext() {
        const currentContext = {};
        
        // content画面かどうかを判定
        if (window.location.pathname.includes('/content/')) {
            currentContext.page_type = 'content';
            
            // content画面のデータを取得
            const contentElement = document.querySelector('[data-content-info]');
            if (contentElement) {
                try {
                    const contentInfo = JSON.parse(contentElement.getAttribute('data-content-info'));
                    console.log('コンテキスト情報:', contentInfo); // デバッグ用
                    currentContext.learning_objective = contentInfo.learningObjective || '';
                    currentContext.subject = contentInfo.subject || '';
                    currentContext.grade = contentInfo.grade || '';
                    currentContext.keywords = contentInfo.keywords || [];
                    currentContext.beginner_goals = contentInfo.beginnerGoals || [];
                    currentContext.intermediate_goals = contentInfo.intermediateGoals || [];
                    currentContext.advanced_goals = contentInfo.advancedGoals || [];
                } catch (error) {
                    console.log('コンテキスト情報の取得に失敗:', error);
                    // フォールバック: 画面から直接データを取得
                    const learningGoalElement = document.querySelector('.goal-description');
                    if (learningGoalElement) {
                        currentContext.learning_objective = learningGoalElement.textContent || '';
                    }
                    const keywordElements = document.querySelectorAll('.keyword-tag');
                    currentContext.keywords = Array.from(keywordElements).map(el => el.textContent);
                }
            }
        } else {
            currentContext.page_type = 'home';
        }
        
        this.currentContext = currentContext;
    }

    // AIプロンプトモーダルを閉じる
    closeAiModal() {
        document.getElementById('aiPromptModal').style.display = 'none';
        document.getElementById('aiResult').innerHTML = '';
    }

    // 共通のAI呼び出しメソッド
    async callAI(prompt, contentType = '') {
        // 認証チェック
        if (!window.authManager || !window.authManager.isLoggedIn()) {
            throw new Error('ログインが必要です。');
        }

        // 利用制限チェック
        if (!window.authManager.canUseAI()) {
            window.authManager.showUsageLimitModal();
            throw new Error('利用制限に達しました。');
        }

        if (!prompt) {
            throw new Error('プロンプトが空です。');
        }

        try {
            const response = await fetch('/api/ai-generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                    content_type: contentType,
                    context: this.currentContext || {}
                })
            });

            const data = await response.json();
            
            if (data.success) {
                // 利用回数を更新
                if (data.usage_count !== undefined && window.authManager) {
                    window.authManager.updateUsageCount(data.usage_count);
                }
                
                return {
                    success: true,
                    result: data.result
                };
            } else {
                // 利用制限超過の場合はモーダルを表示
                if (data.error === 'USAGE_LIMIT_EXCEEDED' && window.authManager) {
                    window.authManager.showUsageLimitModal();
                }
                
                return {
                    success: false,
                    error: data.error
                };
            }
        } catch (error) {
            return {
                success: false,
                error: 'ネットワークエラーが発生しました: ' + error.message
            };
        }
    }

    // AIプロンプトを実行
    async executeAIPrompt() {
        const prompt = document.getElementById('promptText').value.trim();
        const contentType = document.getElementById('currentContentType').textContent;
        
        if (!prompt) {
            alert('プロンプトを入力してください。');
            return;
        }

        // ローディング開始
        const executeBtn = document.getElementById('executeAI');
        const loadingSpinner = executeBtn.querySelector('.loading-spinner');
        const resultDiv = document.getElementById('aiResult');
        
        executeBtn.disabled = true;
        loadingSpinner.style.display = 'inline-block';
        resultDiv.innerHTML = '<div class="loading-message"><i class="fas fa-spinner fa-spin"></i> AIが回答を生成中...</div>';

        try {
            const data = await this.callAI(prompt, contentType);

            if (data.success) {
                // マークダウンを簡易HTMLに変換
                const htmlResult = this.markdownToHtml(data.result);
                resultDiv.innerHTML = `
                    <div class="ai-result-header">
                        <h4><i class="fas fa-robot"></i> AI回答結果</h4>
                        <button onclick="copyToClipboard('${data.result.replace(/'/g, "\\'")}')">
                            <i class="fas fa-copy"></i> コピー
                        </button>
                    </div>
                    <div class="ai-result-content">${htmlResult}</div>
                `;
            } else {
                resultDiv.innerHTML = `<div class="ai-error">❌ エラー: ${data.error}</div>`;
            }
        } catch (error) {
            resultDiv.innerHTML = `<div class="ai-error">❌ 通信エラーが発生しました: ${error.message}</div>`;
            console.error('AI実行エラー:', error);
        } finally {
            executeBtn.disabled = false;
            loadingSpinner.style.display = 'none';
        }
    }

    // 簡易マークダウンをHTMLに変換
    markdownToHtml(markdown) {
        return markdown
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^\* (.*$)/gim, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            .replace(/\n/g, '<br>');
    }
}

// グローバル関数
function openApiModal() {
    window.apiManager.openApiModal();
}

function closeApiModal() {
    window.apiManager.closeApiModal();
}

function openAiModal(contentType, prompt) {
    window.apiManager.openAiModal(contentType, prompt);
}

function closeAiModal() {
    window.apiManager.closeAiModal();
}

// ページ読み込み時に初期化
document.addEventListener('DOMContentLoaded', function() {
    try {
        console.log('🔧 APIマネージャー初期化開始');
        window.apiManager = new APIKeyManager();
        console.log('✅ APIマネージャー初期化完了');
        
        // AI実行ボタンのイベント設定
        const executeBtn = document.getElementById('executeAI');
        if (executeBtn) {
            executeBtn.addEventListener('click', () => {
                window.apiManager.executeAIPrompt();
            });
        }
    } catch (error) {
        console.error('❌ APIマネージャー初期化エラー:', error);
    }
});