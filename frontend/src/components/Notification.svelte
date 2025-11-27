<script context="module">
    // Notification store class
    class NotificationStore {
        constructor() {
            this.notifications = [];
            this.subscribers = [];
            this.nextId = 1;
        }

        subscribe(callback) {
            this.subscribers.push(callback);
            callback(this.notifications);

            return () => {
                const index = this.subscribers.indexOf(callback);
                if (index !== -1) {
                    this.subscribers.splice(index, 1);
                }
            };
        }

        notify() {
            this.subscribers.forEach(callback => callback(this.notifications));
        }

        add(message, type = 'info', duration = 5000) {
            const notification = {
                id: this.nextId++,
                message,
                type,
                timestamp: Date.now()
            };

            this.notifications = [...this.notifications, notification];
            this.notify();

            if (duration > 0) {
                setTimeout(() => {
                    this.remove(notification.id);
                }, duration);
            }

            return notification.id;
        }

        remove(id) {
            this.notifications = this.notifications.filter(n => n.id !== id);
            this.notify();
        }

        clear() {
            this.notifications = [];
            this.notify();
        }

        success(message, duration = 5000) {
            return this.add(message, 'success', duration);
        }

        error(message, duration = 0) {
            return this.add(message, 'error', duration);
        }

        warning(message, duration = 7000) {
            return this.add(message, 'warning', duration);
        }

        info(message, duration = 5000) {
            return this.add(message, 'info', duration);
        }
    }

    // Create global singleton notification store
    const notificationStore = new NotificationStore();

    // Export notification methods for easy use
    export function showSuccess(message, duration) {
        return notificationStore.success(message, duration);
    }

    export function showError(message, duration) {
        return notificationStore.error(message, duration);
    }

    export function showWarning(message, duration) {
        return notificationStore.warning(message, duration);
    }

    export function showInfo(message, duration) {
        return notificationStore.info(message, duration);
    }

    export function clearNotifications() {
        notificationStore.clear();
    }
</script>

<!-- T041: Add success/error notifications component -->
<script>
    import { onDestroy } from 'svelte';
    import { fade, fly } from 'svelte/transition';

    // Component state
    let notifications = [];

    // Subscribe to store
    const unsubscribe = notificationStore.subscribe(value => {
        notifications = value;
    });

    // Cleanup on destroy
    onDestroy(() => {
        unsubscribe();
    });

    // Remove notification
    function removeNotification(id) {
        notificationStore.remove(id);
    }

    // Get icon based on type
    function getIcon(type) {
        switch (type) {
            case 'success':
                return '✓';
            case 'error':
                return '✗';
            case 'warning':
                return '!';
            case 'info':
            default:
                return 'ℹ';
        }
    }

    // Get class based on type
    function getClass(type) {
        return `notification notification-${type}`;
    }
</script>

<div class="notification-container">
    {#each notifications as notification (notification.id)}
        <div
            class={getClass(notification.type)}
            in:fly={{ y: -20, duration: 300 }}
            out:fade={{ duration: 200 }}
        >
            <div class="notification-icon">
                {getIcon(notification.type)}
            </div>
            <div class="notification-content">
                <div class="notification-message">
                    {notification.message}
                </div>
            </div>
            <button
                class="notification-close"
                on:click={() => removeNotification(notification.id)}
                aria-label="Close notification"
            >
                ×
            </button>
        </div>
    {/each}
</div>

<style>
    .notification-container {
        position: fixed;
        top: 80px;
        right: 24px;
        z-index: 9999;
        max-width: 420px;
        pointer-events: none;
    }

    .notification {
        display: flex;
        align-items: flex-start;
        margin-bottom: 12px;
        padding: 16px 18px;
        background: white;
        border-radius: 14px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12), 0 4px 12px rgba(0, 0, 0, 0.08);
        pointer-events: auto;
        transition: all 0.3s ease;
        backdrop-filter: blur(10px);
    }

    .notification:hover {
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15), 0 6px 16px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    .notification-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        margin-right: 14px;
        border-radius: 50%;
        font-weight: bold;
        font-size: 14px;
        flex-shrink: 0;
    }

    .notification-content {
        flex: 1;
        min-width: 0;
    }

    .notification-message {
        font-size: 14px;
        line-height: 1.5;
        word-wrap: break-word;
        color: #1e293b;
        font-weight: 500;
    }

    .notification-close {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        margin-left: 12px;
        background: transparent;
        border: none;
        border-radius: 8px;
        font-size: 20px;
        line-height: 1;
        color: #94a3b8;
        cursor: pointer;
        transition: all 0.2s;
        flex-shrink: 0;
    }

    .notification-close:hover {
        background: #f1f5f9;
        color: #475569;
    }

    /* Success notification */
    .notification-success {
        border-left: 4px solid #10b981;
        background: linear-gradient(135deg, #ffffff 0%, #ecfdf5 100%);
    }

    .notification-success .notification-icon {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
    }

    /* Error notification */
    .notification-error {
        border-left: 4px solid #ef4444;
        background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%);
    }

    .notification-error .notification-icon {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
    }

    /* Warning notification */
    .notification-warning {
        border-left: 4px solid #f59e0b;
        background: linear-gradient(135deg, #ffffff 0%, #fffbeb 100%);
    }

    .notification-warning .notification-icon {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
    }

    /* Info notification */
    .notification-info {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
    }

    .notification-info .notification-icon {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    }

    /* Responsive design */
    @media (max-width: 480px) {
        .notification-container {
            left: 16px;
            right: 16px;
            top: 72px;
            max-width: none;
        }

        .notification {
            padding: 14px 16px;
        }
    }
</style>