// ============================================================
// Servicio de Autenticacion - CONIITI Front-end
// Consume exclusivamente auth-service a traves del gateway.
// ============================================================

import { getApiBase, getJsonHeaders } from './apiConfig';

const API_BASE = getApiBase();
const API_ORIGIN = import.meta.env.VITE_API_ORIGIN ?? '';
const AUTH_BASE = `${API_BASE}/auth`;

function normalizeUserRole(userData) {
    if (!userData || typeof userData !== 'object') {
        return userData;
    }

    if (typeof userData.role !== 'string') {
        return userData;
    }

    return {
        ...userData,
        role: userData.role.trim().toLowerCase(),
    };
}

function getApiOrigin() {
    if (API_ORIGIN) {
        return API_ORIGIN.replace(/\/$/, '');
    }

    return window.location.origin;
}

function buildAuthUrl(path) {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${AUTH_BASE}${normalizedPath}`;
}

function buildBrowserAuthUrl(path) {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    if (/^https?:\/\//i.test(AUTH_BASE)) {
        return `${AUTH_BASE}${normalizedPath}`;
    }
    return `${getApiOrigin()}${AUTH_BASE}${normalizedPath}`;
}

function buildOtpDebugStorageKey(email, purpose) {
    return `coniiti_otp_debug_${String(email || '').toLowerCase()}_${purpose || 'login'}`;
}

function getValidationErrorMessage(errorItem) {
    const field = Array.isArray(errorItem?.loc) ? errorItem.loc[errorItem.loc.length - 1] : '';

    if (field === 'password' || field === 'new_password') {
        return 'La contrasena debe tener al menos 8 caracteres.';
    }

    if (field === 'email') {
        return 'Ingresa un correo electronico valido.';
    }

    if (field === 'code') {
        return 'El codigo OTP debe tener 6 digitos.';
    }

    return typeof errorItem?.msg === 'string' ? errorItem.msg : null;
}

function getApiErrorMessage(errorData) {
    if (typeof errorData.detail === 'string') {
        return errorData.detail;
    }

    if (Array.isArray(errorData.detail)) {
        const validationMessage = errorData.detail
            .map(getValidationErrorMessage)
            .find(Boolean);

        if (validationMessage) {
            return validationMessage;
        }
    }

    return 'No se pudo completar la solicitud. Intentalo de nuevo.';
}

function hasSessionHint() {
    if (typeof document === 'undefined') {
        return true;
    }

    return document.cookie
        .split(';')
        .map((item) => item.trim())
        .some((item) => item === 'session_hint=1' || item.startsWith('session_hint=1;'));
}

function shouldAttemptSessionRestore() {
    if (typeof window === 'undefined') {
        return true;
    }

    if (hasSessionHint()) {
        return true;
    }

    const protectedPaths = new Set(['/staff', '/superusuario', '/perfil', '/mis-grupos']);
    if (
        protectedPaths.has(window.location.pathname)
        || window.location.pathname.startsWith('/superusuario/')
        || window.location.pathname.startsWith('/staff/')
        || window.location.pathname.startsWith('/mis-grupos/')
    ) {
        return true;
    }

    const params = new URLSearchParams(window.location.search);
    return params.get('oauth') === 'success';
}

export function getMicrosoftLoginUrl() {
    return buildBrowserAuthUrl('/oauth/microsoft');
}

export function getGoogleLoginUrl() {
    return buildBrowserAuthUrl('/oauth/google');
}

async function apiFetch(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(getApiErrorMessage(errorData));
    }

    if (response.status === 204) return null;
    return response.json();
}

export async function register(data) {
    const result = await apiFetch(buildAuthUrl('/register'), {
        method: 'POST',
        body: JSON.stringify(data),
    });
    return normalizeUserRole(result);
}

export async function login(data) {
    const result = await apiFetch(buildAuthUrl('/login'), {
        method: 'POST',
        body: JSON.stringify(data),
    });
    return normalizeUserRole(result);
}

export async function getMe(options = {}) {
    const { force = false } = options;
    if (!force && !shouldAttemptSessionRestore()) {
        return null;
    }

    try {
        const result = await apiFetch(buildAuthUrl('/me'));
        return normalizeUserRole(result);
    } catch {
        return null;
    }
}

export async function logout() {
    return apiFetch(buildAuthUrl('/logout'), { method: 'POST' });
}

export async function verifyOtp(data) {
    const result = await apiFetch(buildAuthUrl('/verify-otp'), {
        method: 'POST',
        body: JSON.stringify(data),
    });
    return normalizeUserRole(result);
}

export function cacheOtpDebugInfo({ email, purpose, debugOtp, message, deliveryMode }) {
    if (typeof window === 'undefined' || !email || !debugOtp) {
        return;
    }

    window.sessionStorage.setItem(
        buildOtpDebugStorageKey(email, purpose),
        JSON.stringify({
            email,
            purpose,
            debugOtp,
            message,
            deliveryMode,
        }),
    );
}

export function getCachedOtpDebugInfo(email, purpose) {
    if (typeof window === 'undefined' || !email) {
        return null;
    }

    const raw = window.sessionStorage.getItem(buildOtpDebugStorageKey(email, purpose));
    if (!raw) {
        return null;
    }

    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

export function clearCachedOtpDebugInfo(email, purpose) {
    if (typeof window === 'undefined' || !email) {
        return;
    }

    window.sessionStorage.removeItem(buildOtpDebugStorageKey(email, purpose));
}

export async function refreshToken() {
    throw new Error('Esta acción ya no está disponible.');
}

export async function forgotPassword(data) {
    return apiFetch(buildAuthUrl('/forgot-password'), {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function resetPassword(data) {
    return apiFetch(buildAuthUrl('/reset-password'), {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function loginWithMicrosoft() {
    window.location.assign(getMicrosoftLoginUrl());
}

export function loginWithGoogle() {
    window.location.assign(getGoogleLoginUrl());
}
