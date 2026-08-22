import { getApiBase, getJsonHeaders } from './apiConfig';


const API_BASE = getApiBase();


async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}/raffles${path}`, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });
    const payload = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload?.detail ?? 'No se pudo completar la operación de sorteos.');
    }
    return payload;
}


export function listRaffles() {
    return request('');
}


export function createRaffle(payload) {
    return request('', { method: 'POST', body: JSON.stringify(payload) });
}


export function lockRaffleSnapshot(raffleId) {
    return request(`/${raffleId}/snapshot`, { method: 'POST' });
}


export function getRaffleEligibility(raffleId, page = 1, pageSize = 100) {
    return request(`/${raffleId}/eligibility?page=${page}&page_size=${pageSize}`);
}


export function drawRaffleWinner(raffleId, idempotencyKey) {
    return request(`/${raffleId}/draw`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
    });
}


export function publishRaffle(raffleId) {
    return request(`/${raffleId}/publish`, { method: 'POST' });
}


export function cancelRaffle(raffleId) {
    return request(`/${raffleId}/cancel`, { method: 'POST' });
}


export function getRaffleResult(raffleId) {
    return request(`/${raffleId}/result`);
}
