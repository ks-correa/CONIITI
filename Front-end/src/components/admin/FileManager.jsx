import { FiAlertTriangle } from 'react-icons/fi';

import AssetPicker from './AssetPicker';
import styles from '../../styles/components/DocumentManager.module.css';


export default function FileManager() {
    return (
        <div>
            <AssetPicker
                allowUpload
                allowDelete
                heading="Biblioteca multimedia"
            />
            <p className={styles.hint} style={{ marginTop: '1rem' }}>
                <FiAlertTriangle style={{ verticalAlign: 'middle', marginRight: '.35rem' }} />
                Imágenes, videos y documentos se validan por firma y tamaño. Un recurso referenciado no puede eliminarse.
            </p>
        </div>
    );
}
