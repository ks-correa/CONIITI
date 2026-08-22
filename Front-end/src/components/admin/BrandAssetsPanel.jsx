import AssetPicker from './AssetPicker';
import styles from '../../styles/components/SiteSettingsPanel.module.css';


function AssetField({ title, value, onChange }) {
    return (
        <div className={styles.assetField}>
            <h4>{title}</h4>
            {value?.url && <img src={value.url} alt={`Vista previa: ${title}`} className={styles.brandPreview} />}
            <AssetPicker
                selectedId={value?.assetId}
                contentType="image"
                onSelect={(asset) => onChange(asset ? { assetId: asset.id, url: asset.url } : { assetId: null, url: null })}
                heading={`Biblioteca para ${title.toLowerCase()}`}
            />
            {value?.assetId && <button type="button" className={styles.secondaryButton} onClick={() => onChange({ assetId: null, url: null })}>Quitar selección</button>}
        </div>
    );
}

export default function BrandAssetsPanel({ branding, onChange }) {
    return (
        <section className={styles.subpanel}>
            <div className={styles.subpanelHeader}><h3>Marca e imágenes</h3><p>Selecciona recursos existentes o súbelos al contenedor de Files.</p></div>
            <AssetField
                title="Logo del evento"
                value={{ assetId: branding.logo_asset_id, url: branding.logo_url }}
                onChange={(asset) => onChange({ ...branding, logo_asset_id: asset.assetId, logo_url: asset.url })}
            />
            <AssetField
                title="Imagen principal de inicio"
                value={{ assetId: branding.hero_asset_id, url: branding.hero_url }}
                onChange={(asset) => onChange({ ...branding, hero_asset_id: asset.assetId, hero_url: asset.url })}
            />
        </section>
    );
}
