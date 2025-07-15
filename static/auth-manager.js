/**
 * 認証システム管理用JavaScript
 * ユーザー認証、利用制限、プレミアム機能などを管理
 */

class AuthManager {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    async init() {
        // 登録・ログインページでは認証チェックを無効化
        const currentPath = window.location.pathname;
        if (currentPath.includes('/register') || currentPath.includes('/login')) {
            console.log('📝 登録・ログインページのため、認証チェックを無効化します。');
            return;
        }

        // ページ読み込み時にユーザー情報を取得
        await this.loadCurrentUser();
        this.setupEventListeners();
        this.updateUI();
    }

    async loadCurrentUser() {
        try {
            const response = await fetch('/api/current-user');
            const data = await response.json();
            
            if (data.success) {
                this.currentUser = data.user;
            } else {
                this.currentUser = null;
            }
        } catch (error) {
            console.error('ユーザー情報の取得に失敗しました:', error);
            this.currentUser = null;
        }
    }

    setupEventListeners() {
        // ログアウトボタン
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.logout();
            });
        }
    }

    updateUI() {
        const loggedInNav = document.getElementById('loggedInNav');
        const notLoggedInNav = document.getElementById('notLoggedInNav');
        
        if (this.currentUser) {
            // ログイン時の表示
            loggedInNav.style.display = 'flex';
            notLoggedInNav.style.display = 'none';
            
            // ユーザー情報の表示
            const userEmail = document.getElementById('userEmail');
            const usageCount = document.getElementById('usageCount');
            const premiumBadge = document.getElementById('premiumBadge');
            
            if (userEmail) userEmail.textContent = this.currentUser.email;
            if (usageCount) usageCount.textContent = `${this.currentUser.free_usage_count}/30`;
            
            if (premiumBadge) {
                premiumBadge.style.display = this.currentUser.is_premium ? 'inline' : 'none';
            }
        } else {
            // 未ログイン時の表示
            loggedInNav.style.display = 'none';
            notLoggedInNav.style.display = 'flex';
        }
    }

    async logout() {
        try {
            window.location.href = '/logout';
        } catch (error) {
            console.error('ログアウトに失敗しました:', error);
        }
    }

    isLoggedIn() {
        return this.currentUser !== null;
    }

    canUseAI() {
        if (!this.currentUser) return false;
        return this.currentUser.is_premium || this.currentUser.free_usage_count < 30;
    }

    showUsageLimitModal() {
        const modal = document.getElementById('usageLimitModal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    closeUsageLimitModal() {
        const modal = document.getElementById('usageLimitModal');
        if (modal) {
            modal.style.display = 'none';
        }
        
        // 認証フォームを非表示
        const activationForm = document.getElementById('activationForm');
        if (activationForm) {
            activationForm.style.display = 'none';
        }
    }

    showActivationForm() {
        const activationForm = document.getElementById('activationForm');
        if (activationForm) {
            activationForm.style.display = 'block';
        }
    }

    async activatePremium() {
        const activationCode = document.getElementById('activationCode').value;
        
        if (!activationCode) {
            alert('認証コードを入力してください。');
            return;
        }

        try {
            const response = await fetch('/api/activate-premium', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ activation_code: activationCode })
            });

            const data = await response.json();
            
            if (data.success) {
                alert('プレミアムアカウントが有効化されました！');
                this.closeUsageLimitModal();
                await this.loadCurrentUser();
                this.updateUI();
            } else {
                alert(data.error || '認証コードが無効です。');
            }
        } catch (error) {
            console.error('認証エラー:', error);
            alert('認証に失敗しました。もう一度お試しください。');
        }
    }

    updateUsageCount(newCount) {
        if (this.currentUser) {
            this.currentUser.free_usage_count = newCount;
            this.updateUI();
        }
    }
}

// グローバル関数（HTMLのonclick属性から呼び出し用）
function closeUsageLimitModal() {
    window.authManager.closeUsageLimitModal();
}

function showActivationForm() {
    window.authManager.showActivationForm();
}

function activatePremium() {
    window.authManager.activatePremium();
}

// グローバルインスタンス
window.authManager = new AuthManager();

// 他のスクリプトからアクセスできるようにexport
window.AuthManager = AuthManager;