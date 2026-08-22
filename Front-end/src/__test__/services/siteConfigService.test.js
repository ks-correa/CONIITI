import { afterEach, describe, expect, it, vi } from 'vitest';

import {
    DEFAULT_SITE_CONFIGURATION,
    fetchSiteConfiguration,
    updateSiteConfiguration,
} from '../../services/siteConfigService';
import { fetchContentSection, fetchContentSectionStrict } from '../../services/contentService';


afterEach(() => {
    vi.unstubAllGlobals();
});

describe('siteConfigService', () => {
    it('no duplica edición ni fechas autoritativas de Agenda en Files', () => {
        expect(DEFAULT_SITE_CONFIGURATION.guest_country).not.toHaveProperty('edition_label');
        expect(DEFAULT_SITE_CONFIGURATION.pages.home.subtitle).not.toMatch(/\b20\d{2}\b|octubre/i);
    });

    it('conserva el ETag publicado por Files', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
            JSON.stringify({ ...DEFAULT_SITE_CONFIGURATION, revision: 7, created_at: '2026-08-21T00:00:00Z' }),
            { status: 200, headers: { 'Content-Type': 'application/json', ETag: '"7"' } },
        )));

        const result = await fetchSiteConfiguration();
        expect(result.etag).toBe('"7"');
        expect(result.configuration.revision).toBe(7);
    });

    it('envía If-Match al publicar para evitar sobrescrituras', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(
            JSON.stringify({ ...DEFAULT_SITE_CONFIGURATION, revision: 8, created_at: '2026-08-21T00:00:00Z' }),
            { status: 200, headers: { 'Content-Type': 'application/json', ETag: '"8"' } },
        ));
        vi.stubGlobal('fetch', fetchMock);

        await updateSiteConfiguration(DEFAULT_SITE_CONFIGURATION, '"7"', 'Cambio probado');
        expect(fetchMock).toHaveBeenCalledWith('/api/files/site-config', expect.objectContaining({
            method: 'PUT',
            headers: expect.objectContaining({ 'If-Match': '"7"' }),
        }));
    });
});

describe('contentService', () => {
    it('no presenta tarjetas demo cuando Files está caído', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
        await expect(fetchContentSection('galerias')).resolves.toEqual([]);
        await expect(fetchContentSectionStrict('galerias')).rejects.toThrow('offline');
    });
});
