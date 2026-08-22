export const SESSION_STATUS = Object.freeze({
    NORMAL: 'Normal',
    CAMBIO_SALON: 'Cambio de Salón',
    RETRASADO: 'Retrasado',
});

export const SESSION_MODALITY = Object.freeze({
    PRESENCIAL: 'Presencial',
    VIRTUAL: 'Virtual',
    HIBRIDO: 'Híbrido',
});

export const SESSION_TRACK = Object.freeze({
    IA: 'Inteligencia Artificial',
    CIBERSEGURIDAD: 'Ciberseguridad',
    IOT: 'Internet de las Cosas',
    DESARROLLO: 'Desarrollo de Software',
    DATOS: 'Ciencia de Datos',
    INNOVACION: 'Innovación y Tendencias',
});

export const SESSION_EVENT_TYPE = Object.freeze({
    CONFERENCE: 'Conferencia',
    WORKSHOP: 'Taller',
    SYMPOSIUM: 'Simposio',
    PANEL: 'Panel',
});

// Las sedes ya no se compilan en el bundle: se consultan en /api/agenda/venues.
export const SESSION_ROOMS = Object.freeze({});

export const VENUE_RESOURCE_TYPE = Object.freeze({
    VIDEO: 'video',
    IMAGE: 'image',
    DOCUMENT: 'document',
    LINK: 'link',
    POSTER: 'poster',
});

export const VENUE_RESOURCE_STATE = Object.freeze({
    PENDING_ASSET: 'pending_asset',
    ACTIVE: 'active',
    PENDING_DELETE: 'pending_delete',
    TOMBSTONED: 'tombstoned',
    ERROR: 'error',
});
