import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import {
    DEFAULT_SITE_CONFIGURATION,
    fetchSiteConfiguration,
    rollbackSiteConfiguration,
    updateSiteConfiguration,
} from '../services/siteConfigService';
import { getAgendaConfiguration } from '../services/agendaService';


// eslint-disable-next-line react-refresh/only-export-components
export const GUEST_COUNTRY_PRESETS = [
    { id: 'italia', country: 'Italia', colors: ['#009246', '#ffffff', '#ce2b37'] },
    { id: 'brasil', country: 'Brasil', colors: ['#009b3a', '#ffdf00', '#002776'] },
    { id: 'mexico', country: 'México', colors: ['#006847', '#ffffff', '#ce1126'] },
    { id: 'espana', country: 'España', colors: ['#aa151b', '#f1bf00', '#aa151b'] },
    { id: 'francia', country: 'Francia', colors: ['#0055a4', '#ffffff', '#ef4135'] },
    { id: 'argentina', country: 'Argentina', colors: ['#74acdf', '#ffffff', '#f6b40e'] },
];

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function mergeConfiguration(value) {
    const source = value && typeof value === 'object' ? value : {};
    return {
        ...clone(DEFAULT_SITE_CONFIGURATION),
        ...source,
        event: { ...DEFAULT_SITE_CONFIGURATION.event, ...source.event },
        guest_country: { ...DEFAULT_SITE_CONFIGURATION.guest_country, ...source.guest_country },
        branding: { ...DEFAULT_SITE_CONFIGURATION.branding, ...source.branding },
        pages: {
            ...DEFAULT_SITE_CONFIGURATION.pages,
            ...source.pages,
            home: { ...DEFAULT_SITE_CONFIGURATION.pages.home, ...source.pages?.home },
            about: { ...DEFAULT_SITE_CONFIGURATION.pages.about, ...source.pages?.about },
            contact: { ...DEFAULT_SITE_CONFIGURATION.pages.contact, ...source.pages?.contact },
            speakers: { ...DEFAULT_SITE_CONFIGURATION.pages.speakers, ...source.pages?.speakers },
            agenda: { ...DEFAULT_SITE_CONFIGURATION.pages.agenda, ...source.pages?.agenda },
        },
        modules: { ...DEFAULT_SITE_CONFIGURATION.modules, ...source.modules },
    };
}

function toTheme(configuration, agendaConfiguration) {
    const guest = configuration.guest_country;
    return {
        id: guest.id,
        country: guest.country,
        editionLabel: agendaConfiguration?.edition_label ?? '',
        colors: guest.colors,
        siteAccentsEnabled: guest.site_accents_enabled,
        agendaParticlesEnabled: guest.agenda_particles_enabled,
    };
}

function toWritableConfiguration(configuration) {
    const writable = clone(configuration);
    delete writable.revision;
    delete writable.schema_version;
    delete writable.created_at;
    // Compatibilidad de lectura con revisiones antiguas. Agenda es la única
    // autoridad de la edición y Files ya no acepta este campo.
    delete writable.guest_country?.edition_label;
    return writable;
}

function isHexColor(value) {
    return /^#[0-9a-f]{6}$/i.test(value);
}

function hexToRgb(value) {
    const numeric = Number.parseInt(isHexColor(value) ? value.slice(1) : '000000', 16);
    return [(numeric >> 16) & 255, (numeric >> 8) & 255, numeric & 255].join(', ');
}

function applyThemeVariables(theme) {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const colors = theme.colors.map((color, index) => (
        isHexColor(color) ? color : DEFAULT_SITE_CONFIGURATION.guest_country.colors[index]
    ));
    const appliedColors = theme.siteAccentsEnabled ? colors : ['#0d2b4e', '#0d2b4e', '#0d2b4e'];
    root.style.setProperty('--guest-color-one', appliedColors[0]);
    root.style.setProperty('--guest-color-two', appliedColors[1]);
    root.style.setProperty('--guest-color-three', appliedColors[2]);
    root.style.setProperty('--guest-color-one-rgb', hexToRgb(appliedColors[0]));
    root.style.setProperty('--guest-color-two-rgb', hexToRgb(appliedColors[1]));
    root.style.setProperty('--guest-color-three-rgb', hexToRgb(appliedColors[2]));
    root.style.setProperty(
        '--guest-flag-gradient',
        `linear-gradient(90deg, ${appliedColors[0]} 0 33%, ${appliedColors[1]} 33% 66%, ${appliedColors[2]} 66% 100%)`,
    );
    root.dataset.guestAccents = theme.siteAccentsEnabled ? 'on' : 'off';
}

const EventThemeContext = createContext(null);

export function EventThemeProvider({ children }) {
    const [siteConfig, setSiteConfig] = useState(() => mergeConfiguration(DEFAULT_SITE_CONFIGURATION));
    const [etag, setEtag] = useState('"0"');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [agendaConfig, setAgendaConfig] = useState(null);
    const [agendaConfigLoading, setAgendaConfigLoading] = useState(true);
    const [agendaConfigError, setAgendaConfigError] = useState('');
    const theme = useMemo(() => toTheme(siteConfig, agendaConfig), [agendaConfig, siteConfig]);

    const refreshConfiguration = useCallback(async () => {
        setLoading(true);
        try {
            const result = await fetchSiteConfiguration();
            setSiteConfig(mergeConfiguration(result.configuration));
            setEtag(result.etag);
            setError('');
            return result.configuration;
        } catch (requestError) {
            setError(requestError.message);
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    const refreshAgendaConfiguration = useCallback(async () => {
        setAgendaConfigLoading(true);
        try {
            const configuration = await getAgendaConfiguration();
            setAgendaConfig(configuration);
            setAgendaConfigError('');
            return configuration;
        } catch (requestError) {
            setAgendaConfigError(requestError.message);
            return null;
        } finally {
            setAgendaConfigLoading(false);
        }
    }, []);

    useEffect(() => {
        refreshConfiguration();
    }, [refreshConfiguration]);

    useEffect(() => {
        refreshAgendaConfiguration();
    }, [refreshAgendaConfiguration]);

    useEffect(() => {
        if (!error) return undefined;
        const retryTimer = window.setTimeout(refreshConfiguration, 30_000);
        return () => window.clearTimeout(retryTimer);
    }, [error, refreshConfiguration]);

    useEffect(() => {
        if (!agendaConfigError) return undefined;
        const retryTimer = window.setTimeout(refreshAgendaConfiguration, 30_000);
        return () => window.clearTimeout(retryTimer);
    }, [agendaConfigError, refreshAgendaConfiguration]);

    useEffect(() => {
        applyThemeVariables(theme);
    }, [theme]);

    const saveConfiguration = useCallback(async (nextConfiguration, changeSummary) => {
        const writable = toWritableConfiguration(mergeConfiguration(nextConfiguration));
        const result = await updateSiteConfiguration(writable, etag, changeSummary);
        setSiteConfig(mergeConfiguration(result.configuration));
        setEtag(result.etag);
        setError('');
        return result.configuration;
    }, [etag]);

    const rollbackConfiguration = useCallback(async (revision) => {
        const result = await rollbackSiteConfiguration(revision, etag);
        setSiteConfig(mergeConfiguration(result.configuration));
        setEtag(result.etag);
        setError('');
        return result.configuration;
    }, [etag]);

    const value = useMemo(() => ({
        theme,
        presets: GUEST_COUNTRY_PRESETS,
        siteConfig,
        agendaConfig,
        agendaConfigLoading,
        agendaConfigError,
        etag,
        loading,
        error,
        refreshConfiguration,
        refreshAgendaConfiguration,
        saveConfiguration,
        rollbackConfiguration,
        isModuleVisible: (moduleName) => siteConfig.modules?.[`${moduleName}_visible`] !== false,
        updateTheme: (patch) => setSiteConfig((current) => ({
            ...current,
            guest_country: {
                ...current.guest_country,
                id: patch.id ?? current.guest_country.id,
                country: patch.country ?? current.guest_country.country,
                colors: patch.colors ?? current.guest_country.colors,
                site_accents_enabled: patch.siteAccentsEnabled ?? current.guest_country.site_accents_enabled,
                agenda_particles_enabled: patch.agendaParticlesEnabled ?? current.guest_country.agenda_particles_enabled,
            },
        })),
    }), [
        error,
        agendaConfig,
        agendaConfigError,
        agendaConfigLoading,
        etag,
        loading,
        refreshConfiguration,
        refreshAgendaConfiguration,
        rollbackConfiguration,
        saveConfiguration,
        siteConfig,
        theme,
    ]);

    return <EventThemeContext.Provider value={value}>{children}</EventThemeContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useEventTheme() {
    const context = useContext(EventThemeContext);
    if (!context) throw new Error('useEventTheme debe usarse dentro de EventThemeProvider.');
    return context;
}
