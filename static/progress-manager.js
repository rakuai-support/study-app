
// 学習進捗管理システム (パフォーマンス最適化版)
class ProgressManager {
    constructor() {
        // ログイン中のユーザーIDを取得
        this.userId = null;
        this.progressData = {}; // { 'identifier': { 'level': [true, false], ... }, ... }
        
        // パフォーマンス最適化用
        this.localCache = {}; // ローカルキャッシュ
        this.pendingUpdates = new Map(); // 未保存の変更: Map<string, {identifier, level, goalIndex, completed}>
        this.saveTimeout = null; // デバウンス用タイマー
        this.SAVE_DELAY = 3000; // 3秒デバウンス
        this.isSaving = false; // 保存中フラグ
        
        // API統計キャッシュ
        this.statsCache = null;
        this.statsCacheExpiry = null;
        this.STATS_CACHE_DURATION = 30000; // 30秒キャッシュ
        
        // 進捗データキャッシュ
        this.progressDataCache = null;
        this.progressCacheExpiry = null;
        this.PROGRESS_CACHE_DURATION = 60000; // 60秒キャッシュ
        this.lastProgressLoadTime = null;
        
        this.init();
    }

    async init() {
        // 登録・ログインページでは進捗管理を無効化
        const currentPath = window.location.pathname;
        if (currentPath.includes('/register') || currentPath.includes('/login')) {
            console.log('📝 登録・ログインページのため、進捗管理を無効化します。');
            return;
        }

        // 古いlocalStorageデータをクリア（ユーザー別管理に移行）
        this.clearOldLocalStorageData();
        
        await this.getCurrentUser();
        if (this.userId) {
            await this.loadProgressFromServer();
            this.initializeLocalCache();
            this.setupEventListeners();
            this.setupAutoSave();
            await this.initializeUI();
        } else {
            console.log('⚠️ ユーザーがログインしていません。進捗管理は無効です。');
        }
    }

    // 古いlocalStorageデータをクリア
    clearOldLocalStorageData() {
        const keysToRemove = ['progress_data', 'lastMilestone', 'studyProgress'];
        keysToRemove.forEach(key => {
            if (localStorage.getItem(key)) {
                localStorage.removeItem(key);
                console.log(`🗑️ 古いlocalStorageデータを削除: ${key}`);
            }
        });
    }

    // 現在のユーザー情報を取得
    async getCurrentUser() {
        try {
            const response = await fetch('/api/current-user');
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.userId = data.user.id;
                    console.log(`✅ ユーザー認証成功: ${data.user.email} (ID: ${this.userId})`);
                } else {
                    console.log('⚠️ ユーザーが認証されていません');
                    this.showUserFriendlyError('ログインが必要です', 'ログインしてから学習を始めましょう。');
                }
            } else if (response.status === 401) {
                console.log('⚠️ 認証が期限切れです');
                this.showUserFriendlyError('セッションが期限切れです', 'もう一度ログインしてください。', true);
            } else {
                console.log('⚠️ ユーザー情報の取得に失敗しました');
                this.showUserFriendlyError('接続エラー', 'サーバーとの通信に問題があります。しばらく待ってから再試行してください。');
            }
        } catch (error) {
            console.error('ユーザー情報取得エラー:', error);
            if (!navigator.onLine) {
                this.showUserFriendlyError('インターネット接続エラー', 'インターネット接続を確認してください。');
            } else {
                this.showUserFriendlyError('予期しないエラー', 'しばらく待ってから再試行してください。');
            }
        }
    }

    setupEventListeners() {
        // チェックボックスの変更を監視（最適化版）
        document.addEventListener('change', (event) => {
            if (event.target.classList.contains('progress-checkbox')) {
                this.handleProgressChangeOptimized(event.target);
            }
        });

        // 進捗リセットボタン (注意: 現状はUIのみのリセット)
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('reset-progress-btn')) {
                this.resetProgress(event.target.dataset.identifier);
            }
        });
    }
    
    // ローカルキャッシュ初期化
    initializeLocalCache() {
        this.localCache = JSON.parse(JSON.stringify(this.progressData));
        console.log('✅ ローカルキャッシュを初期化しました');
    }
    
    // 自動保存設定
    setupAutoSave() {
        // ページ離脱時の強制保存
        window.addEventListener('beforeunload', () => {
            if (this.pendingUpdates.size > 0) {
                this.forceSaveToServer();
            }
        });
        
        // フォーカス離脱時の保存
        window.addEventListener('blur', () => {
            if (this.pendingUpdates.size > 0) {
                this.batchSaveToServer();
            }
        });
        
        console.log('✅ 自動保存機能をセットアップしました');
    }
    
    // 最適化された進捗変更ハンドラー
    handleProgressChangeOptimized(checkbox) {
        const identifier = checkbox.dataset.identifier;
        const level = checkbox.dataset.level;
        const goalIndex = parseInt(checkbox.dataset.index, 10);
        const isCompleted = checkbox.checked;
        
        console.log(`🚀 [OPTIMIZED] 進捗変更: ${identifier}.${level}[${goalIndex}] = ${isCompleted}`);
        
        // 1. 即座にローカルキャッシュ更新
        this.updateLocalCache(identifier, level, goalIndex, isCompleted);
        
        // 2. UI即時更新
        this.updateUIImmediately(identifier);
        
        // 3. 変更を未保存リストに追加
        const updateKey = `${identifier}.${level}.${goalIndex}`;
        this.pendingUpdates.set(updateKey, {
            identifier,
            level,
            goalIndex,
            completed: isCompleted
        });
        
        // 4. デバウンス保存
        this.scheduleBatchSave();
    }
    
    // ローカルキャッシュ更新
    updateLocalCache(identifier, level, goalIndex, isCompleted) {
        if (!this.localCache[identifier]) {
            this.localCache[identifier] = {};
        }
        if (!this.localCache[identifier][level]) {
            this.localCache[identifier][level] = [];
        }
        
        this.localCache[identifier][level][goalIndex] = isCompleted;
        
        // progressDataも更新（既存機能との互換性）
        if (!this.progressData[identifier]) {
            this.progressData[identifier] = {};
        }
        if (!this.progressData[identifier][level]) {
            this.progressData[identifier][level] = [];
        }
        this.progressData[identifier][level][goalIndex] = isCompleted;
    }
    
    // UI即時更新
    updateUIImmediately(identifier) {
        // 進捗バーと統計を即座に更新
        this.updateProgressDisplay(identifier);
        
        // 進捗変更通知
        this.showProgressNotification(true);
        
        // 学習日を記録
        if (window.recordStudyDay) {
            window.recordStudyDay();
        }
        
        // フローティング進捗カードも更新
        if (window.location.pathname === '/') {
            this.updateFloatingProgressCard();
        }
    }
    
    // フローティング進捗カード更新
    updateFloatingProgressCard() {
        // 既存のupdateHomePageProgressメソッドを呼び出し
        if (typeof this.updateHomePageProgress === 'function') {
            this.updateHomePageProgress();
        }
    }
    
    // バッチ保存のスケジューリング
    scheduleBatchSave() {
        // 既存のタイマーをクリア
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        // 新しいタイマー設定
        this.saveTimeout = setTimeout(() => {
            this.batchSaveToServer();
        }, this.SAVE_DELAY);
        
        console.log(`⏰ バッチ保存を${this.SAVE_DELAY}ms後にスケジュール (保留中: ${this.pendingUpdates.size}件)`);
    }
    
    // バッチ保存実行
    async batchSaveToServer() {
        if (this.isSaving || this.pendingUpdates.size === 0) {
            return;
        }
        
        this.isSaving = true;
        const updates = Array.from(this.pendingUpdates.values());
        console.log(`💾 バッチ保存開始: ${updates.length}件の変更`);
        
        try {
            const response = await fetch('/api/progress/batch-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    userId: this.userId,
                    updates: updates
                }),
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    console.log(`✅ バッチ保存完了: ${updates.length}件`);
                    this.pendingUpdates.clear();
                    
                    // キャッシュを無効化（次回アクセス時に最新データを取得）
                    this.invalidateProgressCache();
                } else {
                    console.error('❌ バッチ保存失敗:', data.error);
                }
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('❌ バッチ保存エラー:', error);
            // エラー時は次回の保存でリトライ
        } finally {
            this.isSaving = false;
        }
    }
    
    // 強制保存（ページ離脱時用）
    forceSaveToServer() {
        if (this.pendingUpdates.size === 0) return;
        
        const updates = Array.from(this.pendingUpdates.values());
        const data = JSON.stringify({
            userId: this.userId,
            updates: updates
        });
        
        // sendBeaconで非同期送信（ページ離脱後も実行される）
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/progress/batch-update', data);
            console.log(`🚀 強制保存: ${updates.length}件 (sendBeacon)`);
        }
    }
    
    // 進捗データキャッシュを無効化
    invalidateProgressCache() {
        this.progressDataCache = null;
        this.progressCacheExpiry = null;
        console.log('🗑️ 進捗データキャッシュを無効化しました');
    }
    
    // 最初に表示されるUIの初期化（キャッシュ最適化版）
    async initializeUI() {
        const currentIdentifier = this.getCurrentIdentifier();
        if (currentIdentifier) {
            // 詳細ページの場合 - キャッシュチェック後に初期化
            console.log('📄 Content画面：進捗データ初期化開始');
            
            // 既にデータがキャッシュされているかチェック
            if (this.progressData && Object.keys(this.progressData).length > 0) {
                console.log('🚀 Content画面：キャッシュされた進捗データを使用');
            } else {
                // キャッシュがない場合のみサーバーから読み込み
                await this.loadProgressFromServer();
            }
            
            this.initializeProgressForIdentifier(currentIdentifier);
        } else {
            // ホームページの場合
            setTimeout(async () => {
                await this.updateHomePageProgress();
            }, 100);
        }
    }

    // サーバーから進捗データを読み込み、内部データ構造を構築（キャッシュ機能付き）
    async loadProgressFromServer(forceRefresh = false) {
        try {
            // キャッシュチェック（強制リフレッシュでない場合）
            const now = Date.now();
            if (!forceRefresh && this.progressDataCache && this.progressCacheExpiry && now < this.progressCacheExpiry) {
                console.log('✅ 進捗データキャッシュを使用（API呼び出しスキップ）');
                this.progressData = this.progressDataCache;
                return;
            }
            
            console.log('🔄 サーバーから進捗データを取得中...');
            const response = await fetch(`/api/progress/${this.userId}`);
            if (response.status === 401) {
                this.showUserFriendlyError('認証エラー', 'セッションが期限切れです。再ログインしてください。', true);
                return;
            }
            if (!response.ok) {
                if (response.status === 429) {
                    this.showUserFriendlyError('アクセス制限', 'しばらく時間をおいてから再試行してください。');
                    return;
                }
                throw new Error(`サーバーエラー: ${response.status} ${response.statusText}`);
            }
            const data = await response.json();

            if (data.success) {
                this.progressData = this.formatProgressData(data.progress);
                
                // キャッシュに保存
                this.progressDataCache = this.progressData;
                this.progressCacheExpiry = now + this.PROGRESS_CACHE_DURATION;
                this.lastProgressLoadTime = now;
                
                console.log('✅ サーバーから進捗データ読み込み完了（キャッシュに保存）');
            } else {
                console.error('進捗データの読み込みに失敗しました:', data.error);
                this.progressData = {};
                this.showUserFriendlyError('データ読み込みエラー', 'しばらく待ってから再試行してください。');
            }
        } catch (error) {
            console.error('進捗データ読み込みAPIの呼び出しエラー:', error);
            this.progressData = {};
            
            if (!navigator.onLine) {
                this.showUserFriendlyError('オフライン', 'インターネット接続を確認してください。', false, true);
            } else {
                this.showUserFriendlyError('接続エラー', 'サーバーとの通信に問題があります。', false, true);
            }
        }
    }

    // サーバーからのデータをJSで扱いやすい形式に変換
    // 例: [{'item_identifier': '...', 'level': '...', 'goal_index': 0, 'completed': 1}, ...]
    //  -> { 'identifier': { 'level': [true, false], ... }, ... }
    formatProgressData(records) {
        const formatted = {};
        records.forEach(record => {
            const { item_identifier, level, goal_index, completed } = record;
            if (!formatted[item_identifier]) {
                formatted[item_identifier] = {};
            }
            if (!formatted[item_identifier][level]) {
                // このレベルのゴール配列を、現在のDOMから取得できる最大のインデックスで初期化
                const maxIndex = this.getMaxGoalIndex(item_identifier, level);
                formatted[item_identifier][level] = new Array(maxIndex + 1).fill(false);
            }
            
            // 配列の長さが足りなければ拡張
            while (formatted[item_identifier][level].length <= goal_index) {
                formatted[item_identifier][level].push(false);
            }

            formatted[item_identifier][level][goal_index] = !!completed;
        });
        return formatted;
    }

    // 【削除済み】古いupdateProgressOnServerメソッド
    // 新しいバッチ更新システムに置き換え済み

    // 特定の識別子の進捗データを取得 (内部データから)
    getProgressForIdentifier(identifier) {
        if (!this.progressData[identifier]) {
            // データがない場合は、DOMに基づいて初期化
            this.progressData[identifier] = this.initializeProgressDataFromDOM(identifier);
        }
        return this.progressData[identifier];
    }

    // DOM要素からゴール数を読み取って進捗データを初期化
    initializeProgressDataFromDOM(identifier) {
        return {
            beginnerGoals: new Array(this.getActualGoalCount(identifier, 'beginnerGoals')).fill(false),
            intermediateGoals: new Array(this.getActualGoalCount(identifier, 'intermediateGoals')).fill(false),
            advancedGoals: new Array(this.getActualGoalCount(identifier, 'advancedGoals')).fill(false)
        };
    }
    
    // DOMから特定のレベルのゴール数を取得
    getActualGoalCount(identifier, level) {
        const checkboxes = document.querySelectorAll(`input.progress-checkbox[data-identifier="${identifier}"][data-level="${level}"]`);
        return checkboxes.length;
    }

    // DOMから特定のレベルの最大のインデックスを取得
    getMaxGoalIndex(identifier, level) {
        const checkboxes = document.querySelectorAll(`input.progress-checkbox[data-identifier="${identifier}"][data-level="${level}"]`);
        let maxIndex = -1;
        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index, 10);
            if (index > maxIndex) {
                maxIndex = index;
            }
        });
        return maxIndex;
    }


    // 【削除済み】古いhandleProgressChangeメソッド
    // 新しいhandleProgressChangeOptimizedメソッドに置き換え済み

    // 進捗表示を更新
    updateProgressDisplay(identifier) {
        const progress = this.getProgressForIdentifier(identifier);
        
        ['beginnerGoals', 'intermediateGoals', 'advancedGoals'].forEach(level => {
            const actualTotal = this.getActualGoalCount(identifier, level);
            if (actualTotal === 0) return;

            const goals = progress[level] || [];
            const completed = goals.filter(g => g).length;
            const percentage = Math.round((completed / actualTotal) * 100);

            const progressBar = document.querySelector(`[data-identifier="${identifier}"][data-level="${level}"] .progress-bar-fill`);
            const progressText = document.querySelector(`[data-identifier="${identifier}"][data-level="${level}"] .progress-text`);
            
            if (progressBar) {
                progressBar.style.width = `${percentage}%`;
                progressBar.style.backgroundColor = this.getProgressColor(percentage);
            }
            if (progressText) {
                progressText.textContent = `${completed}/${actualTotal} (${percentage}%)`;
            }
        });

        this.updateOverallProgress(identifier);
        
        // フローティング進捗カードも更新
        if (window.updateFloatingProgress) {
            window.updateFloatingProgress();
        }
    }

    // 全体進捗を更新
    updateOverallProgress(identifier) {
        const progress = this.getProgressForIdentifier(identifier);
        let totalCompleted = 0;
        let totalGoals = 0;
        
        ['beginnerGoals', 'intermediateGoals', 'advancedGoals'].forEach(level => {
            const actualTotal = this.getActualGoalCount(identifier, level);
            const goals = progress[level] || [];
            totalCompleted += goals.filter(g => g).length;
            totalGoals += actualTotal;
        });

        const overallPercentage = totalGoals > 0 ? Math.round((totalCompleted / totalGoals) * 100) : 0;
        
        const overallBar = document.querySelector(`[data-identifier="${identifier}"] .overall-progress-bar .progress-bar-fill`);
        const overallText = document.querySelector(`[data-identifier="${identifier}"] .overall-progress-text`);
        
        if (overallBar) {
            overallBar.style.width = `${overallPercentage}%`;
            overallBar.style.backgroundColor = this.getProgressColor(overallPercentage);
        }
        if (overallText) {
            overallText.textContent = `${totalCompleted}/${totalGoals} (${overallPercentage}%)`;
        }
    }

    // トップページのカードに進捗を表示（キャッシュ最適化版）
    async updateHomePageProgress(forceRefresh = false) {
        // キャッシュされたデータがあるかチェック
        if (!forceRefresh && this.progressData && Object.keys(this.progressData).length > 0) {
            console.log('🚀 ホーム画面：キャッシュされた進捗データを使用');
        } else {
            // キャッシュがない場合のみサーバーから読み込み
            await this.loadProgressFromServer(forceRefresh);
        }

        const cards = document.querySelectorAll('.identifier-card');
        cards.forEach(card => {
            const identifier = card.getAttribute('data-identifier');
            if (identifier) {
                const progress = this.getProgressForCard(identifier);
                this.addProgressToCard(card, progress, identifier);
            }
        });
        // 全体統計も更新
        await this.updateOverallStatistics();
        
        // フローティング進捗カードも更新
        if (window.updateFloatingProgress) {
            window.updateFloatingProgress();
        }
        
        // 進捗ダッシュボードも更新
        if (window.updateProgressDashboard) {
            window.updateProgressDashboard();
        }
    }

    // カード用の進捗データを計算 (改修版)
    getProgressForCard(identifier) {
        const cardElement = document.querySelector(`.identifier-card[data-identifier="${identifier}"]`);
        const totalGoals = cardElement ? parseInt(cardElement.dataset.totalGoals, 10) : 0;

        const progress = this.progressData[identifier];
        if (!progress || totalGoals === 0) {
            return { percentage: 0, completed: 0, total: totalGoals };
        }

        let totalCompleted = 0;
        ['beginnerGoals', 'intermediateGoals', 'advancedGoals'].forEach(level => {
            if (progress[level]) {
                totalCompleted += progress[level].filter(g => g).length;
            }
        });

        const percentage = Math.round((totalCompleted / totalGoals) * 100);
        return { percentage, completed: totalCompleted, total: totalGoals };
    }
    
    // 詳細ページの進捗UIを初期化
    initializeProgressForIdentifier(identifier) {
        const progress = this.getProgressForIdentifier(identifier);
        
        ['beginnerGoals', 'intermediateGoals', 'advancedGoals'].forEach(level => {
            const goals = progress[level] || [];
            goals.forEach((isCompleted, index) => {
                const checkbox = document.querySelector(`[data-identifier="${identifier}"][data-level="${level}"][data-index="${index}"]`);
                if (checkbox) {
                    checkbox.checked = isCompleted;
                }
            });
        });

        this.updateProgressDisplay(identifier);
    }

    // --- 以下、UI表示関連のヘルパー関数 (変更なし) ---
    
    getProgressColor(percentage) {
        if (percentage >= 80) return '#4CAF50';
        if (percentage >= 60) return '#FF9800';
        if (percentage >= 40) return '#2196F3';
        if (percentage >= 20) return '#FFC107';
        return '#e0e0e0';
    }

    showProgressNotification(isCompleted) {
        const message = isCompleted ? '🎉 目標を達成しました！' : '📝 目標のチェックを外しました';
        this.showNotification(message, isCompleted ? 'success' : 'info');
    }

    showNotification(message, type) {
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            console.log(`Notification (${type}): ${message}`);
        }
    }

    // ユーザーフレンドリーなエラー表示
    showUserFriendlyError(title, message, showLogin = false, showRetry = false) {
        // 既存のエラーモーダルがあれば削除
        const existingModal = document.getElementById('errorModal');
        if (existingModal) {
            existingModal.remove();
        }

        const modal = document.createElement('div');
        modal.id = 'errorModal';
        modal.className = 'error-modal';
        modal.innerHTML = `
            <div class="error-modal-content">
                <div class="error-modal-header">
                    <div class="error-icon">
                        <i class="fas fa-exclamation-circle"></i>
                    </div>
                    <h3>${title}</h3>
                </div>
                <div class="error-modal-body">
                    <p>${message}</p>
                </div>
                <div class="error-modal-footer">
                    ${showLogin ? '<button class="error-btn primary" onclick="window.location.href=\'/login\'">ログインページへ</button>' : ''}
                    ${showRetry ? '<button class="error-btn secondary" onclick="window.location.reload()">再試行</button>' : ''}
                    <button class="error-btn secondary" onclick="closeErrorModal()">閉じる</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('show'), 100);

        // 自動で閉じる（ログイン・再試行が不要な場合）
        if (!showLogin && !showRetry) {
            setTimeout(() => {
                if (modal.parentNode) {
                    modal.classList.remove('show');
                    setTimeout(() => modal.remove(), 300);
                }
            }, 5000);
        }
    }

    // エラーモーダルを閉じる（グローバル関数）
    closeErrorModal() {
        const modal = document.getElementById('errorModal');
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    }
    
    getCurrentIdentifier() {
        const breadcrumb = document.querySelector('.breadcrumb-current');
        return breadcrumb ? breadcrumb.textContent.trim() : null;
    }

    // (注意) このリセットは現在サーバーと同期していません
    resetProgress(identifier) {
        if (confirm('この項目の進捗をリセットしますか？ (注意: ページを再読み込みすると元に戻ります)')) {
            delete this.progressData[identifier];
            
            const checkboxes = document.querySelectorAll(`[data-identifier="${identifier}"].progress-checkbox`);
            checkboxes.forEach(cb => cb.checked = false);
            
            this.updateProgressDisplay(identifier);
            this.showNotification('🔄 進捗をリセットしました (UI上のみ)', 'info');
        }
    }
    
    // --- ホームページ用の統計関数 ---
    
    async getStatistics() {
        console.log('🔍 [DEBUG] getStatistics開始');
        console.log('🔍 [DEBUG] this.progressData:', this.progressData);
        console.log('🔍 [DEBUG] this.userId:', this.userId);
        
        let completedGoals = 0;
        let achievedIdentifiers = 0;
        let totalIdentifiers = 0;
        let totalGoals = 0;

        try {
            // キャッシュチェック
            const now = Date.now();
            if (this.statsCache && this.statsCacheExpiry && now < this.statsCacheExpiry) {
                console.log('🔍 [DEBUG] 統計データキャッシュヒット');
                totalIdentifiers = this.statsCache.totalIdentifiers;
                totalGoals = this.statsCache.totalGoals;
            } else {
                console.log('🔍 [DEBUG] API統計データ取得開始');
                const response = await fetch('/api/progress-stats');
                const data = await response.json();
                console.log('🔍 [DEBUG] API統計レスポンス:', data);
                if (data.success) {
                    totalIdentifiers = data.totalIdentifiers;
                    totalGoals = data.totalGoals;
                    
                    // キャッシュに保存
                    this.statsCache = { totalIdentifiers, totalGoals };
                    this.statsCacheExpiry = now + this.STATS_CACHE_DURATION;
                    console.log('🔍 [DEBUG] API統計データをキャッシュ:', { totalIdentifiers, totalGoals });
                }
            }
        } catch (error) {
            console.error('❌ [DEBUG] 統計API呼び出しエラー:', error);
        }

        console.log('🔍 [DEBUG] progressData処理開始');
        console.log('🔍 [DEBUG] progressDataのキー数:', Object.keys(this.progressData).length);
        
        Object.keys(this.progressData).forEach(identifier => {
            console.log(`🔍 [DEBUG] 処理中のidentifier: ${identifier}`);
            const progress = this.getProgressForCard(identifier);
            console.log(`🔍 [DEBUG] ${identifier}の進捗:`, progress);
            completedGoals += progress.completed;
            if (progress.percentage > 50) {
                achievedIdentifiers++;
                console.log(`🔍 [DEBUG] ${identifier}は50%超過で達成済み`);
            }
        });

        const overallPercentage = totalIdentifiers > 0 ? Math.round((achievedIdentifiers / totalIdentifiers) * 100) : 0;
        
        const result = {
            totalIdentifiers,
            achievedIdentifiers,
            completedGoals,
            totalGoals,
            overallPercentage
        };
        
        console.log('🔍 [DEBUG] getStatistics結果:', result);
        return result;
    }

    addProgressToCard(card, progress, identifier) {
        let existingProgress = card.querySelector('.card-progress');
        if (existingProgress) existingProgress.remove();

        const progressContainer = document.createElement('div');
        progressContainer.className = 'card-progress';
        
        progressContainer.innerHTML = `
            <div class="card-progress-info">
                <span class="card-progress-text">${progress.completed}/${progress.total} (${progress.percentage}%)</span>
                <div class="card-progress-bar">
                    <div class="card-progress-fill" style="width: ${progress.percentage}%; background-color: ${this.getProgressColor(progress.percentage)};"></div>
                </div>
            </div>
        `;

        if (progress.percentage >= 50) {
            const badgeClass = progress.percentage >= 80 ? 'high-achievement' : 'good-progress';
            const icon = progress.percentage >= 80 ? 'fa-trophy' : 'fa-star';
            const badge = document.createElement('div');
            badge.className = `achievement-badge ${badgeClass}`;
            badge.innerHTML = `<i class="fas ${icon}"></i>`;
            progressContainer.appendChild(badge);
            card.classList.add(`${badgeClass}-card`);
        } else {
            card.classList.remove('high-achievement-card', 'good-progress-card');
        }
        
        card.querySelector('.card-content').appendChild(progressContainer);
    }

    async updateOverallStatistics() {
        const stats = await this.getStatistics();
        const progressMessage = this.getProgressMessage(stats.overallPercentage);
        
        let compactContainer = document.querySelector('#progressSummaryCompact');
        if (compactContainer) {
            compactContainer.innerHTML = `
                <div class="progress-compact-display">
                    <div class="progress-circle-mini" style="--progress-angle: ${stats.overallPercentage * 3.6}deg;">
                        <span class="progress-percentage-mini">${stats.overallPercentage}%</span>
                    </div>
                    <div class="progress-info-mini">
                        <div class="progress-text-mini">
                            <span class="progress-icon-mini">${progressMessage.icon}</span>
                            <span class="achievement-mini">${stats.achievedIdentifiers}/${stats.totalIdentifiers}項目達成</span>
                        </div>
                        <div class="progress-message-mini">${progressMessage.message}</div>
                    </div>
                </div>
            `;
        }
    }

    // 全体統計を取得 (フローティング進捗カード用)
    async getOverallStats() {
        return await this.getStatistics();
    }

    getProgressMessage(percentage) {
        if (percentage >= 95) return { icon: '🎉', message: '完璧です！素晴らしい成果！' };
        if (percentage >= 90) return { icon: '🏆', message: 'もうすぐ完成！最後の一歩！' };
        if (percentage >= 75) return { icon: '⭐', message: '素晴らしい進捗です！' };
        if (percentage >= 50) return { icon: '🌳', message: '順調に成長中！' };
        if (percentage >= 25) return { icon: '🌿', message: '良いスタートです！' };
        if (percentage >= 10) return { icon: '🌱', message: '学習の芽が出てきました！' };
        return { icon: '💪', message: '一緒に頑張りましょう！' };
    }
}

// ページ読み込み時に初期化
document.addEventListener('DOMContentLoaded', function() {
    window.progressManager = new ProgressManager();
    
    // content画面でも進捗を初期化
    if (window.location.pathname.includes('/content/')) {
        console.log('🎯 content画面検出：進捗初期化開始');
        
        setTimeout(async () => {
            console.log('🔄 content画面進捗初期化実行');
            
            if (window.progressManager && window.progressManager.userId) {
                console.log('✅ progressManager利用可能、データ読み込み開始');
                try {
                    await window.progressManager.loadProgressFromServer();
                    console.log('✅ サーバーから進捗データ読み込み完了');
                    
                    // フローティング進捗カードを更新
                    if (window.updateFloatingProgress) {
                        await window.updateFloatingProgress();
                        // console.log('✅ フローティング進捗カード更新完了');
                    }
                } catch (error) {
                    console.error('❌ content画面進捗初期化エラー:', error);
                }
            } else {
                console.warn('⚠️ progressManager未初期化 (content画面)');
            }
        }, 1500);
    }
});
