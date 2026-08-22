// ============================================================
// Servicio de Usuarios — CONIITI Front-end
// Centraliza las llamadas HTTP para la gestión de cuentas staff.
// Solo utilizado desde el panel del superusuario.
// ============================================================

import { getApiBase, getJsonHeaders } from './apiConfig';

const API_BASE = getApiBase();

/**
 * Realiza una solicitud autenticada al API incluyendo cookies HttpOnly.
 *
 * @param {string} path - Ruta relativa del endpoint
 * @param {RequestInit} options - Opciones del fetch
 * @returns {Promise<any>}
 */
async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail ?? 'No se pudo completar la solicitud. Inténtalo de nuevo.');
    }

    if (response.status === 204) return null;

    return response.json();
}


// =============================================================
// Sección: CRUD de cuentas staff
// =============================================================

/**
 * Obtiene la lista de todos los usuarios con rol staff.
 *
 * @returns {Promise<Array>}
 */
export async function listStaff() {
    return apiFetch('/users/staff');
}

/**
 * Crea una nueva cuenta de staff.
 *
 * @param {{ full_name: string, email: string, institution?: string, password: string }} data
 */
export async function createStaff(data) {
    return apiFetch('/users/staff', {
        method: 'POST',
        body: JSON.stringify({
            ...data,
            role: 'staff',
        }),
    });
}

/**
 * Actualiza los datos de una cuenta staff existente.
 *
 * @param {string} userId - UUID del usuario a actualizar
 * @param {object} data - Campos a actualizar (todos opcionales)
 */
export async function updateStaff(userId, data) {
    return apiFetch(`/users/staff/${userId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

/**
 * Elimina permanentemente una cuenta staff.
 *
 * @param {string} userId - UUID del usuario a eliminar
 */
export async function deleteStaff(userId) {
    return apiFetch(`/users/staff/${userId}`, {
        method: 'DELETE',
    });
}


// =============================================================
// Perfil propio y administracion global de perfiles
// =============================================================

export async function getOwnProfile() {
    return apiFetch('/users/me');
}

export async function updateOwnProfile(data) {
    return apiFetch('/users/me', {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

export async function listProfiles({ search = '', role = '', isActive = '', page = 1, pageSize = 25 } = {}) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search.trim()) params.set('search', search.trim());
    if (role) params.set('role', role);
    if (isActive !== '') params.set('is_active', String(isActive));
    return apiFetch(`/users/admin/profiles?${params.toString()}`);
}

export async function updateProfileAsAdmin(userId, data) {
    return apiFetch(`/users/admin/profiles/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}


// =============================================================
// Grupos y membresias
// =============================================================

export async function listGroups({ search = '', page = 1, pageSize = 50 } = {}) {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search.trim()) params.set('search', search.trim());
    return apiFetch(`/users/groups?${params.toString()}`);
}

export async function listMyGroups() {
    return apiFetch('/users/me/groups');
}

export async function getGroup(groupId) {
    return apiFetch(`/users/groups/${groupId}`);
}

export async function createGroup(data) {
    return apiFetch('/users/groups', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateGroup(groupId, data) {
    return apiFetch(`/users/groups/${groupId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

export async function deactivateGroup(groupId) {
    return apiFetch(`/users/groups/${groupId}`, { method: 'DELETE' });
}

export async function listGroupMembers(groupId) {
    return apiFetch(`/users/groups/${groupId}/members`);
}

export async function addGroupMember(groupId, data) {
    return apiFetch(`/users/groups/${groupId}/members`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateGroupMember(groupId, userId, data) {
    return apiFetch(`/users/groups/${groupId}/members/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

export async function removeGroupMember(groupId, userId) {
    return apiFetch(`/users/groups/${groupId}/members/${userId}`, { method: 'DELETE' });
}

export async function listGroupAudit(groupId, limit = 100) {
    return apiFetch(`/users/groups/${groupId}/audit?limit=${limit}`);
}


// =============================================================
// Comite (backend autoritativo; no cards CMS duplicadas)
// =============================================================

export async function listCommitteeMembers(activeOnly = false) {
    return apiFetch(`/committees/members?active_only=${String(activeOnly)}`);
}

export async function createCommitteeMember(data) {
    return apiFetch('/committees/members', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function updateCommitteeMember(memberId, data) {
    return apiFetch(`/committees/members/${memberId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

export async function deleteCommitteeMember(memberId) {
    return apiFetch(`/committees/members/${memberId}`, { method: 'DELETE' });
}
