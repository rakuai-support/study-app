// AIアシスタント管理
class AiAssistant {
    constructor() {
        this.isOpen = false;
        this.messages = [];
        this.currentContext = null;
        this.init();
    }

    init() {
        this.detectContext();
        this.setupQuickQuestions();
        this.setupEventListeners();
    }

    // 現在のページコンテキストを検出
    detectContext() {
        const breadcrumb = document.querySelector('.breadcrumb-current');
        const searchInput = document.querySelector('#searchInput');
        
        console.log('🔍 コンテキスト検出中...');
        console.log('breadcrumb要素:', breadcrumb);
        console.log('searchInput要素:', searchInput);
        console.log('searchInput値:', searchInput?.value);
        
        if (breadcrumb) {
            // 学習項目ページ - 詳細情報も取得
            const identifier = breadcrumb.textContent.trim();
            const contentElement = document.querySelector('[data-content-info]');
            
            this.currentContext = {
                type: 'content',
                identifier: identifier,
                message: `「${identifier}」について詳しく説明できます`
            };
            
            // 詳細情報を取得
            if (contentElement) {
                try {
                    const contentInfo = JSON.parse(contentElement.getAttribute('data-content-info'));
                    this.currentContext.contentData = contentInfo;
                    console.log('📚 学習データ取得成功:', contentInfo);
                } catch (error) {
                    console.log('❌ 学習データ取得失敗:', error);
                    // フォールバック: 画面から直接取得
                    const goalElement = document.querySelector('.goal-description');
                    const keywordElements = document.querySelectorAll('.keyword-tag');
                    
                    this.currentContext.fallbackData = {
                        learningObjective: goalElement?.textContent || '',
                        keywords: Array.from(keywordElements).map(el => el.textContent)
                    };
                }
            }
            
            console.log('✅ コンテンツページ検出:', this.currentContext);
        } else if (searchInput && searchInput.value.trim()) {
            // 検索中
            this.currentContext = {
                type: 'search',
                query: searchInput.value.trim(),
                message: `「${searchInput.value.trim()}」の検索に関してサポートします`
            };
            console.log('✅ 検索状態検出:', this.currentContext);
        } else {
            // ホーム画面
            this.currentContext = {
                type: 'home',
                message: '学習に関することなら何でもお聞きください'
            };
            console.log('✅ ホーム画面検出:', this.currentContext);
        }
        
        this.updateContextMessage();
    }

    // コンテキストメッセージを更新
    updateContextMessage() {
        const contextEl = document.getElementById('contextMessage');
        if (contextEl && this.currentContext) {
            contextEl.textContent = this.currentContext.message;
        }
    }

    // クイック質問を設定
    setupQuickQuestions() {
        const quickQuestionsEl = document.getElementById('quickQuestions');
        if (!quickQuestionsEl) return;

        let questions = [];
        
        if (this.currentContext?.type === 'content') {
            questions = [
                'この項目をわかりやすく説明して',
                '関連する練習問題を作って',
                '実生活での応用例を教えて',
                '覚え方のコツは？'
            ];
        } else if (this.currentContext?.type === 'search') {
            questions = [
                'この分野の基礎から教えて',
                '学習順序を教えて',
                '関連する項目は？'
            ];
        } else {
            questions = [
                '数学の学習方法を教えて',
                'おすすめの学習順序は？',
                '効果的な復習方法は？'
            ];
        }

        quickQuestionsEl.innerHTML = questions.map(q => 
            `<button class="quick-question-btn" onclick="aiAssistant.sendQuickQuestion('${q}')">${q}</button>`
        ).join('');
    }

    // イベントリスナー設定
    setupEventListeners() {
        const chatInput = document.getElementById('aiChatInput');
        if (chatInput) {
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // 入力時の自動リサイズ
            chatInput.addEventListener('input', () => {
                chatInput.style.height = 'auto';
                chatInput.style.height = Math.min(chatInput.scrollHeight, 80) + 'px';
            });
        }

        // モーダル外クリックで閉じる
        const modal = document.getElementById('aiAssistantModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.close();
                }
            });
        }
    }

    // モーダルを開く
    open() {
        const modal = document.getElementById('aiAssistantModal');
        if (modal) {
            modal.style.display = 'block';
            this.isOpen = true;
            
            console.log('🚀 AIアシスタント開く - コンテキスト再検出開始');
            
            // コンテキストを再検出
            this.detectContext();
            
            // クイック質問も再設定
            this.setupQuickQuestions();
            
            // フォーカス
            setTimeout(() => {
                const chatInput = document.getElementById('aiChatInput');
                if (chatInput) chatInput.focus();
            }, 300);
        }
    }

    // モーダルを閉じる
    close() {
        const modal = document.getElementById('aiAssistantModal');
        if (modal) {
            modal.style.display = 'none';
            this.isOpen = false;
        }
    }

    // クイック質問を送信
    sendQuickQuestion(question) {
        const chatInput = document.getElementById('aiChatInput');
        if (chatInput) {
            chatInput.value = question;
            this.sendMessage();
        }
    }

    // メッセージを送信
    async sendMessage() {
        console.log('🚀 sendMessage called');
        const chatInput = document.getElementById('aiChatInput');
        const message = chatInput?.value?.trim();
        
        console.log('💬 Message:', message);
        
        if (!message) {
            console.log('❌ Message is empty');
            return;
        }


        // ユーザーメッセージを表示
        this.addMessage('user', message);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // 送信ボタンを無効化
        this.setSendButtonState(false);

        // ローディング表示
        const loadingId = this.addLoadingMessage();

        try {
            // コンテキスト付きプロンプトを構築
            const contextualPrompt = this.buildContextualPrompt(message);
            console.log('🧠 Contextual prompt built');
            
            // 共通のAI呼び出しメソッドを使用
            if (!window.apiManager) {
                console.log('❌ APIマネージャーが見つかりません');
                throw new Error('APIマネージャーが初期化されていません。');
            }
            console.log('✅ APIマネージャーが見つかりました');
            console.log('📡 AI呼び出し開始');
            const data = await window.apiManager.callAI(contextualPrompt, 'Learning Assistant');
            console.log('📡 AI呼び出し完了:', data);

            // ローディング削除
            this.removeLoadingMessage(loadingId);

            if (data.success) {
                this.addMessage('assistant', data.result);
            } else {
                this.showSystemMessage('エラー: ' + data.error);
            }

        } catch (error) {
            console.error('AI Assistant Error:', error);
            this.removeLoadingMessage(loadingId);
            this.showSystemMessage('通信エラーが発生しました: ' + error.message);
        }

        // 送信ボタンを再有効化
        this.setSendButtonState(true);
    }

    // コンテキスト付きプロンプトを構築
    buildContextualPrompt(userMessage) {
        let contextInfo = '';
        
        console.log('🧠 プロンプト構築中...');
        console.log('現在のコンテキスト:', this.currentContext);
        
        if (this.currentContext?.type === 'content') {
            const data = this.currentContext.contentData || this.currentContext.fallbackData;
            
            if (data) {
                contextInfo = `
【現在の学習項目】
• 識別子: ${this.currentContext.identifier}
• 教科: ${data.subject || '未設定'}
• 学年: ${data.grade ? data.grade + '年生' : '未設定'}
• 学習目標: ${data.learningObjective || '未設定'}
• キーワード: ${Array.isArray(data.keywords) ? data.keywords.join(', ') : '未設定'}

【学習ゴール】
${data.beginnerGoals ? '初心者: ' + data.beginnerGoals.join(', ') : ''}
${data.intermediateGoals ? '中級者: ' + data.intermediateGoals.join(', ') : ''}
${data.advancedGoals ? '上級者: ' + data.advancedGoals.join(', ') : ''}
                `;
            } else {
                contextInfo = `現在、学習項目「${this.currentContext.identifier}」について学習中です。`;
            }
        } else if (this.currentContext?.type === 'search') {
            contextInfo = `現在、「${this.currentContext.query}」について検索中です。`;
        }

        const finalPrompt = `あなたは不登校の子どもたちをサポートする優しい教育アシスタントです。
${contextInfo}

ユーザーからの質問: ${userMessage}

以下の点を意識して回答してください：
- 短く、分かりやすい説明（200文字程度）
- マークダウン記法は使わない（普通の文章で）
- 温かく励ましの気持ちを込める
- プレッシャーを与えない表現
- 具体的で実践しやすいアドバイス

簡潔で読みやすい文章で答えてください。`;

        console.log('📝 構築されたプロンプト:', finalPrompt);
        return finalPrompt;
    }

    // メッセージを追加
    addMessage(type, content) {
        const messagesContainer = document.getElementById('aiChatMessages');
        if (!messagesContainer) return;

        // ウェルカムメッセージを非表示
        const welcome = document.querySelector('.ai-chat-welcome');
        if (welcome) {
            welcome.style.display = 'none';
        }

        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${type}`;
        messageEl.textContent = content;
        
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        this.messages.push({ type, content, timestamp: Date.now() });
    }

    // ローディングメッセージを追加
    addLoadingMessage() {
        const messagesContainer = document.getElementById('aiChatMessages');
        if (!messagesContainer) return null;

        const loadingId = 'loading_' + Date.now();
        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message loading';
        messageEl.id = loadingId;
        messageEl.innerHTML = `
            考えています...
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return loadingId;
    }

    // ローディングメッセージを削除
    removeLoadingMessage(loadingId) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) {
            loadingEl.remove();
        }
    }

    // システムメッセージを表示
    showSystemMessage(message) {
        const messagesContainer = document.getElementById('aiChatMessages');
        if (!messagesContainer) return;

        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message assistant';
        messageEl.style.backgroundColor = '#fff3cd';
        messageEl.style.color = '#856404';
        messageEl.style.border = '1px solid #ffeaa7';
        messageEl.textContent = message;
        
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 送信ボタンの状態を設定
    setSendButtonState(enabled) {
        const sendBtn = document.getElementById('aiChatSend');
        if (sendBtn) {
            sendBtn.disabled = !enabled;
        }
    }
}

// グローバル関数
function toggleAiAssistant() {
    if (!window.aiAssistant) {
        console.log('⚠️ AIアシスタントがまだ初期化されていません');
        return;
    }
    
    if (window.aiAssistant.isOpen) {
        window.aiAssistant.close();
    } else {
        window.aiAssistant.open();
    }
}

function closeAiAssistant() {
    if (!window.aiAssistant) {
        console.log('⚠️ AIアシスタントがまだ初期化されていません');
        return;
    }
    window.aiAssistant.close();
}

function sendAiMessage() {
    if (!window.aiAssistant) {
        console.log('⚠️ AIアシスタントがまだ初期化されていません');
        return;
    }
    window.aiAssistant.sendMessage();
}

// 初期化（他のスクリプトの読み込みを待つ）
document.addEventListener('DOMContentLoaded', function() {
    let attempts = 0;
    const maxAttempts = 100; // 最大10秒待機
    
    // APIマネージャーが初期化されるまで待機
    function initializeWhenReady() {
        attempts++;
        
        if (window.apiManager) {
            window.aiAssistant = new AiAssistant();
            console.log('✅ AIアシスタント初期化完了');
        } else if (attempts < maxAttempts) {
            console.log(`⏳ APIマネージャーを待機中... (${attempts}/${maxAttempts})`);
            setTimeout(initializeWhenReady, 100);
        } else {
            console.error('❌ APIマネージャーの初期化がタイムアウトしました。ページを再読み込みしてください。');
        }
    }
    
    // より確実な初期化のために少し遅延
    setTimeout(initializeWhenReady, 100);
});