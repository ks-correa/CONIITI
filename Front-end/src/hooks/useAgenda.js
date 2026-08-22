import { useCallback, useEffect, useMemo, useState } from 'react';

import { filterSessions, getAgendaConfiguration, getVenues } from '../services/agendaService';


function formatDays(configuration) {
    if (!configuration?.conference_days) return [];
    return configuration.conference_days.map((value, index) => ({
        value,
        ordinal: index + 1,
        label: new Intl.DateTimeFormat('es-CO', {
            month: 'short', day: 'numeric', timeZone: 'UTC',
        }).format((() => {
            const [year, month, day] = value.split('-').map(Number);
            return new Date(Date.UTC(year, month - 1, day, 12));
        })()),
    }));
}


export function useAgenda() {
    const [configuration, setConfiguration] = useState(null);
    const [venues, setVenues] = useState([]);
    const [activeDay, setActiveDay] = useState(null);
    const [activeModality, setActiveModality] = useState(null);
    const [activeEventType, setActiveEventType] = useState(null);
    const [activeRoom, setActiveRoom] = useState(null);
    const [activeVenueId, setActiveVenueId] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [sessions, setSessions] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const days = useMemo(() => formatDays(configuration), [configuration]);

    const fetchMetadata = useCallback(async () => {
        try {
            const [nextConfiguration, nextVenues] = await Promise.all([
                getAgendaConfiguration(),
                getVenues(),
            ]);
            setConfiguration(nextConfiguration);
            setVenues(nextVenues);
            setActiveDay((current) => (
                nextConfiguration.conference_days.includes(current)
                    ? current
                    : nextConfiguration.conference_days[0] ?? null
            ));
            setError('');
        } catch (metadataError) {
            setError(metadataError.message);
            setIsLoading(false);
        }
    }, []);

    const fetchSessions = useCallback(async () => {
        if (!activeDay) return;
        setIsLoading(true);
        try {
            const data = await filterSessions({
                day: activeDay,
                modality: activeModality,
                eventType: activeEventType,
                room: activeRoom,
                venueId: activeVenueId,
                search: searchQuery,
            });
            setSessions(data);
            setError('');
        } catch (fetchError) {
            setError(fetchError.message);
            setSessions([]);
        } finally {
            setIsLoading(false);
        }
    }, [activeDay, activeModality, activeEventType, activeRoom, activeVenueId, searchQuery]);

    useEffect(() => {
        fetchMetadata();
    }, [fetchMetadata]);

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    return {
        sessions,
        configuration,
        venues,
        days,
        activeDay,
        activeModality,
        activeEventType,
        activeRoom,
        activeVenueId,
        searchQuery,
        isLoading,
        error,
        setActiveDay,
        setActiveModality,
        setActiveEventType,
        setActiveRoom,
        setActiveVenueId,
        setSearchQuery,
        refresh: fetchSessions,
        refreshMetadata: fetchMetadata,
    };
}
