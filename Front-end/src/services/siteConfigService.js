import { getApiBase, getJsonHeaders } from './apiConfig';


const FILES_BASE = `${getApiBase()}/files`;

export const DEFAULT_SITE_CONFIGURATION = Object.freeze({
    revision: 0,
    schema_version: 1,
    event: {
        title: 'XI CONIITI 2026',
        subtitle: 'Congreso Internacional de Innovación y Tendencias en Ingeniería',
        description: '',
        location_label: 'Bogotá, Colombia',
    },
    guest_country: {
        id: 'italia',
        country: 'Italia',
        colors: ['#009246', '#ffffff', '#ce2b37'],
        site_accents_enabled: true,
        agenda_particles_enabled: true,
    },
    branding: {
        logo_asset_id: null,
        logo_url: null,
        hero_asset_id: null,
        hero_url: null,
    },
    pages: {
        home: {
            title: 'XI CONIITI 2026',
            subtitle: 'Congreso Internacional de Innovación y Tendencias en Ingeniería.',
            cta_label: 'Ver agenda',
        },
        about: {
            title: 'Acerca de CONIITI',
            description: 'Un punto de encuentro académico para explorar innovación, tendencias y nuevas aproximaciones en ingeniería con visión internacional.',
        },
        contact: {
            title: 'Contacto',
            email: 'coniiti@ucatolica.edu.co',
            phone: 'PBX: (601) 4433700',
            address: 'Bogotá, carrera 13 # 47 - 30',
            message: 'Estamos disponibles para orientar tus consultas sobre el congreso.',
        },
        speakers: {
            title: 'Conferencistas principales',
            subtitle: 'Conoce a los conferencistas invitados del Congreso CONIITI.',
            show_organization: true,
        },
        agenda: {
            title: 'Agenda',
            subtitle: 'Conferencias y talleres del Congreso CONIITI.',
            show_filters: true,
            columns: 3,
        },
    },
    modules: {
        agenda_visible: true,
        gallery_visible: true,
        speakers_visible: true,
        memories_visible: true,
        authors_visible: true,
        committee_visible: true,
        about_visible: true,
        contact_visible: true,
        payments_visible: true,
    },
});

export class SiteConfigurationError extends Error {
    constructor(message, status = 0) {
        super(message);
        this.name = 'SiteConfigurationError';
        this.status = status;
    }
}

async function request(path, options = {}) {
    const response = await fetch(`${FILES_BASE}${path}`, {
        ...options,
        credentials: 'include',
        headers: getJsonHeaders(options),
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new SiteConfigurationError(
            error.detail ?? 'No se pudo completar la operación de configuración.',
            response.status,
        );
    }
    const configuration = await response.json();
    return {
        configuration,
        etag: response.headers.get('ETag') ?? `"${configuration.revision}"`,
    };
}

export function fetchSiteConfiguration() {
    return request('/site-config');
}

export function updateSiteConfiguration(configuration, etag, changeSummary) {
    return request('/site-config', {
        method: 'PUT',
        headers: { 'If-Match': etag },
        body: JSON.stringify({
            configuration,
            change_summary: changeSummary || 'Actualización desde el panel de administración',
        }),
    });
}

export async function listSiteConfigurationRevisions({ limit = 25, offset = 0 } = {}) {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const response = await fetch(`${FILES_BASE}/site-config/revisions?${query}`, {
        credentials: 'include',
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new SiteConfigurationError(error.detail ?? 'No se pudo consultar el historial.', response.status);
    }
    return response.json();
}

export function rollbackSiteConfiguration(revision, etag, changeSummary) {
    return request(`/site-config/rollback/${revision}`, {
        method: 'POST',
        headers: { 'If-Match': etag },
        body: JSON.stringify({
            change_summary: changeSummary || `Restauración de la revisión ${revision}`,
        }),
    });
}
