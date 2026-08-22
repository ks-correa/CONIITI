import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FiCheck, FiEye, FiLock, FiPlus, FiRefreshCw, FiSlash, FiTarget } from 'react-icons/fi';

import {
    cancelRaffle,
    createRaffle,
    drawRaffleWinner,
    getRaffleEligibility,
    getRaffleResult,
    listRaffles,
    lockRaffleSnapshot,
    publishRaffle,
} from '../../services/raffleService';
import styles from '../../styles/components/RaffleManager.module.css';


const STATUS_LABELS = {
    draft: 'Borrador',
    eligibility_locked: 'Elegibilidad fijada',
    drawn: 'Sorteado',
    published: 'Publicado',
    cancelled: 'Cancelado',
};


function operationKey() {
    return globalThis.crypto?.randomUUID?.() ?? `draw-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}


function formatDate(value) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}


export default function RaffleManager() {
    const [raffles, setRaffles] = useState([]);
    const [formOpen, setFormOpen] = useState(false);
    const [name, setName] = useState('');
    const [winnerCount, setWinnerCount] = useState(1);
    const [sessionIds, setSessionIds] = useState('');
    const [selected, setSelected] = useState(null);
    const [eligibility, setEligibility] = useState(null);
    const [result, setResult] = useState(null);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const pendingDrawKeys = useRef(new Map());

    const load = useCallback(async () => {
        setError('');
        try {
            setRaffles(await listRaffles());
        } catch (err) {
            setError(err.message);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const selectedRaffle = useMemo(
        () => raffles.find((raffle) => raffle.id === selected) ?? null,
        [raffles, selected],
    );

    const run = async (key, callback) => {
        setBusy(key);
        setError('');
        try {
            await callback();
            await load();
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy('');
        }
    };

    const handleCreate = (event) => {
        event.preventDefault();
        const ids = sessionIds.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean);
        run('create', async () => {
            await createRaffle({
                name,
                winner_count: Number(winnerCount),
                eligibility_rule: {
                    require_registration: true,
                    ...(ids.length ? { session_ids: ids } : {}),
                },
            });
            setName('');
            setWinnerCount(1);
            setSessionIds('');
            setFormOpen(false);
        });
    };

    const inspect = async (raffle) => {
        setSelected(raffle.id);
        setEligibility(null);
        setResult(null);
        setBusy(`inspect-${raffle.id}`);
        setError('');
        try {
            if (raffle.snapshot_hash) {
                const [eligibleData, resultData] = await Promise.all([
                    getRaffleEligibility(raffle.id),
                    ['drawn', 'published', 'cancelled'].includes(raffle.status)
                        ? getRaffleResult(raffle.id)
                        : Promise.resolve(null),
                ]);
                setEligibility(eligibleData);
                setResult(resultData);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy('');
        }
    };

    const drawNext = (raffleId) => {
        const existingKey = pendingDrawKeys.current.get(raffleId);
        const idempotencyKey = existingKey ?? operationKey();
        pendingDrawKeys.current.set(raffleId, idempotencyKey);
        return run(`draw-${raffleId}`, async () => {
            await drawRaffleWinner(raffleId, idempotencyKey);
            pendingDrawKeys.current.delete(raffleId);
        });
    };

    return (
        <section className={styles.manager} aria-labelledby="raffles-title">
            <div className={styles.header}>
                <div>
                    <h2 id="raffles-title">Sorteos auditables</h2>
                    <p>Los candidatos proceden únicamente de asistencias confirmadas y quedan congelados antes del sorteo.</p>
                </div>
                <button className={styles.primary} onClick={() => setFormOpen((value) => !value)}>
                    <FiPlus /> Nuevo sorteo
                </button>
            </div>

            {error && <div className={styles.error} role="alert">{error}</div>}

            {formOpen && (
                <form className={styles.form} onSubmit={handleCreate}>
                    <label>
                        Nombre
                        <input required minLength={3} maxLength={180} value={name} onChange={(event) => setName(event.target.value)} />
                    </label>
                    <label>
                        Número de ganadores
                        <input type="number" min="1" max="100" value={winnerCount} onChange={(event) => setWinnerCount(event.target.value)} />
                    </label>
                    <label className={styles.wide}>
                        Sesiones elegibles (UUID separados por coma; vacío = todas)
                        <textarea rows="2" value={sessionIds} onChange={(event) => setSessionIds(event.target.value)} />
                    </label>
                    <button className={styles.primary} disabled={busy === 'create'}>
                        {busy === 'create' ? 'Creando…' : 'Crear borrador'}
                    </button>
                </form>
            )}

            <div className={styles.grid}>
                {raffles.length === 0 ? (
                    <div className={styles.empty}>Todavía no hay sorteos.</div>
                ) : raffles.map((raffle) => (
                    <article className={styles.card} key={raffle.id}>
                        <div className={styles.cardTop}>
                            <h3>{raffle.name}</h3>
                            <span className={`${styles.status} ${styles[raffle.status]}`}>{STATUS_LABELS[raffle.status]}</span>
                        </div>
                        <dl>
                            <div><dt>Elegibles</dt><dd>{raffle.eligible_count}</dd></div>
                            <div><dt>Ganadores</dt><dd>{raffle.drawn_count}/{raffle.winner_count}</dd></div>
                            <div><dt>Creado</dt><dd>{formatDate(raffle.created_at)}</dd></div>
                        </dl>
                        <div className={styles.actions}>
                            {raffle.status === 'draft' && (
                                <button onClick={() => run(`snapshot-${raffle.id}`, () => lockRaffleSnapshot(raffle.id))} disabled={Boolean(busy)}>
                                    <FiLock /> Fijar elegibilidad
                                </button>
                            )}
                            {(raffle.status === 'eligibility_locked' || raffle.status === 'drawn') && raffle.drawn_count < raffle.winner_count && (
                                <button className={styles.draw} onClick={() => drawNext(raffle.id)} disabled={Boolean(busy)}>
                                    <FiTarget /> Sortear siguiente
                                </button>
                            )}
                            {raffle.status === 'drawn' && raffle.drawn_count === raffle.winner_count && (
                                <button onClick={() => run(`publish-${raffle.id}`, () => publishRaffle(raffle.id))} disabled={Boolean(busy)}>
                                    <FiCheck /> Publicar resultado
                                </button>
                            )}
                            {!['published', 'cancelled'].includes(raffle.status) && (
                                <button className={styles.danger} onClick={() => run(`cancel-${raffle.id}`, () => cancelRaffle(raffle.id))} disabled={Boolean(busy)}>
                                    <FiSlash /> Cancelar
                                </button>
                            )}
                            <button onClick={() => inspect(raffle)} disabled={busy === `inspect-${raffle.id}`}>
                                <FiEye /> Auditar
                            </button>
                        </div>
                    </article>
                ))}
            </div>

            {selectedRaffle && (
                <aside className={styles.audit}>
                    <div className={styles.auditHeader}>
                        <div>
                            <h3>Auditoría: {selectedRaffle.name}</h3>
                            <code>{selectedRaffle.snapshot_hash ?? 'Snapshot no fijado'}</code>
                        </div>
                        <button aria-label="Cerrar auditoría" onClick={() => setSelected(null)}>×</button>
                    </div>
                    {busy === `inspect-${selectedRaffle.id}` ? <p><FiRefreshCw /> Consultando…</p> : (
                        <>
                            <h4>Elegibilidad ({eligibility?.total ?? 0})</h4>
                            <ul>
                                {(eligibility?.items ?? []).map((item) => (
                                    <li key={item.user_id}><strong>#{item.ordinal}</strong> {item.full_name ?? item.user_id}</li>
                                ))}
                            </ul>
                            <h4>Ganadores</h4>
                            {(result?.winners ?? []).length === 0 ? <p>Aún no hay ganadores.</p> : (
                                <ul>
                                    {result.winners.map((winner) => (
                                        <li key={winner.audit_hash ?? winner.winner_reference}>
                                            <strong>#{winner.draw_number}</strong> {winner.full_name ?? winner.user_id ?? winner.winner_reference}
                                            {winner.audit_hash && <code>{winner.audit_hash}</code>}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </>
                    )}
                </aside>
            )}
        </section>
    );
}
