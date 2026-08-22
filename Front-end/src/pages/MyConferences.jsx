import { useContext, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiBookmark, FiLogIn } from 'react-icons/fi';

import AgendaGrid from '../components/AgendaGrid';
import LiveFilter from '../components/LiveFilter';
import SpeakerModal from '../components/SpeakerModal';
import { AuthContext } from '../context/AuthContext';
import { useAgenda } from '../hooks/useAgenda';
import styles from '../styles/pages/MyConferences.module.css';

export default function MyConferences({ registeredIds = new Set(), onToggleRegister }) {
    const { user } = useContext(AuthContext);
    const [selectedSpeaker, setSelectedSpeaker] = useState(null);
    const {
        sessions,
        days,
        activeDay,
        activeModality,
        activeEventType,
        venues,
        activeVenueId,
        searchQuery,
        setActiveDay,
        setActiveModality,
        setActiveEventType,
        setActiveVenueId,
        setSearchQuery,
    } = useAgenda();

    if (!user) {
        return (
            <div className={styles.page}>
                <div className={styles.empty}>
                    <FiLogIn size={48} className={styles.emptyIcon} style={{ color: '#dc2626' }} />
                    <h2 style={{ color: 'var(--color-primary)', marginTop: '1rem' }}>Inicia sesión</h2>
                    <p style={{ margin: '1rem 0 1.5rem 0', color: 'var(--text-muted)' }}>
                        Debes estar registrado e iniciar sesión para ver y gestionar tus preinscripciones.
                    </p>
                    <Link
                        to="/login"
                        style={{
                            background: 'var(--color-primary)',
                            color: 'white',
                            padding: '0.8rem 1.5rem',
                            borderRadius: '8px',
                            textDecoration: 'none',
                            fontWeight: '600',
                            transition: 'background 0.3s',
                        }}
                    >
                        Ir al inicio de sesión
                    </Link>
                </div>
            </div>
        );
    }

    const mySessions = sessions
        .filter((session) => registeredIds.has(session.id))
        .sort((left, right) => {
            if (left.hora_inicio < right.hora_inicio) return -1;
            if (left.hora_inicio > right.hora_inicio) return 1;
            return 0;
        });

    return (
        <div className={styles.page}>
            <div className={styles.header}>
                <FiBookmark className={styles.headerIcon} />
                <div>
                    <h1 className={styles.title}>Mis conferencias</h1>
                    <p className={styles.subtitle}>
                        {mySessions.length === 0
                            ? 'Aún no te has preinscrito en ninguna sesión o no hay resultados disponibles.'
                            : `${mySessions.length} sesión${mySessions.length !== 1 ? 'es' : ''} preinscrita${mySessions.length !== 1 ? 's' : ''}`}
                    </p>
                </div>
            </div>

            <div style={{ padding: '0 2rem 1.5rem 2rem' }}>
                <LiveFilter
                    days={days}
                    activeDay={activeDay}
                    activeModality={activeModality}
                    activeEventType={activeEventType}
                    venues={venues}
                    activeVenueId={activeVenueId}
                    searchQuery={searchQuery}
                    onDayChange={setActiveDay}
                    onModalityChange={setActiveModality}
                    onEventTypeChange={setActiveEventType}
                    onVenueChange={setActiveVenueId}
                    onSearchQueryChange={setSearchQuery}
                />
            </div>

            {mySessions.length === 0 ? (
                <div className={styles.empty}>
                    <FiBookmark size={48} className={styles.emptyIcon} />
                    <p>
                        Ve a la <strong>Agenda</strong> y haz clic en <em>&ldquo;Preinscribirse&rdquo;</em> en las sesiones que te interesen.
                    </p>
                </div>
            ) : (
                <AgendaGrid
                    sessions={mySessions}
                    isLoading={false}
                    onSpeakerClick={setSelectedSpeaker}
                    registeredIds={registeredIds}
                    onToggleRegister={onToggleRegister}
                    mode="mis-conferencias"
                />
            )}

            {selectedSpeaker && (
                <SpeakerModal
                    speaker={selectedSpeaker}
                    onClose={() => setSelectedSpeaker(null)}
                />
            )}
        </div>
    );
}
