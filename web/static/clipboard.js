/**
 * 剪贴板工具 —— 兼容非安全上下文（内网 HTTP）的复制实现。
 *
 * navigator.clipboard 只在安全上下文（HTTPS / localhost）存在，
 * 通过 http://<NAS内网IP> 访问时它是 undefined。此时必须走
 * document.execCommand('copy') 兜底，否则会同步抛 TypeError。
 */
(function () {
    'use strict';

    function fallbackCopy(text) {
        var ta = null;
        var active = document.activeElement;
        try {
            ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.setAttribute('aria-hidden', 'true');
            ta.tabIndex = -1;
            ta.style.position = 'fixed';
            ta.style.top = '0';
            ta.style.left = '0';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            ta.setSelectionRange(0, ta.value.length);
            return document.execCommand('copy');
        } catch (e) {
            return false;
        } finally {
            if (ta && ta.parentNode) {
                ta.parentNode.removeChild(ta);
            }
            // 复制后把焦点还给触发元素，避免键盘用户丢失焦点
            if (active && typeof active.focus === 'function') {
                try { active.focus(); } catch (e) { /* 忽略 */ }
            }
        }
    }

    /**
     * 复制文本，返回 Promise<boolean>（true 表示复制成功）。
     * 任何路径（能力缺失 / API 抛错 / DOM 异常）都不会 reject。
     */
    function copyToClipboard(text) {
        try {
            if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                return navigator.clipboard.writeText(text).then(
                    function () { return true; },
                    function () { return fallbackCopy(text); }
                ).catch(function () {
                    return false;
                });
            }
            return Promise.resolve(fallbackCopy(text));
        } catch (e) {
            return Promise.resolve(false);
        }
    }

    window.copyToClipboard = copyToClipboard;
})();
