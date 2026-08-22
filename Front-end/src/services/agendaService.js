import { getApiBase, getJsonHeaders } from './apiConfig';


const API_BASE = getApiBase();


async function apiResponse(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.detail ?? 'No pudimos completar la operación.');
        error.status = response.status;
        error.data = errorData;
        throw error;
    }
    return response;
}


async function apiFetch(path, options = {}) {
    const response = await apiResponse(path, options);
    if (response.status === 204) return null;
    return response.json();
}


function buildQueryString(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
            params.append(key, value);
        }
    });
    const query = params.toString();
    return query ? `?${query}` : '';
}


export async function getSessions() {
    const data = await apiFetch('/agenda');
    return data.sessions ?? [];
}


export async function filterSessions({ day, modality, eventType, room, venueId, search } = {}) {
    const query = buildQueryString({
        day,
        modality,
        event_type: eventType,
        salon: venueId ? undefined : room,
        venue_id: venueId,
        search,
    });
    const data = await apiFetch(`/agenda${query}`);
    return data.sessions ?? [];
}


export function getSessionById(sessionId) {
    return apiFetch(`/agenda/${sessionId}`);
}


export async function getAgendaConfiguration() {
    const response = await apiResponse('/agenda/config');
    const data = await response.json();
    return { ...data, etag: response.headers.get('ETag') };
}


export async function updateAgendaConfiguration(configuration, etag) {
    const response = await apiResponse('/agenda/config', {
        method: 'PUT',
        headers: { 'If-Match': etag },
        body: JSON.stringify(configuration),
    });
    const data = await response.json();
    return { ...data, etag: response.headers.get('ETag') };
}


export async function getConferenceDays() {
    const configuration = await getAgendaConfiguration();
    return configuration.conference_days.map((value, index) => {
        const [year, month, day] = value.split('-').map(Number);
        return {
            value,
            label: new Intl.DateTimeFormat('es-CO', {
                month: 'short', day: 'numeric', timeZone: 'UTC',
            }).format(new Date(Date.UTC(year, month - 1, day, 12))),
            ordinal: index + 1,
        };
    });
}


export function getRegisteredSessions() {
    return apiFetch('/agenda/me/registered');
}


export function toggleRegistration(sessionId) {
    return apiFetch(`/agenda/${sessionId}/register`, { method: 'POST' });
}


export function createSession(data) {
    return apiFetch('/agenda', { method: 'POST', body: JSON.stringify(data) });
}


export function updateSession(sessionId, data) {
    return apiFetch(`/agenda/${sessionId}`, { method: 'PUT', body: JSON.stringify(data) });
}


export function deleteSession(sessionId) {
    return apiFetch(`/agenda/${sessionId}`, { method: 'DELETE' });
}


export function toggleLinkVerified(sessionId) {
    return apiFetch(`/agenda/${sessionId}/verify-link`, { method: 'PATCH' });
}


export async function getVenues({ manage = false } = {}) {
    const data = await apiFetch(`/agenda/venues${manage ? '/manage' : ''}`);
    return data.venues ?? [];
}


export function getVenue(venueId) {
    return apiFetch(`/agenda/venues/${venueId}`);
}


export function createVenue(data) {
    return apiFetch('/agenda/venues', { method: 'POST', body: JSON.stringify(data) });
}


export function updateVenue(venueId, data) {
    return apiFetch(`/agenda/venues/${venueId}`, { method: 'PATCH', body: JSON.stringify(data) });
}


export function deleteVenue(venueId) {
    return apiFetch(`/agenda/venues/${venueId}`, { method: 'DELETE' });
}


export function createVenueResource(venueId, data) {
    return apiFetch(`/agenda/venues/${venueId}/resources`, {
        method: 'POST', body: JSON.stringify(data),
    });
}


export function updateVenueResource(venueId, resourceId, data) {
    return apiFetch(`/agenda/venues/${venueId}/resources/${resourceId}`, {
        method: 'PATCH', body: JSON.stringify(data),
    });
}


export function deleteVenueResource(venueId, resourceId) {
    return apiFetch(`/agenda/venues/${venueId}/resources/${resourceId}`, { method: 'DELETE' });
}


export function issueAttendanceToken(sessionId, options = {}) {
    return apiFetch(`/agenda/${sessionId}/attendance-token`, {
        method: 'POST', body: JSON.stringify(options),
    });
}


export function confirmAttendance(sessionId, token) {
    return apiFetch(`/agenda/${sessionId}/attendance/check-in`, {
        method: 'POST', body: JSON.stringify({ token }),
    });
}


export async function getSessionAttendance(sessionId, { includeRevoked = false } = {}) {
    const data = await apiFetch(`/agenda/${sessionId}/attendance${buildQueryString({ include_revoked: includeRevoked })}`);
    return data.items ?? [];
}


export async function getMyAttendance() {
    const data = await apiFetch('/agenda/me/attendance');
    return data.items ?? [];
}


export function confirmManualAttendance(sessionId, userId, reason) {
    return apiFetch(`/agenda/${sessionId}/attendance/manual`, {
        method: 'POST', body: JSON.stringify({ user_id: userId, reason }),
    });
}


export function revokeAttendance(sessionId, attendanceId, reason) {
    return apiFetch(`/agenda/${sessionId}/attendance/${attendanceId}/revoke`, {
        method: 'PATCH', body: JSON.stringify({ reason }),
    });
}


export function getSpeakerById() {
    return null;
}


export function isRecentChange(timestampISO, withinMinutes = 30) {
    if (!timestampISO) return false;
    const timestamp = new Date(timestampISO).getTime();
    return Number.isFinite(timestamp) && Date.now() - timestamp <= withinMinutes * 60 * 1000;
}
