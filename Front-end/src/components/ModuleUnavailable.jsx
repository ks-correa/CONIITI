import { Link } from 'react-router-dom';

import styles from '../styles/components/ModuleUnavailable.module.css';


export default function ModuleUnavailable() {
    return (
        <section className={styles.page} role="status">
            <div className={styles.card}>
                <span aria-hidden="true">CONIITI</span>
                <h1>Sección no disponible</h1>
                <p>Este contenido está temporalmente oculto por la administración del evento.</p>
                <Link to="/">Volver al inicio</Link>
            </div>
        </section>
    );
}
