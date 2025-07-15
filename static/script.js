// アニメーション効果
document.addEventListener('DOMContentLoaded', function() {
    // フェードインアニメーション
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // アニメーション対象要素を監視
    const animateElements = document.querySelectorAll('.identifier-card, .info-card, .content-type-card');
    animateElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

    // スムーズスクロール
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // 検索フィルタリング（識別子一覧ページ用）
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const cards = document.querySelectorAll('.identifier-card');
            
            cards.forEach(card => {
                const identifier = card.querySelector('.card-title').textContent.toLowerCase();
                if (identifier.includes(searchTerm)) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }

    // ローディング効果
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="loading-spinner">
            <i class="fas fa-spinner fa-spin"></i>
            <p>読み込み中...</p>
        </div>
    `;
    
    // ローディング用CSS
    const loadingStyles = `
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(102, 126, 234, 0.9);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }
        
        .loading-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        
        .loading-spinner {
            text-align: center;
            color: white;
        }
        
        .loading-spinner i {
            font-size: 3rem;
            margin-bottom: 1rem;
            display: block;
        }
        
        .loading-spinner p {
            font-size: 1.2rem;
            font-weight: 500;
        }
    `;
    
    const styleSheet = document.createElement('style');
    styleSheet.textContent = loadingStyles;
    document.head.appendChild(styleSheet);
    document.body.appendChild(loadingOverlay);

    // ページ遷移時のローディング
    const navigationLinks = document.querySelectorAll('a:not([href^="#"]):not([href^="javascript:"])');
    navigationLinks.forEach(link => {
        link.addEventListener('click', function() {
            loadingOverlay.classList.add('active');
        });
    });

    // ページ読み込み完了時にローディングを隠す
    window.addEventListener('load', function() {
        setTimeout(() => {
            loadingOverlay.classList.remove('active');
        }, 300);
    });
});

// ユーティリティ関数
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" class="notification-close">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // 通知用CSS（動的に追加）
    if (!document.querySelector('#notification-styles')) {
        const notificationStyles = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 1rem 1.5rem;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                display: flex;
                align-items: center;
                gap: 10px;
                z-index: 10000;
                max-width: 300px;
                animation: slideInRight 0.3s ease;
            }
            
            .notification-success { border-left: 4px solid #4CAF50; }
            .notification-error { border-left: 4px solid #F44336; }
            .notification-info { border-left: 4px solid #2196F3; }
            
            .notification-close {
                background: none;
                border: none;
                color: #666;
                cursor: pointer;
                font-size: 0.9rem;
                margin-left: auto;
            }
            
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        
        const styleSheet = document.createElement('style');
        styleSheet.id = 'notification-styles';
        styleSheet.textContent = notificationStyles;
        document.head.appendChild(styleSheet);
    }
    
    document.body.appendChild(notification);
    
    // 3秒後に自動削除
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 3000);
}

// コピー機能
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('クリップボードにコピーしました', 'success');
    }).catch(() => {
        showNotification('コピーに失敗しました', 'error');
    });
}

// チュートリアル機能
let currentTutorialStep = 1;
const totalTutorialSteps = 4;

function showTutorial() {
    console.log('🎬 showTutorial関数実行');
    const modal = document.getElementById('tutorialModal');
    console.log('📋 modalElement:', modal);
    if (modal) {
        console.log('✅ モーダル要素が見つかりました');
        modal.style.display = 'flex';
        modal.classList.add('show');
        currentTutorialStep = 1;
        updateTutorialDisplay();
        
        // モーダル表示後にイベントリスナーを再設定
        setTimeout(() => {
            setupTutorialEventListeners();
        }, 100);
        
        console.log('🎯 チュートリアル表示完了');
    } else {
        console.error('❌ tutorialModal要素が見つかりません');
    }
}

function closeTutorial() {
    const modal = document.getElementById('tutorialModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300); // CSSトランジション完了後に非表示
    }
}

function goToTutorialStep(step) {
    if (step >= 1 && step <= totalTutorialSteps) {
        currentTutorialStep = step;
        updateTutorialDisplay();
    }
}

function nextTutorialStep() {
    console.log('▶️ nextTutorialStep実行 - 現在:', currentTutorialStep, '/', totalTutorialSteps);
    if (currentTutorialStep < totalTutorialSteps) {
        currentTutorialStep++;
        console.log('✅ 次のステップに進む:', currentTutorialStep);
        updateTutorialDisplay();
    } else {
        console.log('⚠️ 最終ステップのため進めません');
    }
}

function previousTutorialStep() {
    console.log('◀️ previousTutorialStep実行 - 現在:', currentTutorialStep);
    if (currentTutorialStep > 1) {
        currentTutorialStep--;
        console.log('✅ 前のステップに戻る:', currentTutorialStep);
        updateTutorialDisplay();
    } else {
        console.log('⚠️ 最初のステップのため戻れません');
    }
}

function updateTutorialDisplay() {
    console.log('🔄 updateTutorialDisplay実行 - currentStep:', currentTutorialStep);
    
    // ステップの表示/非表示を更新
    const steps = document.querySelectorAll('.tutorial-step');
    console.log('📋 ステップ要素数:', steps.length);
    steps.forEach((step, index) => {
        const isActive = index + 1 === currentTutorialStep;
        step.classList.toggle('active', isActive);
        console.log(`  ステップ${index + 1}: ${isActive ? 'アクティブ' : '非アクティブ'}`);
    });

    // ドットの状態を更新
    const dots = document.querySelectorAll('.progress-dots .dot');
    console.log('🔘 ドット要素数:', dots.length);
    dots.forEach((dot, index) => {
        const isActive = index + 1 === currentTutorialStep;
        dot.classList.toggle('active', isActive);
        console.log(`  ドット${index + 1}: ${isActive ? 'アクティブ' : '非アクティブ'}`);
    });

    // ボタンの状態を更新
    const prevBtn = document.getElementById('tutorialPrev');
    const nextBtn = document.getElementById('tutorialNext');
    const startBtn = document.getElementById('tutorialStart');
    
    console.log('🔘 ボタン要素:', { prevBtn: !!prevBtn, nextBtn: !!nextBtn, startBtn: !!startBtn });

    if (prevBtn) {
        prevBtn.disabled = currentTutorialStep === 1;
        console.log('  前へボタン:', currentTutorialStep === 1 ? '無効' : '有効');
    }
    
    if (currentTutorialStep === totalTutorialSteps) {
        if (nextBtn) nextBtn.style.display = 'none';
        if (startBtn) startBtn.style.display = 'inline-block';
        console.log('  最終ステップ: 次へボタン非表示, 開始ボタン表示');
    } else {
        if (nextBtn) nextBtn.style.display = 'inline-block';
        if (startBtn) startBtn.style.display = 'none';
        console.log('  中間ステップ: 次へボタン表示, 開始ボタン非表示');
    }
}

function startLearning() {
    closeTutorial();
    showNotification('学習を開始しました！頑張りましょう！', 'success');
}

// チュートリアルイベントリスナー設定関数
function setupTutorialEventListeners() {
    console.log('🔧 チュートリアルイベントリスナー設定開始');
    
    // 既存のイベントリスナーをクリア（重複防止）
    const nextBtn = document.getElementById('tutorialNext');
    const prevBtn = document.getElementById('tutorialPrev');
    const startBtn = document.getElementById('tutorialStart');
    const dots = document.querySelectorAll('.progress-dots .dot');
    
    // 次へボタン
    if (nextBtn) {
        nextBtn.replaceWith(nextBtn.cloneNode(true)); // 既存リスナーをクリア
        const newNextBtn = document.getElementById('tutorialNext');
        newNextBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🎯 次へボタンがクリックされました！');
            nextTutorialStep();
        });
        console.log('✅ 次へボタンのイベントリスナー設定完了');
    }
    
    // 前へボタン
    if (prevBtn) {
        prevBtn.replaceWith(prevBtn.cloneNode(true)); // 既存リスナーをクリア
        const newPrevBtn = document.getElementById('tutorialPrev');
        newPrevBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🎯 前へボタンがクリックされました！');
            previousTutorialStep();
        });
        console.log('✅ 前へボタンのイベントリスナー設定完了');
    }
    
    // 学習開始ボタン
    if (startBtn) {
        startBtn.replaceWith(startBtn.cloneNode(true)); // 既存リスナーをクリア
        const newStartBtn = document.getElementById('tutorialStart');
        newStartBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🎯 学習開始ボタンがクリックされました！');
            startLearning();
        });
        console.log('✅ 学習開始ボタンのイベントリスナー設定完了');
    }
    
    // ドットボタン
    dots.forEach((dot, index) => {
        dot.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log(`🎯 ドット${index + 1}がクリックされました！`);
            goToTutorialStep(index + 1);
        });
    });
    console.log(`✅ ${dots.length}個のドットのイベントリスナー設定完了`);
}

// グローバル関数として明示的に露出
window.showTutorial = showTutorial;
window.closeTutorial = closeTutorial;
window.goToTutorialStep = goToTutorialStep;
window.nextTutorialStep = nextTutorialStep;
window.previousTutorialStep = previousTutorialStep;
window.startLearning = startLearning;
window.setupTutorialEventListeners = setupTutorialEventListeners;

// チュートリアル自動表示は一時的に無効化
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 DOMContentLoaded - パス:', window.location.pathname);
    console.log('⚠️ チュートリアル自動表示は現在無効化されています');
    
    // TODO: チュートリアル機能の修正後に再有効化
    // if (window.location.pathname === '/') {
    //     setTimeout(() => {
    //         showTutorial();
    //     }, 1000);
    // }
});