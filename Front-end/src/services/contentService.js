import { getApiBase, getJsonHeaders } from './apiConfig';


const FILES_BASE = `${getApiBase()}/files`;

async function apiFetch(path, options = {}) {
    const response = await fetch(`${FILES_BASE}${path}`, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail ?? 'No se pudo completar la operación de contenido.');
    }
    if (response.status === 204) return null;
    return response.json();
}

// Initial render is intentionally empty. Persistent CMS data is the only source
// of truth; demo cards are never presented as if they were current content.
export function getContentSection() {
    return [];
}

export async function fetchContentSection(section) {
    try {
        const cards = await apiFetch(`/content/cards/${section}?active_only=true`);
        return Array.isArray(cards) ? cards : [];
    } catch {
        return [];
    }
}

export async function fetchContentSectionStrict(section) {
    const cards = await apiFetch(`/content/cards/${section}?active_only=true`);
    return Array.isArray(cards) ? cards : [];
}

export async function fetchAdminContentSection(section) {
    const cards = await apiFetch(`/content/cards/${section}?active_only=false`);
    return Array.isArray(cards) ? cards : [];
}

export function createContentCard(data) {
    return apiFetch('/content/cards', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function updateContentCard(cardId, data) {
    return apiFetch(`/content/cards/${cardId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

export function deleteContentCard(cardId) {
    return apiFetch(`/content/cards/${cardId}`, { method: 'DELETE' });
}
