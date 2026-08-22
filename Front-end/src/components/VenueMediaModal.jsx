import { useEffect, useMemo, useRef, useState } from 'react';
import { FiChevronLeft, FiChevronRight, FiExternalLink, FiMapPin, FiX } from 'react-icons/fi';

import styles from '../styles/components/VenueMediaModal.module.css';


function Resource({ resource, poster }) {
    if (!resource) return <p className={styles.empty}>Esta sede aún no tiene recursos publicados.</p>;
    if (resource.resource_type === 'video') {
        return (
            <video
                key={resource.id}
                className={styles.media}
                controls
                preload="metadata"
                poster={poster?.url}
                aria-label={resource.alt_text || resource.title}
            >
                <source src={resource.url} type={resource.mime_type || undefined} />
                {resource.captions_url && (
                    <track kind="captions" src={resource.captions_url} srcLang="es" label="Español" default />
                )}
                Tu navegador no puede reproducir este video.
            </video>
        );
    }
    if (resource.resource_type === 'image' || resource.resource_type === 'poster') {
        return <img className={styles.media} src={resource.url} alt={resource.alt_text || resource.title} loading="lazy" />;
    }
    return (
        <div className={styles.linkResource}>
            <p>{resource.description || 'Este recurso se abre en una pestaña nueva.'}</p>
            <a href={resource.url} target="_blank" rel="noopener noreferrer">
                Abrir {resource.resource_type === 'document' ? 'documento' : 'enlace'} <FiExternalLink />
            </a>
        </div>
    );
}


export default function VenueMediaModal({ venue, onClose }) {
    const closeButton = useRef(null);
    const resources = useMemo(
        () => [...(venue?.resources ?? [])].filter((item) => item.state === 'active').sort(
            (left, right) => left.display_order - right.display_order,
        ),
        [venue],
    );
    const poster = resources.find((item) => item.resource_type === 'poster');
    const browsable = resources.filter((item) => item.resource_type !== 'poster');
    const [activeIndex, setActiveIndex] = useState(0);
    const active = browsable[activeIndex] ?? poster ?? null;

    useEffect(() => {
        closeButton.current?.focus();
        const handleKey = (event) => {
            if (event.key === 'Escape') onClose();
            if (event.key === 'ArrowLeft' && browsable.length > 1) setActiveIndex((value) => (value - 1 + browsable.length) % browsable.length);
            if (event.key === 'ArrowRight' && browsable.length > 1) setActiveIndex((value) => (value + 1) % browsable.length);
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [browsable.length, onClose]);

    if (!venue) return null;

    return (
        <div className={styles.overlay} onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
            <section className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="venue-media-title">
                <header className={styles.header}>
                    <div>
                        <span><FiMapPin /> Conoce la sede</span>
                        <h2 id="venue-media-title">{venue.name}</h2>
                    </div>
                    <button ref={closeButton} type="button" onClick={onClose} aria-label="Cerrar recursos de la sede">
                        <FiX />
                    </button>
                </header>

                <div className={styles.viewer}>
                    <Resource resource={active} poster={poster} />
                    {browsable.length > 1 && (
                        <div className={styles.navigation}>
                            <button type="button" onClick={() => setActiveIndex((activeIndex - 1 + browsable.length) % browsable.length)} aria-label="Recurso anterior">
                                <FiChevronLeft />
                            </button>
                            <span>{activeIndex + 1} de {browsable.length}</span>
                            <button type="button" onClick={() => setActiveIndex((activeIndex + 1) % browsable.length)} aria-label="Recurso siguiente">
                                <FiChevronRight />
                            </button>
                        </div>
                    )}
                </div>

                <div className={styles.details}>
                    <h3>{active?.title ?? 'Información de la sede'}</h3>
                    <p>{active?.description || venue.description || 'Próximamente encontrarás más información.'}</p>
                    {active?.transcript_url && (
                        <a href={active.transcript_url} target="_blank" rel="noopener noreferrer">
                            Consultar transcripción accesible <FiExternalLink />
                        </a>
                    )}
                </div>

                {browsable.length > 1 && (
                    <div className={styles.thumbnails} aria-label="Recursos disponibles">
                        {browsable.map((resource, index) => (
                            <button
                                type="button"
                                key={resource.id}
                                className={index === activeIndex ? styles.activeThumb : ''}
                                onClick={() => setActiveIndex(index)}
                            >
                                {resource.title}
                            </button>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}
