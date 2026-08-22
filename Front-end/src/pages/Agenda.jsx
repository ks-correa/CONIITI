import { useState } from 'react';

import LiveFilter from '../components/LiveFilter';
import AgendaGrid from '../components/AgendaGrid';
import SpeakerModal from '../components/SpeakerModal';
import { useEventTheme } from '../context/EventThemeContext';
import { useAgenda } from '../hooks/useAgenda';
import { usePolling } from '../hooks/usePolling';
import styles from '../styles/pages/Agenda.module.css';

export default function Agenda({ registeredIds = new Set(), onToggleRegister }) {
    const [selectedSpeaker, setSelectedSpeaker] = useState(null);
    const { theme, siteConfig } = useEventTheme();

    const {
        searchQuery, setSearchQuery,
        activeEventType, setActiveEventType,
        activeVenueId, setActiveVenueId,
        sessions, days, activeDay, activeModality,
        configuration, venues, error,
        isLoading, setActiveDay, setActiveModality, refresh,
    } = useAgenda();

    usePolling(refresh, 60_000);

    const activeDayLabel = days.find((day) => day.value === activeDay)?.label ?? 'Dia seleccionado';
    const agendaPageConfig = siteConfig?.pages?.agenda ?? {};
    const agendaTitle = agendaPageConfig.title || `Agenda ${configuration?.edition_label ?? 'CONIITI'}`;
    const agendaSubtitle = agendaPageConfig.subtitle || 'Explora sesiones, talleres y ponencias por día, sala y modalidad.';
    const showFilters = agendaPageConfig.show_filters !== false;
    const columns = Number(agendaPageConfig.columns) || 3;

    return (
        <div className={styles.agendaPage}>
            <section className={styles.hero}>
                {theme.siteAccentsEnabled && theme.agendaParticlesEnabled && (
                    <div className={styles.particleField} aria-hidden="true" />
                )}

                <div className={styles.heroContent}>
                    <div>
                        <span className={styles.eyebrow}>{theme.editionLabel}</span>
                        <h1>{agendaTitle}</h1>
                        <p>{agendaSubtitle}</p>
                    </div>

                    <div className={styles.countryPanel}>
                        <span>Pais invitado</span>
                        <strong>{theme.country}</strong>
                        {theme.siteAccentsEnabled && (
                            <div className={styles.flagStrip} aria-hidden="true">
                                {theme.colors.map((color, index) => (
                                    <i key={`${color}-${index}`} style={{ backgroundColor: color }} />
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div className={styles.quickStats}>
                    <div>
                        <strong>{sessions.length}</strong>
                        <span>{sessions.length === 1 ? 'sesion visible' : 'sesiones visibles'}</span>
                    </div>
                    <div>
                        <strong>{activeDayLabel}</strong>
                        <span>dia activo</span>
                    </div>
                    <div>
                        <strong>{activeModality ?? 'Todas'}</strong>
                        <span>modalidad</span>
                    </div>
                </div>
            </section>

            <div className={styles.pollingBar}>
                <span className={styles.pollingDot} />
                La agenda se actualiza automaticamente para mostrarte la informacion mas reciente.
            </div>

            {error && <div role="alert" className={styles.error}>{error}</div>}

            {showFilters && <LiveFilter
                days={days}
                venues={venues}
                activeDay={activeDay}
                activeModality={activeModality}
                activeEventType={activeEventType}
                activeVenueId={activeVenueId}
                searchQuery={searchQuery}
                onDayChange={setActiveDay}
                onModalityChange={setActiveModality}
                onEventTypeChange={setActiveEventType}
                onVenueChange={setActiveVenueId}
                onSearchQueryChange={setSearchQuery}
            />}

            <AgendaGrid
                sessions={sessions}
                isLoading={isLoading}
                onSpeakerClick={setSelectedSpeaker}
                registeredIds={registeredIds}
                onToggleRegister={onToggleRegister}
                columns={columns}
            />

            {selectedSpeaker && (
                <SpeakerModal
                    speaker={selectedSpeaker}
                    onClose={() => setSelectedSpeaker(null)}
                />
            )}
        </div>
    );
}
