import { useEffect, useMemo, useState } from 'react';
import { FiEdit, FiFile, FiImage, FiPlus, FiSave, FiTrash2, FiX } from 'react-icons/fi';

import AssetPicker from './admin/AssetPicker';
import {
    createContentCard,
    deleteContentCard,
    fetchAdminContentSection,
    updateContentCard,
} from '../services/contentService';
import styles from '../styles/components/CMSPanel.module.css';


const SECTIONS = [
    { value: 'memorias', label: 'Memorias' },
    { value: 'galerias', label: 'Galerías' },
    { value: 'autores', label: 'Autores' },
];

const emptyForm = (section) => ({
    section,
    title: '',
    subtitle: '',
    year: '',
    description: '',
    image_url: '',
    link_url: '',
    asset_id: null,
    media_type: 'image',
    is_active: true,
    sort_order: 0,
});

function MediaPreview({ card }) {
    if (card.media_type === 'video' && card.image_url) {
        return <video src={card.image_url} className={styles.cardImg} controls preload="metadata" />;
    }
    if (card.media_type === 'document' || card.media_type === 'link') {
        return <div className={styles.cardImg} style={{ display: 'grid', placeItems: 'center', background: '#edf2f7', color: '#64748b' }}><FiFile size={28} /></div>;
    }
    if (card.image_url) return <img src={card.image_url} alt={card.title} className={styles.cardImg} loading="lazy" />;
    return <div className={styles.cardImg} style={{ display: 'grid', placeItems: 'center', background: '#edf2f7', color: '#64748b' }}><FiImage size={28} /></div>;
}

export default function CMSPanel() {
    const [section, setSection] = useState('memorias');
    const [cards, setCards] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [modalOpen, setModalOpen] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [editingCard, setEditingCard] = useState(null);
    const [form, setForm] = useState(() => emptyForm('memorias'));
    const sectionLabel = useMemo(() => SECTIONS.find((item) => item.value === section)?.label ?? section, [section]);

    useEffect(() => {
        let cancelled = false;
        fetchAdminContentSection(section)
            .then((items) => { if (!cancelled) setCards(items); })
            .catch((requestError) => { if (!cancelled) { setCards([]); setError(requestError.message); } })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [section]);

    const handleSectionChange = (event) => {
        setSection(event.target.value);
        setLoading(true);
        setError('');
    };

    const closeModal = () => {
        setModalOpen(false);
        setEditingCard(null);
        setForm(emptyForm(section));
        setSubmitting(false);
    };

    const openCreate = () => {
        setForm(emptyForm(section));
        setEditingCard(null);
        setModalOpen(true);
    };

    const openEdit = (card) => {
        setEditingCard(card);
        setForm({
            ...emptyForm(section),
            ...card,
            subtitle: card.subtitle ?? '',
            year: card.year ?? '',
            description: card.description ?? '',
            image_url: card.image_url ?? '',
            link_url: card.link_url ?? '',
        });
        setModalOpen(true);
    };

    const handleChange = (event) => {
        const { name, value, checked, type } = event.target;
        setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
    };

    const selectAsset = (asset) => {
        if (!asset) {
            setForm((current) => ({ ...current, asset_id: null, image_url: '' }));
            return;
        }
        const mediaType = asset.content_type?.startsWith('video/')
            ? 'video'
            : asset.content_type?.startsWith('image/') ? 'image' : 'document';
        setForm((current) => ({
            ...current,
            asset_id: asset.id,
            image_url: asset.url,
            media_type: mediaType,
        }));
    };

    const handleSave = async (event) => {
        event.preventDefault();
        setSubmitting(true);
        setError('');
        const payload = {
            section: form.section,
            title: form.title.trim(),
            subtitle: form.subtitle?.trim() || null,
            year: form.year === '' ? null : Number(form.year),
            description: form.description?.trim() || null,
            image_url: form.image_url?.trim() || null,
            link_url: form.link_url?.trim() || null,
            asset_id: form.asset_id || null,
            media_type: form.media_type,
            is_active: form.is_active,
            sort_order: Number(form.sort_order) || 0,
        };
        try {
            const saved = editingCard
                ? await updateContentCard(editingCard.id, payload)
                : await createContentCard(payload);
            setCards((current) => {
                const next = editingCard
                    ? current.map((item) => (item.id === saved.id ? saved : item))
                    : [...current, saved];
                return next.sort((left, right) => left.sort_order - right.sort_order);
            });
            closeModal();
        } catch (saveError) {
            setError(saveError.message);
            setSubmitting(false);
        }
    };

    const handleDelete = async (card) => {
        if (!window.confirm(`¿Eliminar la tarjeta "${card.title}"?`)) return;
        try {
            await deleteContentCard(card.id);
            setCards((current) => current.filter((item) => item.id !== card.id));
        } catch (deleteError) {
            setError(deleteError.message);
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <div><h2>Contenido del sitio</h2><p>Las tarjetas usan recursos reutilizables de la biblioteca Files.</p></div>
                <div className={styles.controls}>
                    <select value={section} onChange={handleSectionChange} className={styles.select}>{SECTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
                    <button type="button" className={styles.addBtn} onClick={openCreate}><FiPlus /> Nueva tarjeta</button>
                </div>
            </div>
            {error && !modalOpen && <p className={styles.noData} role="alert">{error}</p>}
            {loading ? <p className={styles.noData}>Cargando contenido…</p> : cards.length === 0 ? (
                <p className={styles.noData}>No hay contenido persistido para {sectionLabel.toLowerCase()}.</p>
            ) : (
                <div className={styles.grid}>{cards.map((card) => (
                    <article key={card.id} className={`${styles.card} ${!card.is_active ? styles.inactive : ''}`}>
                        <MediaPreview card={card} />
                        <div className={styles.cardBody}>
                            <h3>{card.title}</h3>{card.subtitle && <p className={styles.subtitle}>{card.subtitle}</p>}{card.year && <p className={styles.yearBadge}>{card.year}</p>}
                            <p className={styles.cardDesc}>{card.description || 'Sin descripción.'}</p>
                            <div className={styles.cardActions}><button type="button" onClick={() => openEdit(card)} title="Editar"><FiEdit /></button><button type="button" onClick={() => handleDelete(card)} className={styles.deleteBtn} title="Eliminar"><FiTrash2 /></button></div>
                        </div>
                    </article>
                ))}</div>
            )}

            {modalOpen && (
                <div className={styles.overlay} onClick={closeModal}>
                    <form className={styles.modal} style={{ maxWidth: '900px', maxHeight: '92vh', overflowY: 'auto' }} onClick={(event) => event.stopPropagation()} onSubmit={handleSave}>
                        <h3>{editingCard ? 'Editar' : 'Nueva'} tarjeta ({sectionLabel})</h3>
                        <label htmlFor="cms-title">Título</label><input id="cms-title" name="title" value={form.title} onChange={handleChange} required />
                        <label htmlFor="cms-subtitle">Subtítulo</label><input id="cms-subtitle" name="subtitle" value={form.subtitle} onChange={handleChange} />
                        {section === 'memorias' && <><label htmlFor="cms-year">Año</label><input id="cms-year" type="number" name="year" value={form.year} onChange={handleChange} /></>}
                        <label htmlFor="cms-description">Descripción</label><textarea id="cms-description" rows="4" name="description" value={form.description} onChange={handleChange} />
                        <label htmlFor="cms-media-type">Tipo de contenido</label>
                        <select id="cms-media-type" name="media_type" value={form.media_type} onChange={handleChange} className={styles.select}><option value="image">Imagen</option><option value="video">Video</option><option value="document">Documento</option><option value="link">Enlace</option></select>
                        <AssetPicker selectedId={form.asset_id} onSelect={selectAsset} contentType={section === 'galerias' ? '' : 'image'} heading="Recurso de la tarjeta" />
                        <label htmlFor="cms-media-url">URL multimedia (opcional si se selecciona un recurso)</label><input id="cms-media-url" name="image_url" value={form.image_url} onChange={handleChange} />
                        <label htmlFor="cms-link-url">Enlace de destino</label><input id="cms-link-url" name="link_url" value={form.link_url} onChange={handleChange} />
                        <label><input type="checkbox" name="is_active" checked={form.is_active} onChange={handleChange} /> Visible al público</label>
                        <label htmlFor="cms-order">Orden</label><input id="cms-order" type="number" name="sort_order" value={form.sort_order} onChange={handleChange} />
                        {error && <p className={styles.noData} role="alert">{error}</p>}
                        <div className={styles.modalFoot}><button type="button" onClick={closeModal}><FiX /> Cancelar</button><button type="submit" className={styles.addBtn} disabled={submitting}><FiSave /> {submitting ? 'Guardando…' : 'Guardar'}</button></div>
                    </form>
                </div>
            )}
        </div>
    );
}
