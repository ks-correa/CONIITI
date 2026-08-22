import { FiSearch } from 'react-icons/fi';

import { SESSION_MODALITY, SESSION_EVENT_TYPE } from '../types/session';
import styles from '../styles/components/LiveFilter.module.css';

export default function LiveFilter({
    days,
    activeDay,
    activeModality,
    activeEventType,
    venues = [],
    activeVenueId,
    searchQuery,
    onDayChange,
    onModalityChange,
    onEventTypeChange,
    onVenueChange,
    onSearchQueryChange,
}) {
    const handleModalityChange = (event) => {
        const value = event.target.value;
        onModalityChange(value === '' ? null : value);
    };

    return (
        <div className={styles.filterBar}>
            <div className={styles.dayTabs} role="tablist" aria-label="D\u00edas del congreso">
                {days.map((day) => (
                    <button
                        key={day.value}
                        role="tab"
                        aria-selected={activeDay === day.value}
                        className={`${styles.dayTab} ${activeDay === day.value ? styles.dayTabActive : ''}`}
                        onClick={() => onDayChange(day.value)}
                    >
                        {day.label}
                    </button>
                ))}
            </div>

            <div className={styles.separator} aria-hidden="true" />

            <div className={styles.selectWrapper}>
                <label className={styles.selectLabel} htmlFor="modality-select">
                    Modalidad
                </label>
                <select
                    id="modality-select"
                    className={styles.select}
                    value={activeModality ?? ''}
                    onChange={handleModalityChange}
                >
                    <option value="">Todas</option>
                    {Object.values(SESSION_MODALITY).map((modality) => (
                        <option key={modality} value={modality}>
                            {modality}
                        </option>
                    ))}
                </select>
            </div>

            <div className={styles.selectWrapper}>
                <label className={styles.selectLabel} htmlFor="event-type-select">Actividad</label>
                <select
                    id="event-type-select"
                    className={styles.select}
                    value={activeEventType ?? ''}
                    onChange={(event) => onEventTypeChange(event.target.value || null)}
                >
                    <option value="">Todos</option>
                    {Object.values(SESSION_EVENT_TYPE).map((eventType) => (
                        <option key={eventType} value={eventType}>{eventType}</option>
                    ))}
                </select>
            </div>

            <div className={`${styles.selectWrapper} ${styles.roomWrapper}`}>
                <label className={styles.selectLabel} htmlFor="venue-select">Sede</label>
                <select
                    id="venue-select"
                    className={`${styles.select} ${styles.roomSelect}`}
                    value={activeVenueId ?? ''}
                    onChange={(event) => onVenueChange(event.target.value || null)}
                >
                    <option value="">Todas</option>
                    {venues.map((venue) => (
                        <option key={venue.id} value={venue.id}>
                            {venue.name}
                        </option>
                    ))}
                </select>
            </div>

            <div className={styles.searchWrapper}>
                <FiSearch className={styles.searchIcon} />
                <input
                    type="text"
                    className={styles.searchInput}
                    placeholder="Tema o palabra clave..."
                    value={searchQuery}
                    onChange={(event) => onSearchQueryChange(event.target.value)}
                />
            </div>
        </div>
    );
}
