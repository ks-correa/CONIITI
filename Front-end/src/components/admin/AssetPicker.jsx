import { useCallback, useEffect, useState } from 'react';
import { FiFile, FiFilm, FiRefreshCw, FiSearch, FiTrash2, FiUploadCloud } from 'react-icons/fi';

import { deleteAsset, listAssets, uploadAsset } from '../../services/filesAdminService';
import styles from '../../styles/components/AssetPicker.module.css';


function formatSize(value) {
    const bytes = Number(value || 0);
    if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
    if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
    if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${bytes} B`;
}

function AssetPreview({ asset }) {
    if (asset.content_type?.startsWith('image/')) {
        return <img src={asset.url} alt="" loading="lazy" />;
    }
    if (asset.content_type?.startsWith('video/')) {
        return <div className={styles.placeholder}><FiFilm /><span>Video</span></div>;
    }
    return <div className={styles.placeholder}><FiFile /><span>Archivo</span></div>;
}

export default function AssetPicker({
    selectedId = null,
    onSelect = () => {},
    contentType = '',
    allowUpload = true,
    allowDelete = false,
    heading = 'Seleccionar recurso',
}) {
    const [assets, setAssets] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedType, setSelectedType] = useState('');
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            setAssets(await listAssets({ limit: 100, search, content_type: contentType || selectedType }));
        } catch (loadError) {
            setAssets([]);
            setError(loadError.message);
        } finally {
            setLoading(false);
        }
    }, [contentType, search, selectedType]);

    useEffect(() => {
        const timer = window.setTimeout(load, 250);
        return () => window.clearTimeout(timer);
    }, [load]);

    const handleUpload = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        setUploading(true);
        setError('');
        try {
            const asset = await uploadAsset(file);
            setAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)]);
            onSelect(asset);
        } catch (uploadError) {
            setError(uploadError.message);
        } finally {
            setUploading(false);
            event.target.value = '';
        }
    };

    const handleDelete = async (asset) => {
        if (!window.confirm(`¿Eliminar "${asset.original_name}"?`)) return;
        setError('');
        try {
            await deleteAsset(asset.id);
            setAssets((current) => current.filter((item) => item.id !== asset.id));
            if (selectedId === asset.id) onSelect(null);
        } catch (deleteError) {
            setError(deleteError.message);
        }
    };

    const accept = contentType === 'image' || contentType === 'image/*'
        ? 'image/*'
        : contentType === 'video' || contentType === 'video/*'
            ? 'video/mp4,video/webm,video/quicktime'
            : contentType === 'text/vtt'
                ? '.vtt,text/vtt'
                : contentType === 'text' || contentType === 'text/*'
                ? '.vtt,text/vtt,.txt,text/plain'
            : 'image/*,video/mp4,video/webm,video/quicktime,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,.ppt,.pptx';

    return (
        <section className={styles.picker}>
            <div className={styles.heading}>
                <div><h3>{heading}</h3><p>Los archivos se guardan una sola vez en Files y pueden reutilizarse.</p></div>
                {allowUpload && (
                    <label className={styles.uploadButton}>
                        <FiUploadCloud /> {uploading ? 'Subiendo…' : 'Subir archivo'}
                        <input type="file" accept={accept} onChange={handleUpload} disabled={uploading} />
                    </label>
                )}
            </div>
            <div className={styles.toolbar}>
                <label className={styles.search}><FiSearch /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre" /></label>
                {!contentType && (
                    <select value={selectedType} onChange={(event) => setSelectedType(event.target.value)} aria-label="Filtrar por tipo">
                        <option value="">Todos</option><option value="image">Imágenes</option><option value="video">Videos</option><option value="application">Documentos</option>
                    </select>
                )}
                <button type="button" onClick={load} title="Actualizar"><FiRefreshCw /></button>
            </div>
            {error && <p className={styles.error} role="alert">{error}</p>}
            {loading ? <p className={styles.empty}>Cargando biblioteca…</p> : assets.length === 0 ? (
                <p className={styles.empty}>No hay recursos que coincidan con el filtro.</p>
            ) : (
                <div className={styles.grid}>
                    {assets.map((asset) => (
                        <article key={asset.id} className={`${styles.card} ${selectedId === asset.id ? styles.selected : ''}`}>
                            <button type="button" className={styles.selectButton} onClick={() => onSelect(asset)} aria-pressed={selectedId === asset.id}>
                                <div className={styles.preview}><AssetPreview asset={asset} /></div>
                                <strong title={asset.original_name}>{asset.original_name}</strong>
                                <span>{asset.content_type} · {formatSize(asset.size_bytes)}</span>
                            </button>
                            <div className={styles.cardActions}>
                                <a href={asset.url} target="_blank" rel="noreferrer">Abrir</a>
                                {allowDelete && <button type="button" onClick={() => handleDelete(asset)}><FiTrash2 /> Eliminar</button>}
                            </div>
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}
