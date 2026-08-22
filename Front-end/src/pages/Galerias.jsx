import { useEffect, useState } from 'react';
import { FiExternalLink } from 'react-icons/fi';

import { useEventTheme } from '../context/EventThemeContext';
import { fetchContentSectionStrict } from '../services/contentService';
import pageStyles from '../styles/pages/DynamicPage.module.css';
import styles from '../styles/pages/Galerias.module.css';


export default function Galerias() {
    const { isModuleVisible } = useEventTheme();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let cancelled = false;
        fetchContentSectionStrict('galerias')
            .then((data) => { if (!cancelled) setItems(data); })
            .catch((requestError) => { if (!cancelled) setError(requestError.message); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, []);

    if (!isModuleVisible('gallery')) {
        return <div className={pageStyles.page}><div className={pageStyles.container}><div className={pageStyles.empty}><h1>Galería no disponible</h1><p>Este módulo está oculto temporalmente por la organización.</p></div></div></div>;
    }

    return (
        <div className={pageStyles.page}>
            <div className={pageStyles.hero}><div className={pageStyles.heroContent}><h1>Galería multimedia</h1><p>Revive los mejores momentos de las ediciones del Congreso CONIITI.</p></div></div>
            <div className={pageStyles.container}>
                {loading ? <div className={pageStyles.empty}><h3>Cargando</h3><p>Consultando la biblioteca oficial…</p></div>
                    : error ? <div className={pageStyles.empty} role="alert"><h3>Contenido no disponible</h3><p>{error}</p></div>
                        : items.length === 0 ? <div className={pageStyles.empty}><h3>Próximamente</h3><p>Aún no hay recursos publicados.</p></div>
                            : <div className={styles.grid}>{items.map((item) => (
                                <article key={item.id} className={styles.card}>
                                    {item.media_type === 'video' && item.image_url ? (
                                        <video src={item.image_url} controls preload="metadata" playsInline aria-label={item.title} />
                                    ) : item.media_type === 'image' && item.image_url ? (
                                        <img src={item.image_url} alt={item.title} loading="lazy" />
                                    ) : <div className={styles.placeholder}>{item.media_type === 'document' ? 'Documento disponible' : 'Recurso sin vista previa'}</div>}
                                    <div className={styles.body}><h2>{item.title}</h2>{item.description && <p>{item.description}</p>}{(item.link_url || (item.media_type !== 'image' && item.image_url)) && <a href={item.link_url || item.image_url} target="_blank" rel="noopener noreferrer"><FiExternalLink /> {item.media_type === 'document' ? 'Abrir documento' : 'Ver recurso relacionado'}</a>}</div>
                                </article>
                            ))}</div>}
            </div>
        </div>
    );
}
