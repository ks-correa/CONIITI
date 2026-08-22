import { useEffect, useMemo, useState } from 'react';
import { FiCheckCircle, FiRefreshCw, FiXCircle } from 'react-icons/fi';

import { checkSystemStatus } from '../services/statusService';
import styles from '../styles/pages/Estado.module.css';


function formatTimestamp(value) {
    if (!value) return '--:--';
    return new Date(value).toLocaleTimeString();
}

export default function Estado() {
    const [checks, setChecks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState(null);

    const summary = useMemo(() => {
        const total = checks.length;
        const healthy = checks.filter((check) => check.ok).length;
        const latencies = checks
            .map((check) => check.latencyMs)
            .filter((latency) => Number.isFinite(latency));
        const averageLatencyMs = latencies.length
            ? Math.round(latencies.reduce((totalLatency, latency) => totalLatency + latency, 0) / latencies.length)
            : null;

        return { total, healthy, averageLatencyMs };
    }, [checks]);

    const loadStatus = async () => {
        setLoading(true);
        const results = await checkSystemStatus();
        setChecks(results);
        setLastUpdated(results[0]?.checkedAt ?? new Date().toISOString());
        setLoading(false);
    };

    useEffect(() => {
        let cancelled = false;
        checkSystemStatus().then((results) => {
            if (!cancelled) {
                setChecks(results);
                setLastUpdated(results[0]?.checkedAt ?? new Date().toISOString());
                setLoading(false);
            }
        });

        return () => {
            cancelled = true;
        };
    }, []);

    return (
        <div className={styles.page}>
            <section className={styles.hero}>
                <div>
                    <span className={styles.eyebrow}>Observabilidad local</span>
                    <h1>Estado del sistema</h1>
                    <p>Disponibilidad básica de los servicios expuestos por Traefik en el entorno local.</p>
                </div>
                <button className={styles.refreshButton} onClick={loadStatus} disabled={loading}>
                    <FiRefreshCw />
                    Actualizar
                </button>
            </section>
            
            <section className={styles.summaryBand}>
                <div>
                    <strong>{summary.healthy}/{summary.total || 8}</strong>
                    <span>servicios disponibles</span>
                </div>
                <div>
                    <strong>{summary.averageLatencyMs ?? '--'}{summary.averageLatencyMs !== null ? ' ms' : ''}</strong>
                    <span>latencia promedio</span>
                </div>
                <div>
                    <strong>{formatTimestamp(lastUpdated)}</strong>
                    <span>última verificación</span>
                </div>
            </section>

            <section className={styles.grid}>
                {loading && checks.length === 0 ? (
                    <div className={styles.empty}>Consultando servicios...</div>
                ) : (
                    checks.map((check) => (
                        <article key={check.id} className={`${styles.card} ${check.ok ? styles.ok : styles.down}`}>
                            <div className={styles.cardHead}>
                                {check.ok ? <FiCheckCircle /> : <FiXCircle />}
                                <div>
                                    <h2>{check.label}</h2>
                                    <p>{check.path}</p>
                                </div>
                            </div>
                            <dl>
                                <div>
                                    <dt>HTTP</dt>
                                    <dd>{check.statusCode ?? 'Sin respuesta'}</dd>
                                </div>
                                <div>
                                    <dt>Latencia</dt>
                                    <dd>{check.latencyMs} ms</dd>
                                </div>
                                <div>
                                    <dt>Estado</dt>
                                    <dd>{check.ok ? 'Disponible' : 'No disponible'}</dd>
                                </div>
                                <div>
                                    <dt>Verificado</dt>
                                    <dd>{formatTimestamp(check.checkedAt)}</dd>
                                </div>
                            </dl>
                            {check.error && <p className={styles.error}>{check.error}</p>}
                        </article>
                    ))
                )}
            </section>
        </div>
    );
}
